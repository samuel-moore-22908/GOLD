# -*- coding: utf-8 -*-
"""
Author: Sam Moore
Purpose: Pull HS6 Trade Data
Date: 8/28/2026

Two tiers, deliberately different in shape:

  UNIVERSE -- overall by-commodity flows, no country dimension. Grain is
  (flow, time, commodity). Chapter 71 is in it with the basic variables, so the
  gold codes sit on the same footing as every other commodity for the
  Grubel-Lloyd comparison.

  GOLD -- chapter 71 with the wide field set, by country. Grain is
  (flow, time, commodity, country).

The universe tier does not need a country loop because Census returns a
CTY_CODE="-" row, "TOTAL FOR ALL COUNTRIES", and that row can be REQUESTED
directly with CTY_CODE=-. One request then returns every HS6 code the US traded
that year against the world: 65,122 import rows in 11.1s, 189,234 export rows
in 49.3s (exports are larger because DF splits domestic from re-export).

The gold tier does not need a country loop either. A "71*" wildcard with no
country filter already returns every partner -- 54 codes across 186 partners
with all 27 fields. Restricting to the top gold partners is therefore a filter
applied to data already in hand, not a reason to issue 500 requests. The
shortlist is still written out, ranked on chapter 71 trade rather than total
trade, because a bullion hub can be trivial in overall trade.

Total: 20 requests, roughly ten minutes.

Findings from live testing that shape this script:

  1. get= MUST NOT contain spaces after commas. "I_COMMODITY, CTY_CODE" returns
     400 "unknown variable ''".
  2. If you filter commodities, only a wildcard works. A comma-separated list
     and a bare prefix both return 204 with an empty body -- a SILENT failure
     that reads as "no data". "7108*" works, "7108" does not.
  3. time= accepts a whole year. Verified exact against twelve monthly pulls
     for HS 710812 in 2025: same 594 rows, same $51,791,089,686.
  4. The CTY_CODE="-" row equals the sum of the individual country rows. In the
     gold tier that is a free completeness audit; in the universe tier it IS
     the payload.
  5. EXPORTS carry the same trap on a second dimension. DF has THREE values --
     "1" domestic, "2" re-exports, and "-" their total -- so summing the raw
     response double-counts every export figure. Verified 2025: 1,759.1 + 420.8
     = 2,179.9bn, which is also what the "-" rows alone come to, and what
     Census publishes.
  6. The response header repeats the commodity column, once from get= and once
     as the echoed predicate. Duplicate names make df["col"] a DataFrame, which
     breaks every cast and .str accessor. Only the first occurrence is kept.

Reconciles exactly: the HS6 pull for Switzerland 2025 sums to $106.21bn against
the $106.21bn Census publishes on its country balance page.
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Key comes from the environment. transfer/ is not gitignored.
API_KEY = os.environ.get("CENSUS_API_KEY", "")
CODES = "https://www.census.gov/foreign-trade/schedules/b/{year}/{side}-code.txt"
COUNTRIES = "https://www.census.gov/foreign-trade/schedules/c/country.txt"

## Variables to pull

IMPORTS_ALL = "I_COMMODITY,CTY_CODE,GEN_VAL_MO,CON_VAL_MO,GEN_QY1_MO,UNIT_QY1"
EXPORTS_ALL = "E_COMMODITY,CTY_CODE,ALL_VAL_MO,QTY_1_MO,UNIT_QY1,DF"

IMPORTS_71 = ("I_COMMODITY,CTY_CODE,GEN_VAL_MO,CON_VAL_MO,GEN_QY1_MO,UNIT_QY1,"
              "GEN_CIF_MO,CON_CIF_MO,GEN_CHA_MO,CON_CHA_MO,"
              "AIR_VAL_MO,AIR_WGT_MO,AIR_CHA_MO,"
              "VES_VAL_MO,VES_WGT_MO,VES_CHA_MO,"
              "CNT_VAL_MO,CNT_WGT_MO,CNT_CHA_MO,"
              "CAL_DUT_MO,DUT_VAL_MO,GEN_QY1_MO_FLAG"
              )

# QTY_1_MO_FLAG, not GEN_QY1_MO_FLAG -- that field exists only on imports.
EXPORTS_71 = ("E_COMMODITY,CTY_CODE,ALL_VAL_MO,QTY_1_MO,UNIT_QY1,DF,"
              "AIR_VAL_MO,AIR_WGT_MO,VES_VAL_MO,VES_WGT_MO,"
              "CNT_VAL_MO,CNT_WGT_MO,QTY_1_MO_FLAG"
              )

# Identifiers stay text. Coerce CTY_CODE and "0304" becomes 304, silently.
KEEP_STR = {"I_COMMODITY", "E_COMMODITY", "CTY_CODE", "CTY_NAME", "UNIT_QY1",
            "UNIT_QY2", "DF", "time", "YEAR", "MONTH", "COMM_LVL", "SUMMARY_LVL",
            "DISTRICT", "DIST_NAME", "RP", "CTY_SUBCODE"}

IMPORT_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
EXPORT_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"

YEARS = range(2022, 2027)
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
WORKERS = 3        # modest on purpose; Census publishes no rate limit
PAUSE = 0.8        # per worker

TOP_GOLD = 50      # partners kept in the gold panel, ranked on chapter 71 trade

# parquet needs pyarrow or fastparquet. Fall back to gzipped CSV so a missing
# optional dependency does not block the pull -- but CSV loses dtypes, so the
# reader must force identifier columns back to str or leading zeros die.
try:
    import pyarrow  # noqa: F401
    FMT = "parquet"
except ImportError:
    FMT = "csv.gz"

## make the session

def make_session(key):
    s = requests.Session()
    s.mount("https://", HTTPAdapter(
        max_retries=Retry(total=5, backoff_factor=1.5,
                          status_forcelist=[429, 500, 502, 503, 504],
                          allowed_methods=["GET"]),
        pool_connections=WORKERS, pool_maxsize=WORKERS))
    s.params = {"key": key}
    return s

def _cast(df):
    for c in df.columns:
        if c in KEEP_STR or c.endswith("_FLAG"):
            df[c] = df[c].astype("string")
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _frame(data):
    """Keep only the first occurrence of each column name -- the header repeats
    the commodity column."""
    header = data[0]
    keep = [i for i, c in enumerate(header) if not header[:i].count(c)]
    return pd.DataFrame([[r[i] for i in keep] for r in data[1:]],
                        columns=[header[i] for i in keep])

## make a commodities list  (reference only -- neither tier filters on a list)

def fetch_import_categories(year):
    text = requests.get(CODES.format(year=year, side="imp"), timeout=180).text
    hs6 = {m.group(1)[:6] for m in re.finditer(r"^(\d{10})\s", text, re.M)}
    return sorted(c for c in hs6 if c[:2] not in ("98", "99"))

def fetch_export_categories(year):
    text = requests.get(CODES.format(year=year, side="exp"), timeout=180).text
    hs6 = {m.group(1)[:6] for m in re.finditer(r"^(\d{10})\s", text, re.M)}
    return sorted(c for c in hs6 if c[:2] not in ("98", "99"))

# make a countries list

def fetch_countries():
    text = requests.get(COUNTRIES, timeout=120).text
    rows = re.findall(r"^\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*([A-Z-]{0,2})\s*$", text, re.M)
    out = [{"cty_code": c, "cty_name": n, "iso2": i or None} for c, n, i in rows]
    out = [c for c in out if c["cty_code"] != "1000"] # drops USA
    return out

## the pull

def _pull(session, url, code_var, variables, year, country=None, commodity=None,
          timeout=900):
    """One request. Returns (DataFrame | None, status).

    country    "-" for the world total only, a 4-digit Schedule C code for one
               partner, or None for every partner
    commodity  a WILDCARD like "71*", or None for every code. A comma list or a
               bare prefix silently returns 204.
    """
    params = {
        "get": variables,
        "time": str(year),
        "COMM_LVL": "HS6",
        "SUMMARY_LVL": "DET",
        }
    if country:
        params["CTY_CODE"] = country
    if commodity:
        params[code_var] = commodity

    try:
        r = session.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return None, type(e).__name__

    if r.status_code in (204, 404) or not r.content.strip():
        return None, "empty"
    if r.status_code != 200:
        return None, str(r.status_code)
    if "json" not in r.headers.get("content-type", ""):
        return None, "non-json"          # bad key returns HTML with a 200
    data = r.json()
    if len(data) < 2:
        return None, "empty"

    df = _frame(data)
    is_country = df["CTY_CODE"].str.fullmatch(r"\d{4}")
    status = "ok"

    if country == "-":
        # The "-" rows ARE the payload here: totals against the world, by
        # commodity. Keep them and drop nothing.
        df = df[~is_country].copy()
    else:
        # Otherwise the "-" row is an aggregate that would double every total.
        # With no country filter it must equal the sum of the country rows, so
        # audit against it before dropping it.
        if not country and (~is_country).any():
            val = [c for c in ("GEN_VAL_MO", "ALL_VAL_MO") if c in df.columns][0]
            tot = pd.to_numeric(df.loc[~is_country, val], errors="coerce").sum()
            parts = pd.to_numeric(df.loc[is_country, val], errors="coerce").sum()
            if int(tot) != int(parts):
                status = "truncated"
        df = df[is_country].copy()

    # Exports carry the SAME trap on a second dimension. DF comes back with
    # three values, not two: "1" domestic, "2" foreign (re-exports), and "-"
    # which is their TOTAL. Verified for 2025: 1,759.1 + 420.8 = 2,179.9bn, and
    # the "-" rows alone are 2,179.9bn -- exactly the published figure. Keeping
    # all three doubles every export total, silently and plausibly. The split is
    # what makes re-exports visible, so "1" and "2" are kept and "-" is used as
    # an audit and then dropped.
    if "DF" in df.columns:
        is_split = df["DF"].isin(["1", "2"])
        if (~is_split).any() and is_split.any():
            tot = pd.to_numeric(df.loc[~is_split, "ALL_VAL_MO"], errors="coerce").sum()
            parts = pd.to_numeric(df.loc[is_split, "ALL_VAL_MO"], errors="coerce").sum()
            if int(tot) != int(parts):
                status = "df_mismatch"
        df = df[is_split].copy()

    if df.empty:
        return None, "empty"

    df = _cast(df)
    df["flow"] = "imports" if code_var == "I_COMMODITY" else "exports"
    df["period"] = str(year)
    return df, status

def export_pull(session, variables, year, country=None, commodity=None):
    return _pull(session, EXPORT_URL, "E_COMMODITY", variables, year, country, commodity)

def import_pull(session, variables, year, country=None, commodity=None):
    return _pull(session, IMPORT_URL, "I_COMMODITY", variables, year, country, commodity)

def save(df, tag):
    path = os.path.join(OUTDIR, tag + "." + FMT)
    if FMT == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False, compression="gzip")

def cached(tag):
    return os.path.exists(os.path.join(OUTDIR, tag + "." + FMT))

def load(tag):
    path = os.path.join(OUTDIR, tag + "." + FMT)
    if FMT == "parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, dtype={"CTY_CODE": str, "I_COMMODITY": str,
                                    "E_COMMODITY": str})

def _job(session, spec):
    """One unit of work: (tag, flow, variables, year, country, commodity)."""
    tag, flow, variables, year, country, commodity = spec
    if cached(tag):
        return tag, "cached", 0
    fn = import_pull if flow == "imports" else export_pull
    df, status = fn(session, variables, year, country, commodity)
    if df is not None:
        save(df, tag)
    time.sleep(PAUSE)
    return tag, status, 0 if df is None else len(df)

def run(session, jobs, label):
    """Work a job list through the pool. Returns manifest rows."""
    manifest, done, t0 = [], 0, time.time()
    print("%s: %d jobs" % (label, len(jobs)))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(_job, session, j): j[0] for j in jobs}
        for f in as_completed(futures):
            tag, status, rows = f.result()
            manifest.append({"tag": tag, "status": status, "rows": rows})
            done += 1
            print("  %-26s %-10s %s rows" % (tag, status, format(rows, ",")))
    print("  %s done in %.1f min" % (label, (time.time() - t0) / 60))
    return manifest

## rank the gold partners
#
# Ranked on chapter 71 trade, both directions, pooled over YEARS -- not on total
# goods trade. A bullion hub can be trivial in overall trade, and ranking on the
# wrong quantity would drop exactly the partners this project is about.

def gold_partners(tags):
    frames = [load(t) for t in tags if cached(t)]
    if not frames:
        raise SystemExit("Gold tier not pulled yet.")
    d = pd.concat(frames, ignore_index=True)
    v = d["GEN_VAL_MO"].fillna(0) if "GEN_VAL_MO" in d.columns else 0
    if "ALL_VAL_MO" in d.columns:
        v = v + d["ALL_VAL_MO"].fillna(0)
    g = (d.assign(v=v).groupby("CTY_CODE", as_index=False)["v"].sum()
          .rename(columns={"CTY_CODE": "cty_code", "v": "ch71_usd"})
          .sort_values("ch71_usd", ascending=False).reset_index(drop=True))
    g["rank_ch71"] = g.index + 1
    g["share_ch71"] = 100 * g.ch71_usd / g.ch71_usd.sum()
    names = {c["cty_code"]: c["cty_name"] for c in fetch_countries()}
    g["cty_name"] = g.cty_code.map(names)
    g["selected"] = g.rank_ch71 <= TOP_GOLD
    return g


if __name__ == "__main__":

    if not API_KEY:
        raise SystemExit("Set CENSUS_API_KEY in the environment first.")
    os.makedirs(OUTDIR, exist_ok=True)

    # make session
    session = make_session(API_KEY)
    manifest = []

    # tier 1: universe. Overall by-commodity flows against the world, basic
    # variables, chapter 71 included on the same footing as everything else.
    universe_jobs = []
    for year in YEARS:
        universe_jobs.append(("universe_imports_%s" % year,
                              "imports", IMPORTS_ALL, year, "-", None))
        universe_jobs.append(("universe_exports_%s" % year,
                              "exports", EXPORTS_ALL, year, "-", None))
    manifest += run(session, universe_jobs, "tier 1 universe (by commodity)")

    # tier 2: gold. Chapter 71, wide fields, every partner.
    gold_jobs, gold_tags = [], []
    for year in YEARS:
        for flow, var in (("imports", IMPORTS_71), ("exports", EXPORTS_71)):
            tag = "gold_%s_%s" % (flow, year)
            gold_jobs.append((tag, flow, var, year, None, "71*"))
            gold_tags.append(tag)
    manifest += run(session, gold_jobs, "tier 2 gold (by country)")

    # rank the gold partners and write the shortlist
    g = gold_partners(gold_tags)
    g.to_csv(os.path.join(OUTDIR, "gold_partners_ranked.csv"), index=False)
    sel = g[g.selected]
    sel.to_csv(os.path.join(OUTDIR, "gold_partners_top%d.csv" % TOP_GOLD), index=False)
    print("\ngold partners: top %d of %d cover %.2f%% of chapter 71 trade"
          % (TOP_GOLD, len(g), sel.share_ch71.sum()))

    # write the gold panel restricted to those partners
    keep = set(sel.cty_code)
    gold = pd.concat([load(t) for t in gold_tags if cached(t)], ignore_index=True)
    gold = gold[gold.CTY_CODE.isin(keep)]
    save(gold, "gold_panel_top%d" % TOP_GOLD)
    print("gold panel: %s rows, %d partners, %d codes"
          % (format(len(gold), ","), gold.CTY_CODE.nunique(),
             gold.filter(regex="COMMODITY").iloc[:, 0].nunique()))

    # write the universe panel
    uni = pd.concat([load(t) for t in
                     ["universe_%s_%s" % (f, y) for y in YEARS
                      for f in ("imports", "exports")] if cached(t)],
                    ignore_index=True)
    save(uni, "universe_panel")
    print("universe panel: %s rows, %d codes"
          % (format(len(uni), ","), uni.filter(regex="COMMODITY").iloc[:, 0].nunique()))

    pd.DataFrame(manifest).to_csv(os.path.join(OUTDIR, "manifest.csv"), index=False)
    ok = sum(1 for m in manifest if m["status"] in ("ok", "cached"))
    print("\ndone. %d/%d jobs ok" % (ok, len(manifest)))
