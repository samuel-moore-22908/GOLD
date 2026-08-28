# -*- coding: utf-8 -*-
"""
Author: Sam Moore
Purpose: Pull HS6 Trade Data
Date: 8/27/2026

CHUNK KEY IS (flow, country, year). One request returns every HS6 code that
partner traded in that year -- no commodity predicate needed at all. Measured
28 Aug 2026: Switzerland 27,843 rows in 8.9s, Canada 50,970 in 17.1s, China
53,187 in 13.5s. That is 2,400 requests for the whole panel, against 12,200 if
you chunk on the commodity dimension instead.

Findings from live testing that shape the rest of this script:

  1. get= MUST NOT contain spaces after commas. "I_COMMODITY, CTY_CODE" returns
     400 "unknown variable ''".
  2. If you DO filter commodities, only a wildcard works. A comma-separated
     list and a bare prefix both return 204 with an empty body -- a SILENT
     failure that reads as "no data". "7108*" works, "7108" does not. This is
     why the gold tier below uses a wildcard and the main pull uses none.
  3. time= accepts a whole year. Verified exact against twelve monthly pulls
     for HS 710812 in 2025: same 594 rows, same $51,791,089,686.
  4. Responses carry a CTY_CODE="-" row, "TOTAL FOR ALL COUNTRIES", despite
     SUMMARY_LVL=DET. When you are NOT filtering by country it equals the sum
     of the individual rows and is a free completeness audit; either way it
     must be dropped or it doubles every total.
  5. The response header repeats the commodity column, once from get= and once
     as the echoed predicate. Duplicate names make df["col"] a DataFrame, which
     breaks every cast and .str accessor. Only the first occurrence is kept.
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

## make a commodities list  (reference only -- the pull does not filter on it)

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
          timeout=600):
    """One request. Returns (DataFrame | None, status).

    country    a 4-digit Schedule C code. This is the chunk key.
    commodity  a WILDCARD like "71*", or None for every code that partner
               traded. A comma list or bare prefix silently returns 204.
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

    # The "-" row is TOTAL FOR ALL COUNTRIES. When no country filter is set it
    # equals the sum of the country rows, so use it as a completeness audit
    # before dropping it. Keeping it would double every total.
    is_country = df["CTY_CODE"].str.fullmatch(r"\d{4}")
    status = "ok"
    if not country and (~is_country).any():
        val = [c for c in ("GEN_VAL_MO", "ALL_VAL_MO") if c in df.columns][0]
        tot = pd.to_numeric(df.loc[~is_country, val], errors="coerce").sum()
        parts = pd.to_numeric(df.loc[is_country, val], errors="coerce").sum()
        if int(tot) != int(parts):
            status = "truncated"
    df = df[is_country].copy()
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

# parquet needs pyarrow or fastparquet. If neither is installed, fall back to
# gzipped CSV so the pull is not blocked by a missing optional dependency --
# but note that CSV loses dtypes, so the reader must force identifier columns
# back to str or leading zeros in CTY_CODE are destroyed on the way back in.
try:
    import pyarrow  # noqa: F401
    FMT = "parquet"
except ImportError:
    FMT = "csv.gz"

def save(df, tag):
    path = os.path.join(OUTDIR, tag + "." + FMT)
    if FMT == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False, compression="gzip")

def cached(tag):
    return os.path.exists(os.path.join(OUTDIR, tag + "." + FMT))

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


if __name__ == "__main__":

    if not API_KEY:
        raise SystemExit("Set CENSUS_API_KEY in the environment first.")
    os.makedirs(OUTDIR, exist_ok=True)

    # make session
    session = make_session(API_KEY)

    ## make a list of countries in the pull
    countries = fetch_countries()
    print("countries: %d" % len(countries))

    jobs = []

    # main panel: one request per (flow, country, year), no commodity filter
    for year in YEARS:
        for c in countries:
            code = c["cty_code"]
            jobs.append(("imports_all_%s_%s" % (year, code),
                         "imports", IMPORTS_ALL, year, code, None))
            jobs.append(("exports_all_%s_%s" % (year, code),
                         "exports", EXPORTS_ALL, year, code, None))

    # gold tier: the wide field set. Small enough to take every country at once,
    # so it needs a commodity wildcard rather than a country loop.
    for year in YEARS:
        jobs.append(("imports_71_%s" % year, "imports", IMPORTS_71, year, None, "71*"))
        jobs.append(("exports_71_%s" % year, "exports", EXPORTS_71, year, None, "71*"))

    print("jobs: %d" % len(jobs))

    manifest, done = [], 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(_job, session, j): j[0] for j in jobs}
        for f in as_completed(futures):
            tag, status, rows = f.result()
            manifest.append({"tag": tag, "status": status, "rows": rows})
            done += 1
            if status not in ("ok", "cached", "empty"):
                print("  ! %-32s %s" % (tag, status))
            if done % 100 == 0:
                el = time.time() - t0
                print("  %d/%d  %.1f min elapsed, ~%.0f min left"
                      % (done, len(jobs), el / 60, (len(jobs) - done) * el / done / 60))

    pd.DataFrame(manifest).to_csv(os.path.join(OUTDIR, "manifest.csv"), index=False)
    ok = sum(1 for m in manifest if m["status"] in ("ok", "cached"))
    print("done in %.1f min. %d/%d ok, %s rows"
          % ((time.time() - t0) / 60, ok, len(manifest),
             format(sum(m["rows"] for m in manifest), ",")))
