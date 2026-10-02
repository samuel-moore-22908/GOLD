#!/usr/bin/env python3
"""
Pull everything the four figures need from US Census trade statistics.

Three outputs, one API, one script:

  us_hs4_universe_monthly.csv   every HS4 heading, all partners aggregated,
                                monthly. Figure 1 needs it to rank gold against
                                the rest of the tariff-window trade.
  us_gold_monthly.csv           HS 7108 and 7115 only, all partners, monthly,
                                back to 2015. Figures 2, 3 and 4 run on it.
  us_gold_partner_monthly.csv   the same two headings split by partner, for the
                                right-hand panel of figure 1.
  us_trade_balance_monthly.csv  the FT-900 goods-and-services balance, which
                                Census and BEA publish jointly. Figure 4 sets
                                the gold against it. Taken from FRED's keyless
                                CSV endpoint because Stata will not do HTTPS
                                here - it hangs rather than failing - so every
                                series a do-file reads has to be on disk first.

BOTH HEADINGS, ALWAYS. 7108 is gold unwrought; 7115 is "other articles of
precious metal". Over the winter of 2024-25 most of the bars went into the
United States under 7115, and BEA reclassifies line 7115900530 as nonmonetary
gold on a balance-of-payments basis. A pull of 7108 alone misses the episode.

VALUE ONLY. Census reports US trade in dollars; the quantity fields for these
headings are empty or in units that are not comparable across lines. Tonnage is
derived downstream by dividing by the LBMA benchmark, and is tagged as derived
wherever it appears.

Idempotent. A file that already exists and covers the requested window is left
alone; pass --force to refetch. Requests are spaced deliberately - this is a
free public API and there is no reason to hammer it.

Needs CENSUS_API_KEY, in the repo .env or the environment. Get one free at
https://api.census.gov/data/key_signup.html

Run from anywhere:
    python gold_final/code/pull_us_customs.py
    python gold_final/code/pull_us_customs.py --force
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS BLOCK IF YOU MOVE THE PROJECT
# ============================================================================
REPO_ROOT = ""                      # blank = infer from this file's location
ENV_FILE = ".env"                   # relative to the root, or an absolute path
OUT_DIR = "gold_final/data/raw"     # relative to the root, or an absolute path
# ============================================================================

# HS 7108 is gold unwrought, 7115 is where the bars were booked in the episode.
HS_GOLD = ("7108", "7115")

# Gold goes back as far as the figures need a pre-trend. The universe and the
# partner split only cover the tariff window, because that is all figure 1 uses
# and the payload is 50x larger.
GOLD_FROM, GOLD_TO = "2015-01", None        # None = as recent as Census has
WINDOW_FROM, WINDOW_TO = "2023-11", None

CHUNK_MONTHS = 24          # months per request; the API takes a range
REQUEST_SPACING_S = 2.0    # deliberate, not maximal
TIMEOUT_S = 180
RETRIES = 3

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]


def _at(value: str) -> Path:
    """Resolve one of the configured paths above.

    An absolute path wins outright and a leading ~ expands; anything else is
    taken relative to the repo root. So OUT_DIR and ENV_FILE can both point
    outside the repo - at a drive you have rights to, a folder outside a synced
    directory - without touching anything else. Matches pull_databento.py.
    """
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


OUT = _at(OUT_DIR)
BASE = "https://api.census.gov/data/timeseries/intltrade"
UA = {"User-Agent": "academic research (gold trade deconvolution)"}

# The two flows name their commodity and value fields differently, and the
# values are not interchangeable: imports are customs value, exports are FAS
# value including re-exports.
FLOWS = {
    "imports": {"code": "I_COMMODITY", "value": "GEN_VAL_MO"},
    "exports": {"code": "E_COMMODITY", "value": "ALL_VAL_MO"},
}


def api_key() -> str:
    """CENSUS_API_KEY from the repo .env, falling back to the environment.

    Never printed. If it is missing, say exactly where to put it rather than
    failing on an HTTP redirect to a 'Missing Key' page, which is what the API
    does and which is not obvious from the traceback.
    """
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
        commodity: str | None = None) -> list[list[str]]:
    """One Census call over a month range. Returns rows including the header."""
    spec = FLOWS[flow]
    params = {
        "get": ",".join(fields),
        "COMM_LVL": "HS4",
        "time": f"from {lo} to {hi}",
        "key": key,
    }
    if commodity:
        params[spec["code"]] = commodity
    url = f"{BASE}/{flow}/hs?" + urllib.parse.urlencode(params)
    for attempt in range(1, RETRIES + 1):
        time.sleep(REQUEST_SPACING_S)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read()
            if not body.lstrip().startswith(b"["):
                raise RuntimeError("not JSON - the key was probably rejected")
            return json.loads(body)
        except Exception as e:
            if attempt == RETRIES:
                raise RuntimeError(f"{flow} {lo}..{hi}: {e}") from e
            wait = 5 * attempt
            print(f"      retry {attempt}/{RETRIES - 1} in {wait}s ({e})",
                  flush=True)
            time.sleep(wait)
    return []


def col(header: list[str], name: str) -> int:
    """Index of a column. Census repeats the commodity field in the header when
    it is also used as a filter, so take the first match and move on."""
    return header.index(name)


def latest_month(key: str) -> str:
    """The most recent month Census has published, found by asking for a wide
    range on a cheap query and taking the maximum it returns."""
    rows = get("imports", ["I_COMMODITY", "GEN_VAL_MO"], "2025-01", "2027-12",
               key, commodity="7108")
    h = rows[0]
    t = col(h, "time")
    newest = max(r[t] for r in rows[1:])
    return newest


def pull_gold(key: str, lo: str, hi: str) -> list[dict]:
    out = []
    for flow, spec in FLOWS.items():
        for hs in HS_GOLD:
            for a, b in chunks(lo, hi, CHUNK_MONTHS):
                print(f"   gold  {flow:7s} {hs}  {a}..{b}", flush=True)
                rows = get(flow, [spec["code"], spec["value"]], a, b, key,
                           commodity=hs)
                h = rows[0]
                iv, it = col(h, spec["value"]), col(h, "time")
                for r in rows[1:]:
                    out.append({"date": f"{r[it]}-01", "flow": flow,
                                "hs4": hs, "value_usd": r[iv] or 0})
    return out


def pull_universe(key: str, lo: str, hi: str) -> list[dict]:
    out = []
    for flow, spec in FLOWS.items():
        for a, b in chunks(lo, hi, 6):     # smaller chunks: ~1200 rows a month
            print(f"   univ  {flow:7s}      {a}..{b}", flush=True)
            rows = get(flow, [spec["code"], spec["value"]], a, b, key)
            h = rows[0]
            ic, iv, it = col(h, spec["code"]), col(h, spec["value"]), col(h, "time")
            for r in rows[1:]:
                out.append({"date": f"{r[it]}-01", "flow": flow,
                            "hs4": r[ic], "value_usd": r[iv] or 0})
    return out


def pull_partners(key: str, lo: str, hi: str) -> list[dict]:
    out = []
    for flow, spec in FLOWS.items():
        for hs in HS_GOLD:
            for a, b in chunks(lo, hi, 12):
                print(f"   part  {flow:7s} {hs}  {a}..{b}", flush=True)
                rows = get(flow, ["CTY_CODE", "CTY_NAME", spec["value"]],
                           a, b, key, commodity=hs)
                h = rows[0]
                ic, inm = col(h, "CTY_CODE"), col(h, "CTY_NAME")
                iv, it = col(h, spec["value"]), col(h, "time")
                for r in rows[1:]:
                    out.append({"date": f"{r[it]}-01", "cty_code": r[ic],
                                "cty_name": r[inm], "flow": flow, "hs4": hs,
                                "value_usd": r[iv] or 0})
    return out


def pull_balance(key: str, lo: str, hi: str) -> list[dict]:
    """The FT-900 goods-and-services balance, monthly, $ millions, negative is
    a deficit. `key`, `lo` and `hi` are unused - the signature matches the
    Census jobs so the driver loop stays one shape."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOPGSTB"
    print("   bal   BOPGSTB from FRED", flush=True)
    time.sleep(REQUEST_SPACING_S)
    req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read().decode()
    except Exception:
        import subprocess
        body = subprocess.run(["curl", "-sS", "-m", "120", "-A",
                               "GOLD-research/1.0", url],
                              check=True, capture_output=True).stdout.decode()
    out = []
    for line in body.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2 or not parts[1].strip() or parts[1].strip() == ".":
            continue
        out.append({"date": parts[0].strip(), "balance_usdmn": parts[1].strip()})
    return out


# FRED series the deflator figure needs. Stata cannot fetch them - it hangs on
# HTTPS rather than failing - so they are pulled here with everything else.
#   IR       BLS import price index, all commodities
#   IQ       BLS export price index, all commodities
#   BOPGIMP  goods imports, BOP basis, $mn   (the denominator for gold's share)
#   BOPGEXP  goods exports, BOP basis, $mn
#   B021RG3Q086SBEA  NIPA chain-type price index for imports of GOODS,
#                    quarterly. Gold-free by construction, because BEA removes
#                    nonmonetary gold from the national accounts.
DEFLATOR_SERIES = ("IR", "IQ", "BOPGIMP", "BOPGEXP", "B021RG3Q086SBEA")


def _fred(series_id: str) -> dict[str, str]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    time.sleep(REQUEST_SPACING_S)
    req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read().decode()
    except Exception:
        import subprocess
        body = subprocess.run(["curl", "-sS", "-m", "120", "-A",
                               "GOLD-research/1.0", url],
                              check=True, capture_output=True).stdout.decode()
    out = {}
    for line in body.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2 and parts[1].strip() and parts[1].strip() != ".":
            out[parts[0].strip()] = parts[1].strip()
    return out


def pull_deflator_inputs(key: str, lo: str, hi: str) -> list[dict]:
    """The price indexes and goods totals the deflator figure runs on. `key`,
    `lo` and `hi` are unused; the signature matches the Census jobs so the
    driver loop stays one shape."""
    cols = {}
    for sid in DEFLATOR_SERIES:
        print(f"   defl  {sid} from FRED", flush=True)
        cols[sid] = _fred(sid)
    dates = sorted(set().union(*(set(v) for v in cols.values())))
    rows = []
    for dt in dates:
        row = {"date": dt}
        for sid in DEFLATOR_SERIES:
            row[sid.lower()] = cols[sid].get(dt, "")
        rows.append(row)
    return rows


# ---------------------------------------------------------------- BLS MXPI
# The published price indexes themselves, from the BLS flat files rather than
# FRED, because FRED does not carry the component series.
#
# BLS calculates the import and export price indexes with a Lowe (modified
# fixed-quantity Laspeyres) formula, chained monthly, and REWEIGHTS EVERY
# JANUARY from Census annual trade values on a TWO-YEAR LAG - their own
# worked example is that the 2025 indexes carry 2023 weights. That rule is
# what makes the weight computable here instead of assumed.
#
#   EIUIR        import price index, BEA end use, all commodities
#   EIUIQ        export price index, BEA end use, all commodities
#   EIUIR14270   import price index, BEA end use 14270, NONMONETARY GOLD
#   EIUIQ12260   export price index, BEA end use 12260, NONMONETARY GOLD
#
# The two gold series settle the coverage question: gold is sampled on both
# sides of the account, so whatever goes wrong is about weight, not blindness.
BLS_BASE = "https://download.bls.gov/pub/time.series/ei"
BLS_FILES = {
    "ei.data.01.BEAImport": ("EIUIR", "EIUIR14270"),
    "ei.data.02.BEAExport": ("EIUIQ", "EIUIQ12260"),
}
# BLS blocks requests that do not identify a caller.
BLS_UA = "GOLD-research/1.0 (samuel.moore.econresearch@gmail.com)"


def _bls_file(name: str) -> str:
    url = f"{BLS_BASE}/{name}"
    time.sleep(REQUEST_SPACING_S)
    req = urllib.request.Request(url, headers={"User-Agent": BLS_UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        import subprocess
        return subprocess.run(["curl", "-sS", "-m", "180", "-A", BLS_UA, url],
                              check=True, capture_output=True).stdout.decode(
                                  "utf-8", "replace")


def pull_mxpi(key: str, lo: str, hi: str) -> list[dict]:
    """BLS import/export price indexes: the all-commodities aggregate and the
    nonmonetary gold component for each side. `key`, `lo`, `hi` are unused;
    the signature matches the Census jobs so the driver loop stays one shape."""
    cols: dict[str, dict[str, str]] = {}
    for name, wanted in BLS_FILES.items():
        print(f"   mxpi  {name} from BLS ({', '.join(wanted)})", flush=True)
        body = _bls_file(name)
        for sid in wanted:
            cols[sid] = {}
        for line in body.splitlines()[1:]:
            f = line.split("	")
            if len(f) < 4:
                continue
            sid, year, period, value = (x.strip() for x in f[:4])
            if sid not in wanted or not period.startswith("M") or period == "M13":
                continue
            if not value or value == "-":
                continue
            cols[sid][f"{year}-{period[1:]}-01"] = value

    dates = sorted(set().union(*(set(v) for v in cols.values())))
    order = [s for w in BLS_FILES.values() for s in w]
    rows = []
    for dt in dates:
        row = {"date": dt}
        for sid in order:
            row[sid.lower()] = cols[sid].get(dt, "")
        rows.append(row)
    return rows


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
    key = api_key()

    print("=" * 74)
    print("US CENSUS TRADE PULL")
    print("=" * 74)
    latest = latest_month(key)
    gold_to = GOLD_TO or latest
    window_to = WINDOW_TO or latest
    print(f"   Census has published through {latest}.")
    print(f"   gold      {GOLD_FROM} .. {gold_to}")
    print(f"   universe  {WINDOW_FROM} .. {window_to}")
    print(f"   partners  {WINDOW_FROM} .. {window_to}")
    print()

    jobs = [
        ("us_gold_monthly.csv", pull_gold, GOLD_FROM, gold_to),
        ("us_hs4_universe_monthly.csv", pull_universe, WINDOW_FROM, window_to),
        ("us_gold_partner_monthly.csv", pull_partners, WINDOW_FROM, window_to),
        ("us_trade_balance_monthly.csv", pull_balance, GOLD_FROM, gold_to),
        ("us_deflator_inputs_monthly.csv", pull_deflator_inputs, GOLD_FROM, gold_to),
        ("us_mxpi_monthly.csv", pull_mxpi, GOLD_FROM, gold_to),
    ]
    for name, fn, lo, hi in jobs:
        path = OUT / name
        if path.exists() and not args.force:
            print(f"   {name} already present - skipping (--force to refetch)")
            continue
        write(fn(key, lo, hi), path)

    print()
    print("   done. Nothing here is committed: the repo gitignores *.csv and")
    print("   these regenerate from this script.")


if __name__ == "__main__":
    main()
