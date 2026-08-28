# -*- coding: utf-8 -*-
"""
Author: Sam Moore
Purpose: Pull HS6 Trade Data
Date: 8/27/2026

Findings from live testing that shape this script (all verified 28 Aug 2026):

  1. get= MUST NOT contain spaces after commas. "I_COMMODITY, CTY_CODE" returns
     400 "unknown variable ''". Strings below are stripped before use.
  2. The commodity predicate does NOT accept a comma-separated list. Any list
     returns 204 with an empty body -- a SILENT failure that looks like "no
     data". Only an exact code or a WILDCARD PREFIX works: "7108*" is fine,
     "7108" and "710811,710812" are not.
  3. time= accepts a whole year. Verified exact against twelve monthly pulls
     for HS 710812 in 2025: same 594 rows, same $51,791,089,686. Twelve times
     fewer requests for identical data.
  4. Every response carries a CTY_CODE="-" row, "TOTAL FOR ALL COUNTRIES",
     DESPITE SUMMARY_LVL=DET. It equals the sum of the individual countries, so
     keeping it doubles every total. It is filtered out below.
  5. The response header repeats the commodity column (once from get=, once as
     the echoed predicate). pd.DataFrame with duplicate names makes df["col"]
     return a DataFrame, which breaks _cast and every .str accessor. Only the
     first occurrence of each name is kept.
  6. Chapter-wide wildcards are slow and fail on big chapters: "71*" took 64s
     for one month, "84*" returned a 500 after 150s. So the chunk key is the
     HS4 prefix, which is small and reliable.
"""

import os
import re
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Key comes from the environment. Do not hardcode it -- transfer/ is not
# gitignored, so a stray `git add .` would publish it.
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

# Identifiers stay text. Coerce these and CTY_CODE "0304" becomes 304, silently,
# and that corridor stops matching for the rest of the project.
KEEP_STR = {"I_COMMODITY", "E_COMMODITY", "CTY_CODE", "CTY_NAME", "UNIT_QY1",
            "UNIT_QY2", "DF", "time", "YEAR", "MONTH", "COMM_LVL", "SUMMARY_LVL",
            "DISTRICT", "DIST_NAME", "RP", "CTY_SUBCODE"}

IMPORT_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
EXPORT_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
PAUSE = 1.2

## make the session

def make_session(key):
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"])))
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
    """Build a DataFrame from the API's list-of-lists, keeping only the first
    occurrence of each column name (the header repeats the commodity column)."""
    header = data[0]
    keep = [i for i, c in enumerate(header) if not header[:i].count(c)]
    rows = [[r[i] for i in keep] for r in data[1:]]
    return pd.DataFrame(rows, columns=[header[i] for i in keep])

## make a commodities list

def fetch_import_categories(year):
    hs6 = set()
    text = requests.get(CODES.format(year=year, side="imp"),
                        timeout=180).text
    hs6 |= {m.group(1)[:6] for m in re.finditer(r"^(\d{10})\s", text, re.M)}
    hs6 = {c for c in hs6 if c[:2] not in ("98", "99")}
    return sorted(hs6)

def fetch_export_categories(year):
    hs6 = set()
    text = requests.get(CODES.format(year=year, side="exp"),
                        timeout=180).text
    hs6 |= {m.group(1)[:6] for m in re.finditer(r"^(\d{10})\s", text, re.M)}
    hs6 = {c for c in hs6 if c[:2] not in ("98", "99")}
    return sorted(hs6)

# make a countries list

def fetch_countries():
    text = requests.get(COUNTRIES, timeout=120).text
    rows = re.findall(r"^\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*([A-Z-]{0,2})\s*$", text, re.M)
    out = [{"cty_code": c, "cty_name": n, "iso2": i or None} for c, n, i in rows]
    out = [c for c in out if c["cty_code"] != "1000"] # drops USA
    return out

def prefixes(hs6_list, n=4):
    """The chunk keys: distinct HS4 prefixes, queried as wildcards."""
    return sorted({c[:n] for c in hs6_list})

def _pull(session, url, code_var, variables, time_period, prefix, country=None,
          timeout=300):
    """One request. Returns (DataFrame | None, status).

    prefix is a wildcard like "7108*". A comma-separated list of codes silently
    returns 204, so it is not an option. country=None means every partner comes
    back in one response -- iterating countries would multiply requests by ~240
    for identical data.
    """
    params = {
        "get": variables,
        "time": time_period,
        "COMM_LVL": "HS6",
        "SUMMARY_LVL": "DET",
        code_var: prefix,
        }
    if country:
        params["CTY_CODE"] = country

    try:
        r = session.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return None, type(e).__name__

    if r.status_code in (204, 404) or not r.content.strip():
        return None, "empty"
    if r.status_code != 200:
        return None, str(r.status_code)
    if "json" not in r.headers.get("content-type", ""):
        return None, "non-json"          # missing/invalid key returns HTML with a 200
    data = r.json()
    if len(data) < 2:
        return None, "empty"

    df = _frame(data)

    # Drop the "TOTAL FOR ALL COUNTRIES" row. It survives SUMMARY_LVL=DET and
    # equals the sum of the individual countries, so keeping it doubles totals.
    df = df[df["CTY_CODE"].str.fullmatch(r"\d{4}")].copy()
    if df.empty:
        return None, "empty"

    df = _cast(df)
    returned = set(df[code_var].dropna())
    if not all(c.startswith(prefix.rstrip("*")) for c in returned):
        return df, "leaked commodities"
    df["flow"] = "imports" if code_var == "I_COMMODITY" else "exports"
    df["period"] = time_period
    return df, "ok"

def export_pull(session, variables, time_period, prefix, country=None):
    return _pull(session, EXPORT_URL, "E_COMMODITY", variables, time_period,
                 prefix, country)

def import_pull(session, variables, time_period, prefix, country=None):
    return _pull(session, IMPORT_URL, "I_COMMODITY", variables, time_period,
                 prefix, country)

def save(df, tag):
    os.makedirs(OUTDIR, exist_ok=True)
    df.to_parquet(os.path.join(OUTDIR, tag + ".parquet"), index=False)


if __name__ == "__main__":

    if not API_KEY:
        raise SystemExit("Set CENSUS_API_KEY in the environment first.")

    # make session
    session = make_session(API_KEY)

    ## make a list of countries in the pull
    countries = fetch_countries()
    print("countries: %d" % len(countries))

    manifest = []

    for year in range(2022, 2027):

        #make a list of HS6 commodity codes for each year (imports and exports)
        # should be the same, but need to be safe
        hs6_imports = fetch_import_categories(year)
        hs6_exports = fetch_export_categories(year)

        # makes batches excluding gold
        hs6_imports_nGold = [c for c in hs6_imports if not c.startswith("71")]
        hs6_imports_Gold  = [c for c in hs6_imports if c.startswith("71")]
        hs6_exports_nGold = [c for c in hs6_exports if not c.startswith("71")]
        hs6_exports_Gold  = [c for c in hs6_exports if c.startswith("71")]

        # chunk keys are HS4 wildcard prefixes, not code lists
        import_batches = prefixes(hs6_imports_nGold)
        export_batches = prefixes(hs6_exports_nGold)

        # special gold batches
        import_gold_batches = prefixes(hs6_imports_Gold)
        export_gold_batches = prefixes(hs6_exports_Gold)

        # time= takes a whole year, verified identical to twelve monthly pulls
        period = str(year)
        print("Pulling: %s  (%d import / %d export prefixes)"
              % (period, len(import_batches), len(export_batches)))

        for label, pull_fn, variables, batches in (
                ("imports_all", import_pull, IMPORTS_ALL, import_batches),
                ("exports_all", export_pull, EXPORTS_ALL, export_batches),
                ("imports_71",  import_pull, IMPORTS_71,  import_gold_batches),
                ("exports_71",  export_pull, EXPORTS_71,  export_gold_batches)):

            for prefix in batches:
                tag = "%s_%s_%s" % (label, period, prefix)
                if os.path.exists(os.path.join(OUTDIR, tag + ".parquet")):
                    continue                       # resume: already fetched

                df, status = pull_fn(session, variables, period, prefix + "*")
                if df is not None and status in ("ok", "leaked commodities"):
                    save(df, tag)
                manifest.append({"tag": tag, "status": status,
                                 "rows": 0 if df is None else len(df)})
                time.sleep(PAUSE)

        pd.DataFrame(manifest).to_csv(
            os.path.join(OUTDIR, "manifest.csv"), index=False)

    print("done. %d chunks, %d ok" %
          (len(manifest), sum(1 for m in manifest if m["status"] == "ok")))
