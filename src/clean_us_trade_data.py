"""
Clean the raw US Census USA Trade Online pulls (General Imports, Domestic
Exports, Foreign Exports / re-exports) into one tidy monthly panel at the
HS4 level.

Input:  data/raw/us_census/US_import.xlsx
        data/raw/us_census/US_domestic_export.xlsx
        data/raw/us_census/US_foreign_export.xlsx
Output: data/processed/us_gold_trade_hs4_monthly.csv
"""
import pandas as pd

RAW = "data/raw/us_census"
OUT = "data/processed/us_gold_trade_hs4_monthly.csv"

ISO3 = {
    "China": "CHN",
    "India": "IND",
    "Switzerland": "CHE",
    "United Kingdom": "GBR",
}

SOURCES = {
    "import": (f"{RAW}/US_import.xlsx", "General Customs Value", "General Customs Value"),
    "export_domestic": (f"{RAW}/US_domestic_export.xlsx", "FAS Value", "FAS Value"),
    "export_reexport": (f"{RAW}/US_foreign_export.xlsx", "FAS Value", "FAS Value"),
}

# Census labels the commodity-code column "HTS Number" for imports and has
# used both "HTS Number" and "Schedule B" for exports across different
# pulls — detect whichever is present rather than hardcoding it per file.
CODE_COL_CANDIDATES = ["HTS Number", "Schedule B"]


def load_one(flow, path, sheet, value_col):
    d = pd.read_excel(path, sheet_name=sheet, header=0)
    code_col = next(c for c in CODE_COL_CANDIDATES if c in d.columns)
    # Drop the "Total:" footer row (and any other summary row) — real
    # observations always have a country, year, month and commodity code.
    d = d.dropna(subset=["Country", "Year", "Month", code_col]).copy()

    d["date"] = pd.to_datetime(
        dict(year=d["Year"].astype(int), month=d["Month"].astype(int), day=1)
    )
    d["country"] = d["Country"]
    d["country_iso3"] = d["country"].map(ISO3)
    # HTS/Schedule B codes are reported at varying granularity across pulls
    # (6-digit here, 10-digit there) but are never left-zero-padded within
    # chapter 71, so the first 4 characters of the code AS GIVEN are always
    # the HS4 heading — do not zero-pad before slicing, or a short code like
    # "710812" left-pads to "0000710812" and produces a bogus hs4 of "0000".
    d["hs_code"] = d[code_col].astype("int64").astype(str)
    d["hs4"] = d["hs_code"].str[:4].astype(int)
    d["value_usd"] = d[value_col].astype("int64")
    d["flow"] = flow

    return d[["date", "country", "country_iso3", "flow", "hs4", "value_usd"]]


def main():
    parts = [load_one(flow, *args) for flow, args in SOURCES.items()]
    raw = pd.concat(parts, ignore_index=True)

    # Aggregates the 6- and 10-digit subheading detail up to HS4 by summing
    # within (date, country, flow, hs4). Each source file reports at a
    # single, consistent code granularity with no overlapping parent/child
    # rows, so this sum does not double-count. Covers HS 7108 (non-monetary
    # gold) and 7115.90 (other articles of precious metal) — the latter was
    # added after most of the Nov 2024-Apr 2025 US-Switzerland tariff-episode
    # flow turned out to be classified there rather than under 7108.
    hs4 = (
        raw.groupby(["date", "country", "country_iso3", "flow", "hs4"], as_index=False)
        ["value_usd"].sum()
    )
    hs4["quality"] = "reported"

    # Convenience total-exports rows (domestic + re-export), flagged as
    # derived rather than reported, mirroring the ch_exports_total
    # convention in exploratory/gold_raw_data.csv.
    exports = hs4[hs4["flow"].isin(["export_domestic", "export_reexport"])]
    total = (
        exports.groupby(["date", "country", "country_iso3", "hs4"], as_index=False)
        ["value_usd"].sum()
    )
    total["flow"] = "export_total"
    total["quality"] = "derived"

    out = pd.concat([hs4, total], ignore_index=True)
    out["source"] = "US Census USA Trade Online"
    out["unit"] = "usd"
    out["note"] = (
        "Value only (Customs Value for imports, FAS Value for exports) — "
        "these pulls did not include a quantity/net-weight field. "
        "export_total = export_domestic + export_reexport (derived)."
    )

    out = out.sort_values(["country", "flow", "date"]).reset_index(drop=True)
    out = out[["date", "country", "country_iso3", "flow", "hs4", "value_usd", "unit", "quality", "source", "note"]]
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")
    print(out.groupby(["country", "flow"])["value_usd"].agg(["count", "sum"]))


if __name__ == "__main__":
    main()
