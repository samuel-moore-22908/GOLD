"""
Pull USGS's Monthly Mineral Industry Surveys (MIS) for gold and build a
tidy monthly panel: US mine production by state, gold price (Engelhard/S&P
Global Platts Metals Week quotes - an independent cross-check on the LBMA
fix), and US imports/exports totals (USGS's own restatement of Census
data, but with quantity in kg, which our direct US Census pull lacks).

Access: `usgs.gov/centers/national-minerals-information-center/gold-
statistics-and-information` needs a browser User-Agent (403 without one,
same as BAZG's CloudFront check) but the actual files sit on an
unprotected public S3 bucket at a predictable URL:
  https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/
  s3fs-public/media/files/mis-{YYYYMM}-gold.xlsx
("palladium" in the path is just USGS's S3 asset-bucket naming, not a
commodity filter - confirmed the same path serves gold files fine.)

Coverage: confirmed live back to 2022-01; 2021 and earlier 403 at this
exact path (older months may only exist as PDF, not investigated further).
Each month's workbook also restates the full prior calendar year, so
pulling monthly files from 2022-01 onward gives full coverage from 2021.

Scope: this script extracts the monthly aggregate series (T1 production,
T2 price, T3/T4 import/export TOTALS only). USGS also publishes a
per-country import/export breakdown, but only for the most-recent month in
each file - extracting that fully would need one more pass and isn't done
here; noted as a possible extension.

Output: data/processed/usgs_gold_monthly.csv
Raw files cached under data/raw/usgs/.
"""
import os
import re

import pandas as pd
import requests

BASE = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/files"
RAW_DIR = "data/raw/usgs"
OUT = "data/processed/usgs_gold_monthly.csv"

START_YEAR, START_MONTH = 2022, 1

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"]
)}


def month_range(start_year, start_month):
    y, m = start_year, start_month
    today = pd.Timestamp.today()
    while (y, m) <= (today.year, today.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def fetch(year, month):
    ym = f"{year}{month:02d}"
    cache_path = f"{RAW_DIR}/mis-{ym}-gold.xlsx"
    if os.path.exists(cache_path):
        return cache_path
    url = f"{BASE}/mis-{ym}-gold.xlsx"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        return None
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(r.content)
    return cache_path


def parse_period_rows(df, value_cols):
    """Walk a USGS table: rows are either a bare year label, a month name,
    or a 'January-December' annual total (skipped). Returns {date: {col: val}}."""
    out = {}
    year = None
    for _, row in df.iterrows():
        period = row[0]
        if pd.isna(period):
            continue
        period = str(period).strip()
        m = re.match(r"^(\d{4})$", period)
        if m:
            year = int(m.group(1))
            continue
        m = re.match(r"^([A-Za-z]+)(?:,\s*(\d{4}))?$", period)
        if m and m.group(1) in MONTHS:
            month = MONTHS[m.group(1)]
            yr = int(m.group(2)) if m.group(2) else year
            if yr is None:
                continue
            out[pd.Timestamp(year=yr, month=month, day=1)] = {c: row[i] for c, i in value_cols.items()}
    return out


def parse_t1(path):
    d = pd.read_excel(path, sheet_name="T1", header=None)
    rows = parse_period_rows(d, {"alaska_kg": 1, "nevada_kg": 2, "other_states_kg": 3, "total_production_kg": 4})
    return rows


def parse_t2(path):
    d = pd.read_excel(path, sheet_name="T2", header=None)
    rows = parse_period_rows(d, {"price_low_usd_oz": 1, "price_high_usd_oz": 3, "price_avg_usd_oz": 5})
    return rows


def parse_trade_total(path, sheet):
    d = pd.read_excel(path, sheet_name=sheet, header=None)
    # "Total3" category sits at columns 7 (Quantity) and 8 (Value, thousand $)
    rows = parse_period_rows(d, {"total_qty_kg": 7, "total_value_kusd": 8})
    return rows


def main():
    all_data = {}
    fetched, missing = 0, 0
    for year, month in month_range(START_YEAR, START_MONTH):
        path = fetch(year, month)
        if path is None:
            missing += 1
            continue
        fetched += 1
        try:
            t1 = parse_t1(path)
            t2 = parse_t2(path)
            t3 = parse_trade_total(path, "T3")
            t4 = parse_trade_total(path, "T4")
        except Exception as e:
            print(f"  {year}-{month:02d}: parse error {e}")
            continue
        for date in set(t1) | set(t2) | set(t3) | set(t4):
            row = all_data.setdefault(date, {})
            row.update(t1.get(date, {}))
            row.update(t2.get(date, {}))
            row.update({f"import_{k}": v for k, v in t3.get(date, {}).items()})
            row.update({f"export_{k}": v for k, v in t4.get(date, {}).items()})

    print(f"Fetched {fetched} monthly reports, {missing} not available at this path")

    out = pd.DataFrame.from_dict(all_data, orient="index").sort_index()
    out.index.name = "date"
    out = out.reset_index()
    out["source"] = "USGS Monthly Mineral Industry Surveys (S3, no auth)"
    out["quality"] = "reported"
    out["note"] = (
        "Later-published reports overwrite earlier preliminary figures for "
        "the same month where both exist (processed oldest-to-newest). "
        "import_*/export_* are USGS's Total3 category restatement of "
        "Census data, not the full category breakdown available in the "
        "source files. price_* is Engelhard/S&P Global Platts Metals Week, "
        "not the LBMA fix - independent cross-check series."
    )
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")
    print(f"Date range: {out.date.min()} to {out.date.max()}")
    print(out.tail(6).to_string())


if __name__ == "__main__":
    main()
