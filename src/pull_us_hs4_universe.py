"""
Pull the full universe of US trade at the HS4 level from the Census API.

The existing processed pulls cover only HS 7108/7115 and only four partner
countries, which cannot support a cross-commodity comparison. This pulls every
HS4 heading, monthly, both flows, country-aggregated.

Country dimension: omitting CTY_CODE from `get` returns the all-countries
total as a single row per commodity. Including it returns one row per partner
plus a "-" total row, which is 60x the payload for no gain here.

Value fields differ by flow and are not interchangeable:
  imports  GEN_VAL_MO  general imports, customs value
  exports  ALL_VAL_MO  total exports (domestic + foreign/re-exports), FAS value

Quantity is reported in the first quantity unit (UNIT_QY1), which varies by
heading - kilograms for some, number/dozens/litres for others. It is only
comparable within a heading, never across them, and is frequently zero.

Input:  Census API (needs CENSUS_API_KEY in the environment)
Output: data/processed/us_hs4_universe_monthly.csv
"""
import csv
import os
import sys
import time

import requests

OUT = "data/processed/us_hs4_universe_monthly.csv"
UA = {"User-Agent": "academic research (samuel.moore.econresearch@gmail.com)"}

# Jan-Apr in both years: the tariff-scare window and the same months a year
# earlier, since commodity trade is strongly seasonal and an adjacent-quarter
# baseline would confound season with treatment.
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in (1, 2, 3, 4)]

SPEC = {
    "imports": ("I_COMMODITY", "I_COMMODITY,GEN_VAL_MO,GEN_QY1_MO,UNIT_QY1"),
    "exports": ("E_COMMODITY", "E_COMMODITY,ALL_VAL_MO,QTY_1_MO,UNIT_QY1"),
}


def fetch(flow, month, key, tries=3):
    code_col, getv = SPEC[flow]
    url = f"https://api.census.gov/data/timeseries/intltrade/{flow}/hs"
    params = {"get": getv, "COMM_LVL": "HS4", "time": month, "key": key}
    for attempt in range(tries):
        try:
            # Exports routinely take 45s+; a short timeout reads as a failure
            # when the query is merely slow.
            r = requests.get(url, params=params, headers=UA, timeout=300)
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                return r.json()
            print(f"    {flow} {month}: HTTP {r.status_code} "
                  f"{r.text[:90]!r}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    {flow} {month}: {type(e).__name__} "
                  f"(attempt {attempt + 1})", flush=True)
        time.sleep(5 * (attempt + 1))
    return None


def main():
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        print("error: CENSUS_API_KEY is not set", file=sys.stderr)
        return 2

    rows = []
    for month in MONTHS:
        for flow in SPEC:
            t = time.time()
            j = fetch(flow, month, key)
            if not j:
                print(f"  {flow} {month}: FAILED", flush=True)
                continue
            head = j[0]
            ix = {name: i for i, name in enumerate(head)}
            code_col = SPEC[flow][0]
            val_col = "GEN_VAL_MO" if flow == "imports" else "ALL_VAL_MO"
            qty_col = "GEN_QY1_MO" if flow == "imports" else "QTY_1_MO"
            n = 0
            for r in j[1:]:
                code = r[ix[code_col]]
                # Chapters 98/99 are special classification provisions (low-value
                # shipments, returned goods, repairs) rather than commodities;
                # they would otherwise rank among the largest "headings".
                if not code or not code.isdigit() or code[:2] in ("98", "99"):
                    continue
                try:
                    value = int(r[ix[val_col]])
                except (ValueError, TypeError):
                    continue
                try:
                    qty = int(r[ix[qty_col]])
                except (ValueError, TypeError):
                    qty = 0
                rows.append({
                    "date": month + "-01", "flow": flow, "hs4": code,
                    "value_usd": value, "qty": qty,
                    "unit": r[ix["UNIT_QY1"]] if "UNIT_QY1" in ix else "",
                })
                n += 1
            print(f"  {flow} {month}: {n} rows in {time.time() - t:.0f}s",
                  flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "flow", "hs4", "value_usd",
                                          "qty", "unit"])
        w.writeheader()
        w.writerows(rows)
    codes = {r["hs4"] for r in rows}
    print(f"\nwrote {OUT}: {len(rows)} rows, {len(codes)} distinct HS4 headings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
