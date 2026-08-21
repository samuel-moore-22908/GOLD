"""
Pull USGS's deep historical gold series: Data Series 140 (US production/
trade, annual, 1900-2022, one static file) and the Minerals Yearbook's
world mine production by country table (annual, ~2006-2022, one file per
year with a 5-year rolling window per file).

Both confirmed live on the same public S3 bucket / usgs.gov media pattern
already used in pull_usgs_gold_series.py - needs a browser User-Agent to
resolve the media landing page URL to its real S3 file, but the S3 files
themselves are unprotected.

Output: data/processed/usgs_ds140_gold_annual.csv (US + world aggregate, 1900-2022)
        data/processed/usgs_myb_world_production_by_country.csv (by-country, ~2002-2022)
"""
import os
import re

import pandas as pd
import requests

RAW_DIR = "data/raw/usgs_historical"

DS140_URL = "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/files/ds140-gold-2022.xlsx"

# Two different hosting patterns across years - found by resolving the
# gold-statistics-and-information page's Minerals Yearbook links.
MYB_URLS = {
    2006: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2006-gold.xls",
    2007: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2007-gold.xls",
    2008: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2008-gold.xls",
    2009: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2009-gold.xls",
    2010: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2010-gold.xls",
    2011: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2011-gold.xls",
    2012: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2012-gold.xls",
    2013: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2013-gold.xls",
    2014: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2014-gold.xls",
    2015: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/mineral-pubs/gold/myb1-2015-gold.xls",
    2016: "https://d9-wret.s3-us-west-2.amazonaws.com/assets/palladium/production/atoms/files/myb1-2016-gold.xlsx",
    2017: "https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/atoms/files/myb1-2017-gold.xls",
    2018: "https://pubs.usgs.gov/myb/vol1/2018/myb1-2018-gold.xlsx",
    2019: "https://pubs.usgs.gov/myb/vol1/2019/myb1-2019-gold.xlsx",
    2020: "https://pubs.usgs.gov/myb/vol1/2020/myb1-2020-gold.xlsx",
    2021: "https://pubs.usgs.gov/myb/vol1/2021/myb1-2021-gold.xlsx",
    2022: "https://pubs.usgs.gov/myb/vol1/2022/myb1-2022-gold.xlsx",
}


def pull_ds140():
    os.makedirs(RAW_DIR, exist_ok=True)
    path = f"{RAW_DIR}/ds140-gold.xlsx"
    r = requests.get(DS140_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    open(path, "wb").write(r.content)
    d = pd.read_excel(path, sheet_name="Gold", header=None)
    header = ["year", "us_primary_production_t", "us_secondary_production_t", "us_imports_t",
              "us_exports_t", "us_reported_consumption_t", "unit_value_usd_per_t",
              "unit_value_1998usd_per_t", "world_production_t"]
    d = d.iloc[5:].copy()
    d.columns = header[: d.shape[1]]
    d = d[pd.to_numeric(d["year"], errors="coerce").notna()]
    d["year"] = d["year"].astype(int)
    d["source"] = "USGS Data Series 140"
    d["quality"] = "reported"
    return d


def pull_myb_world_production():
    rows = []
    for pub_year, url in MYB_URLS.items():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  {pub_year}: skipped ({e})")
            continue
        ext = "xlsx" if url.endswith("xlsx") else "xls"
        os.makedirs(RAW_DIR, exist_ok=True)
        path = f"{RAW_DIR}/myb-{pub_year}-gold.{ext}"
        open(path, "wb").write(r.content)
        try:
            d = pd.read_excel(path, sheet_name="T8", header=None)
        except Exception as e:
            print(f"  {pub_year}: T8 parse failed ({e})")
            continue

        # Find the header row: first column is a "Country or locality..." label,
        # year values sit at even column indices from 2 onward.
        header_row = None
        for i in range(min(10, len(d))):
            if str(d.iloc[i, 0]).lower().startswith("country"):
                header_row = i
                break
        if header_row is None:
            continue
        year_cols = {}
        for c in range(2, d.shape[1], 2):
            val = d.iloc[header_row, c]
            if pd.notna(val):
                try:
                    year_cols[int(val)] = c
                except (TypeError, ValueError):
                    pass

        for i in range(header_row + 1, len(d)):
            country = d.iloc[i, 0]
            if pd.isna(country) or not isinstance(country, str):
                continue
            country_clean = re.sub(r"\d+$", "", country).strip().rstrip("e:")
            for year, col in year_cols.items():
                val = d.iloc[i, col]
                if pd.isna(val) or not isinstance(val, (int, float)):
                    continue
                rows.append({"year": year, "country": country_clean, "mine_production_kg": val, "myb_edition": pub_year})
        print(f"  {pub_year}: ok, years {sorted(year_cols)}")

    d = pd.DataFrame(rows)
    # Later editions overwrite earlier preliminary figures for the same
    # (year, country) - keep the row from the most recent edition.
    d = d.sort_values("myb_edition").drop_duplicates(subset=["year", "country"], keep="last")
    d["source"] = "USGS Minerals Yearbook, Table 8 (World Mine Production)"
    d["quality"] = "reported"
    return d


def main():
    print("Pulling Data Series 140 ...")
    ds140 = pull_ds140()
    ds140.to_csv("data/processed/usgs_ds140_gold_annual.csv", index=False)
    print(f"  wrote {len(ds140)} rows, {ds140.year.min()}-{ds140.year.max()}")

    print("Pulling Minerals Yearbook world production by country ...")
    myb = pull_myb_world_production()
    myb.to_csv("data/processed/usgs_myb_world_production_by_country.csv", index=False)
    print(f"  wrote {len(myb)} rows, {myb.year.min()}-{myb.year.max()}, {myb.country.nunique()} countries")

    print("\nOur five countries, most recent year available:")
    focus = myb[myb.country.isin(["United States", "United Kingdom", "Switzerland", "India", "China"])]
    print(focus.sort_values(["country", "year"]).groupby("country").tail(3).to_string())


if __name__ == "__main__":
    main()
