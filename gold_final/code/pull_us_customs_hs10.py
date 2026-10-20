#!/usr/bin/env python3
"""
Raw US Census trade data for every HS10 line under 7108 and 7115, by partner,
monthly, Jan 2015 on. No classification, no conversion, no derived columns:
values are written exactly as Census returns them, under Census's own field
names.

Two outputs, because the two flows carry different fields:

  us_gold_hs10_imports_monthly.csv
  us_gold_hs10_exports_monthly.csv

WHAT IS PULLED. Every HS10 line Census reports under the two headings -
including the silver, platinum and mixed-metal lines and gold leaf - for every
partner. 7108 is gold unwrought or semimanufactured; 7115 is "other articles
of precious metal", where most of the 2024-25 bars were booked.

FIELDS, imports (HTS codes)
  I_COMMODITY, _SDESC, _LDESC   HS10 code, short and long description
  GEN_*                         general imports: everything entering US
                                territory, including into bonded warehouses
                                and foreign-trade zones
  CON_*                         imports for consumption: entries into US
                                customs territory for use. Differs from GEN
                                by warehouse/FTZ timing
  *_VAL_MO                      customs value, $
  *_CIF_MO                      CIF value, $ (customs value + charges)
  *_CHA_MO                      import charges, $: freight, insurance and
                                other costs to bring the goods to the US
  *_QY1_MO, *_QY2_MO            quantity 1 and 2, in UNIT_QY1 / UNIT_QY2
  *_QY1_MO_FLAG, _QY2_MO_FLAG   true-zero flags for the quantities
  DUT_VAL_MO                    dutiable value, $ (consumption basis)
  CAL_DUT_MO                    calculated duty, $ (consumption basis)
  AIR_/VES_/CNT_ VAL, WGT, CHA  value, shipping weight (kg) and charges by
                                mode: air, vessel, containerized vessel.
                                Shipping weight is the gross weight of the
                                shipment, packaging included
  CC_MO                         card count: number of entry records

FIELDS, exports (Schedule B codes)
  E_COMMODITY, _SDESC, _LDESC   HS10 code, short and long description
  DF                            "1" domestic, "2" foreign (re-exports),
                                "-" total. Every cell comes back three times;
                                never sum across DF
  ALL_VAL_MO                    FAS value, $
  QTY_1_MO, QTY_2_MO            quantity 1 and 2, in UNIT_QY1 / UNIT_QY2
  QTY_1_MO_FLAG, QTY_2_MO_FLAG  true-zero flags
  AIR_/VES_/CNT_ VAL, WGT       value and shipping weight (kg) by mode
  CC_MO                         card count

BOTH FLOWS
  CTY_CODE, CTY_NAME            partner. "-" is the all-countries total
  SUMMARY_LVL                   "DET" for a country, "CGP" for a country
                                grouping (EU, OPEC, "1XXX" North America...).
                                Never sum over all rows
  time                          YYYY-MM

UNITS ARE PER LINE. UNIT_QY1 is GM (gross grams), CGM (grams of gold
content), or CM2 (square centimetres, gold leaf), and import and export codes
for the same goods do not always use the same unit. "-" means no unit.

Idempotent: an existing output is left alone unless --force is passed.
Requests are spaced deliberately.

Needs CENSUS_API_KEY, in the repo .env or the environment.

Run from anywhere:
    python gold_final/code/pull_us_customs_hs10.py
    python gold_final/code/pull_us_customs_hs10.py --force
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS BLOCK IF YOU MOVE THE PROJECT
# ============================================================================
REPO_ROOT = ""                      # blank = infer from this file's location
ENV_FILE = ".env"                   # relative to the root, or an absolute path
OUT_DIR = "gold_final/data/raw"     # relative to the root, or an absolute path
# ============================================================================

HS_GOLD = ("7108", "7115")
FROM, TO = "2015-01", None          # None = as recent as Census has

CHUNK_MONTHS = 12
REQUEST_SPACING_S = 2.0             # deliberate, not maximal
TIMEOUT_S = 300
RETRIES = 3

import argparse
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]


def _at(value: str) -> Path:
    """Absolute paths win, ~ expands, anything else is relative to the root.
    Matches pull_us_customs.py."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


OUT = _at(OUT_DIR)
BASE = "https://api.census.gov/data/timeseries/intltrade"
UA = {"User-Agent": "academic research (gold trade deconvolution)"}

FLOWS = {
    "imports": {
        "code": "I_COMMODITY",
        "out": "us_gold_hs10_imports_monthly.csv",
        "fields": [
            "CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
            "I_COMMODITY", "I_COMMODITY_SDESC", "I_COMMODITY_LDESC",
            "UNIT_QY1", "UNIT_QY2",
            "GEN_VAL_MO", "GEN_CIF_MO", "GEN_CHA_MO",
            "GEN_QY1_MO", "GEN_QY1_MO_FLAG", "GEN_QY2_MO", "GEN_QY2_MO_FLAG",
            "CON_VAL_MO", "CON_CIF_MO", "CON_CHA_MO",
            "CON_QY1_MO", "CON_QY1_MO_FLAG", "CON_QY2_MO", "CON_QY2_MO_FLAG",
            "DUT_VAL_MO", "CAL_DUT_MO",
            "AIR_VAL_MO", "AIR_WGT_MO", "AIR_CHA_MO",
            "VES_VAL_MO", "VES_WGT_MO", "VES_CHA_MO",
            "CNT_VAL_MO", "CNT_WGT_MO", "CNT_CHA_MO",
            "CC_MO",
        ],
    },
    "exports": {
        "code": "E_COMMODITY",
        "out": "us_gold_hs10_exports_monthly.csv",
        "fields": [
            "CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
            "E_COMMODITY", "E_COMMODITY_SDESC", "E_COMMODITY_LDESC",
            "DF",
            "UNIT_QY1", "UNIT_QY2",
            "ALL_VAL_MO",
            "QTY_1_MO", "QTY_1_MO_FLAG", "QTY_2_MO", "QTY_2_MO_FLAG",
            "AIR_VAL_MO", "AIR_WGT_MO",
            "VES_VAL_MO", "VES_WGT_MO",
            "CNT_VAL_MO", "CNT_WGT_MO",
            "CC_MO",
        ],
    },
}


def api_key() -> str:
    env = _at(ENV_FILE)
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CENSUS_API_KEY=") and len(line) > 15:
                return line.split("=", 1)[1].strip()
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if key:
        return key
    raise SystemExit(
        f"no CENSUS_API_KEY found.\n"
        f"  add a line   CENSUS_API_KEY=<your key>   to {env}\n"
        f"  or export it in the environment\n"
        f"  free signup: https://api.census.gov/data/key_signup.html")


def months(a: str, b: str) -> list[str]:
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    out = []
    while (ya, ma) <= (yb, mb):
        out.append(f"{ya}-{ma:02d}")
        ma += 1
        if ma == 13:
            ya, ma = ya + 1, 1
    return out


def chunks(lo: str, hi: str, n: int) -> list[tuple[str, str]]:
    ms = months(lo, hi)
    return [(ms[i], ms[min(i + n, len(ms)) - 1]) for i in range(0, len(ms), n)]


def get(flow: str, fields: list[str], lo: str, hi: str, key: str,
        commodity: str, level: str = "HS10") -> list[list[str]]:
    """One Census call over a month range. Returns rows including the header.
    A range with no data comes back as HTTP 204 and an empty body; that is
    returned as a header-only result rather than treated as an error."""
    params = {
        "get": ",".join(fields),
        "COMM_LVL": level,
        FLOWS[flow]["code"]: commodity,
        "time": f"from {lo} to {hi}",
        "key": key,
    }
    url = f"{BASE}/{flow}/hs?" + urllib.parse.urlencode(params)
    for attempt in range(1, RETRIES + 1):
        time.sleep(REQUEST_SPACING_S)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read()
            if not body.strip():
                return [fields + ["time"]]
            if not body.lstrip().startswith(b"["):
                raise RuntimeError("not JSON - the key was probably rejected")
            return json.loads(body)
        except Exception as e:
            if attempt == RETRIES:
                raise RuntimeError(f"{flow} {commodity} {lo}..{hi}: {e}") from e
            wait = 5 * attempt
            print(f"      retry {attempt}/{RETRIES - 1} in {wait}s ({e})",
                  flush=True)
            time.sleep(wait)
    return []


def latest_month(key: str) -> str:
    rows = get("imports", ["I_COMMODITY", "GEN_VAL_MO"], "2025-01", "2027-12",
               key, commodity="7108", level="HS4")
    t = rows[0].index("time")
    return max(r[t] for r in rows[1:])


def pull(flow: str, key: str, lo: str, hi: str) -> list[dict]:
    """Every HS10 line under each heading, every partner, raw. Census echoes
    filter fields back as extra columns; only the first occurrence of each
    requested field is kept."""
    fields = FLOWS[flow]["fields"]
    out = []
    for hs in HS_GOLD:
        for a, b in chunks(lo, hi, CHUNK_MONTHS):
            print(f"   {flow:7s} {hs}*  {a}..{b}", flush=True)
            rows = get(flow, fields, a, b, key, commodity=f"{hs}*")
            h = rows[0]
            ix = {f: h.index(f) for f in fields + ["time"]}
            for r in rows[1:]:
                out.append({f: r[ix[f]] for f in ["time"] + fields})
    return out


def write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"   wrote {path.relative_to(ROOT)}  ({len(rows):,} rows)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="refetch even if the output already exists")
    args = ap.parse_args()
    os.chdir(ROOT)

    print("=" * 74)
    print("US CENSUS HS10 PULL - 7108 AND 7115, RAW")
    print("=" * 74)
    key = None
    hi = TO
    for flow, spec in FLOWS.items():
        path = OUT / spec["out"]
        if path.exists() and not args.force:
            print(f"   {spec['out']} already present - skipping "
                  f"(--force to refetch)")
            continue
        key = key or api_key()
        hi = hi or latest_month(key)
        print(f"   {flow}  {FROM} .. {hi}")
        write(pull(flow, key, FROM, hi), path)


if __name__ == "__main__":
    main()
