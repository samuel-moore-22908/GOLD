"""
Act I, step 2. Pull the US bilateral HS6 trade panel.

Scope, and why it is what it is:

  WINDOW 2022-01 .. 2026-05. HS6 codes are revised on a five-year cycle and both
  HS2017 and HS2022 fall inside a 2015-2026 sample; roughly a tenth of
  subheadings are created, split or merged across a revision. HS2022 entered
  force on 1 January 2022, so a panel starting there sits entirely inside one HS
  edition and needs no correlation table at all. That single restriction removes
  a day or two of concordance work and a permanent footnote, and it costs
  nothing, because the difference-in-differences windows (pre 2023-06..2024-11,
  post 2024-12..2026-05) both sit inside it with 35 months of pre-period to
  spare.

  TWO TIERS. The universe pull carries six lean fields across all chapters --
  country names and long descriptions are excluded because they repeat on every
  one of roughly sixteen million rows and are cheaper to join afterwards from
  the concordance. Chapter 71 is pulled again with a wider field set: four HS6
  codes, so the extra width is free, and it buys air charges and shipping
  weight (freight cost per kilogram, measured, on the leg that matters, since
  bullion moves by air) and calculated duty (how you show from the primary
  source that nothing was collected on gold).

  RESUMABLE. Around ten thousand requests over several hours. Something will
  fail. Every chunk is written to its own parquet file and recorded in a
  manifest; re-running skips whatever already succeeded. Never append to a
  single growing file in a job this long.

Set CHUNK_MODE from the step-1 probe report before running. Field names were
read from the endpoints' own variables.json, not guessed; note that imports call
the quantity field GEN_QY1_MO while exports call it QTY_1_MO.

Usage:
    set CENSUS_API_KEY=...
    python 02_pull_hs6_panel.py --tier universe
    python 02_pull_hs6_panel.py --tier gold
    python 02_pull_hs6_panel.py --consolidate
"""
import argparse
import json
import os
import random
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path("claude/act1-hs6-census-pull")
OUT = ROOT / "output"
RAW = OUT / "raw"
MANIFEST = OUT / "manifest.csv"

API = "https://api.census.gov/data/timeseries/intltrade/{flow}/hs"
KEY = os.environ.get("CENSUS_API_KEY", "")

# The window and the chapter list live in 01b_build_worklist.py, which is the
# single source of truth for the plan. This script only executes it.

# VERIFIED AGAINST THE LIVE API, 28 Aug 2026. Only the wildcard form works:
#   "prefix_wildcard"  I_COMMODITY=7108*   -> 200, correct rows        USE THIS
#   "explicit_list"    I_COMMODITY=a,b,c   -> 204 EMPTY BODY, silently
#   "prefix_bare"      I_COMMODITY=7108    -> 204 EMPTY BODY, silently
#   "month_only"       no predicate        -> times out on a full month
# The two silent-204 forms are the dangerous ones: they look like "no data"
# rather than a bad request, so a whole run can complete and produce nothing.
# Chunk on the HS4 prefix -- chapter-wide wildcards are slow ("71*" took 64s
# for one month) and fail outright on large chapters ("84*" returned a 500).
CHUNK_MODE = "prefix_wildcard"

PAUSE = 1.2          # deliberate pacing between calls
JITTER = 0.4
MAX_RETRIES = 5
TIMEOUT = 180

UNIVERSE_IMPORT = ["I_COMMODITY", "CTY_CODE", "GEN_VAL_MO", "CON_VAL_MO",
                   "GEN_QY1_MO", "UNIT_QY1"]
UNIVERSE_EXPORT = ["E_COMMODITY", "CTY_CODE", "ALL_VAL_MO", "QTY_1_MO",
                   "UNIT_QY1", "DF"]
GOLD_IMPORT = UNIVERSE_IMPORT + [
    "GEN_CIF_MO", "GEN_CHA_MO", "CON_CHA_MO", "CON_CIF_MO",
    "AIR_VAL_MO", "AIR_WGT_MO", "AIR_CHA_MO",
    "VES_VAL_MO", "VES_WGT_MO", "VES_CHA_MO",
    "CAL_DUT_MO", "DUT_VAL_MO", "GEN_QY1_MO_FLAG"]
GOLD_EXPORT = UNIVERSE_EXPORT + [
    "AIR_VAL_MO", "AIR_WGT_MO", "VES_VAL_MO", "VES_WGT_MO", "QTY_1_MO_FLAG"]

CODE_VAR = {"imports": "I_COMMODITY", "exports": "E_COMMODITY"}


def load_worklist(tier):
    """The iteration plan, built once by 01b_build_worklist.py. Keeping it in a
    file rather than regenerating it here means the plan that was validated is
    the plan that runs, and a resumed job cannot silently re-plan itself."""
    path = OUT / "worklist_{}.csv".format(tier)
    if not path.exists():
        raise SystemExit("Missing {}. Run 01b_build_worklist.py first.".format(path))
    return pd.read_csv(path, dtype={"chapter": str, "codes": str, "month": str})


# ------------------------------------------------------------------ manifest
def load_manifest():
    if MANIFEST.exists():
        return pd.read_csv(MANIFEST, dtype=str).set_index("chunk_id").to_dict("index")
    return {}


def append_manifest(rec):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    header = not MANIFEST.exists()
    pd.DataFrame([rec]).to_csv(MANIFEST, mode="a", header=header, index=False)


# ------------------------------------------------------------------ fetching
def build_params(flow, month, fields, chapter, codes):
    p = {"get": ",".join(fields), "time": month,
         "COMM_LVL": "HS6", "SUMMARY_LVL": "DET", "key": KEY}
    var = CODE_VAR[flow]
    if CHUNK_MODE == "explicit_list":
        p[var] = ",".join(codes)
    elif CHUNK_MODE == "prefix_wildcard":
        p[var] = chapter + "*"
    elif CHUNK_MODE == "prefix_bare":
        p[var] = chapter
    return p


def fetch(flow, params):
    """Returns (dataframe_or_None, status_string). An empty result is a normal
    outcome -- plenty of chapter-months have no trade -- and is distinguished
    from a failure so the manifest does not mark it for retry forever."""
    last = ""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(API.format(flow=flow), params=params, timeout=TIMEOUT)
        except Exception as exc:                    # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, exc)
            time.sleep(2 ** attempt + random.random())
            continue

        if r.status_code in (204,) or (r.status_code == 200 and not r.content.strip()):
            return None, "empty"
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            try:
                data = r.json()
            except ValueError as exc:
                last = "unparseable: {}".format(exc)
            else:
                if len(data) < 2:
                    return None, "empty"
                return pd.DataFrame(data[1:], columns=data[0]), "ok"
        elif r.status_code == 200:
            # Unkeyed requests return an HTML page with a 200. Fail loudly
            # rather than silently writing a chunk of nothing.
            return None, "non_json_200"
        elif r.status_code == 404:
            # The API answers "no records match" with a 404 on these endpoints.
            return None, "empty"
        elif r.status_code in (429, 500, 502, 503, 504):
            last = "http {}".format(r.status_code)
            time.sleep(2 ** attempt + random.random())
            continue
        else:
            return None, "http_{}".format(r.status_code)
    return None, "failed:{}".format(last[:120])


def validate(df, flow, chapter):
    """Cheap invariants, checked on every chunk. A silent violation here is a
    wrong headline number three weeks later."""
    var = CODE_VAR[flow]
    problems = []
    if var not in df.columns:
        problems.append("missing " + var)
        return problems
    codes = df[var].astype(str)
    if not codes.str.len().eq(6).all():
        problems.append("non-6-digit codes present")
    if CHUNK_MODE != "month_only" and not codes.str.startswith(chapter).all():
        problems.append("codes outside chapter " + chapter)
    if "CTY_CODE" in df.columns:
        cty = df["CTY_CODE"].astype(str)
        # Country groupings are excluded by SUMMARY_LVL=DET; this catches the
        # case where that stops working, which would double-count everything.
        if not cty.str.fullmatch(r"\d{4}").all():
            problems.append("non 4-digit country codes -- SUMMARY_LVL may have failed")
    return problems


# ------------------------------------------------------------------ the loop
def run(tier):
    if not KEY:
        raise SystemExit("No CENSUS_API_KEY set.")
    work = load_worklist(tier)
    fields = {"imports": GOLD_IMPORT if tier == "gold" else UNIVERSE_IMPORT,
              "exports": GOLD_EXPORT if tier == "gold" else UNIVERSE_EXPORT}

    done = load_manifest()
    settled = {k for k, v in done.items() if v["status"] in ("ok", "empty")}
    pending = work[~work.chunk_id.isin(settled)]
    print("tier '{}': {:,} chunks planned, {:,} already settled, {:,} to do"
          .format(tier, len(work), len(work) - len(pending), len(pending)))

    t0 = time.time()
    for n, row in enumerate(pending.itertuples(index=False), 1):
        codes = row.codes.split(",") if isinstance(row.codes, str) else []
        params = build_params(row.flow, row.month, fields[row.flow],
                              row.chapter, codes)
        df, status = fetch(row.flow, params)
        rec = {"chunk_id": row.chunk_id, "tier": tier, "flow": row.flow,
               "month": row.month, "chapter": row.chapter, "batch": row.batch,
               "status": status, "n_rows": 0,
               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "problems": ""}

        if df is not None:
            problems = validate(df, row.flow, row.chapter)
            rec["problems"] = ";".join(problems)
            rec["n_rows"] = len(df)
            path = RAW / tier / row.flow / row.month[:4]
            path.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path / "{}_{}_{}_b{}.parquet".format(
                row.flow, row.month, row.chapter, row.batch), index=False)
            if problems:
                print("  ! {} :: {}".format(row.chunk_id, rec["problems"]))
        elif status.startswith(("failed", "http", "non_json")):
            print("  x {} :: {}".format(row.chunk_id, status))

        append_manifest(rec)
        time.sleep(PAUSE + random.random() * JITTER)

        if n % 200 == 0:
            rate = n / (time.time() - t0)
            print("  {:,}/{:,}  {:.1f} chunks/s  eta {:.0f} min".format(
                n, len(pending), rate, (len(pending) - n) / rate / 60))

    print("done in {:.1f} min".format((time.time() - t0) / 60))


def consolidate():
    """Fold the per-chunk parquet files into one tidy long table per tier.
    Value columns arrive from the API as strings and are cast here, once."""
    num_cols = ["GEN_VAL_MO", "CON_VAL_MO", "ALL_VAL_MO", "GEN_QY1_MO", "QTY_1_MO",
                "GEN_CIF_MO", "CON_CIF_MO", "GEN_CHA_MO", "CON_CHA_MO",
                "AIR_VAL_MO", "AIR_WGT_MO", "AIR_CHA_MO",
                "VES_VAL_MO", "VES_WGT_MO", "VES_CHA_MO",
                "CAL_DUT_MO", "DUT_VAL_MO"]
    for tier in ("universe", "gold"):
        files = sorted((RAW / tier).rglob("*.parquet")) if (RAW / tier).exists() else []
        if not files:
            continue
        frames = []
        for fp in files:
            d = pd.read_parquet(fp)
            flow = fp.parent.parent.name
            d["flow"] = flow
            d["date"] = pd.to_datetime(fp.stem.split("_")[1] + "-01")  # flow_YYYY-MM_ch_bN
            d = d.rename(columns={"I_COMMODITY": "hs6", "E_COMMODITY": "hs6"})
            frames.append(d)
        out = pd.concat(frames, ignore_index=True)
        for c in num_cols:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        out["hs2"] = out["hs6"].astype(str).str[:2]
        dest = OUT / "us_trade_hs6_{}.parquet".format(tier)
        out.to_parquet(dest, index=False)
        print("{:<9} {:>12,} rows -> {} ({:.0f} MB)".format(
            tier, len(out), dest.name, dest.stat().st_size / 1e6))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["universe", "gold"])
    ap.add_argument("--consolidate", action="store_true")
    a = ap.parse_args()
    if a.consolidate:
        consolidate()
    elif a.tier:
        run(a.tier)
    else:
        ap.error("pass --tier universe|gold or --consolidate")
