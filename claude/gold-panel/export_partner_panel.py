"""
Export the bilateral gold panel to CSV so Stata can read it.

Stata 18 has no native parquet reader, and the gold partner pull lives in
transfer/raw/gold_panel_top50.parquet. This flattens it to the columns the
panel figure needs and attaches an ISO3 code per partner, since the figure
labels points with ISO3 rather than full country names.

The ISO3 map is written out by hand rather than derived. Census Schedule C
codes are not ISO codes and the name strings carry parenthetical suffixes
("Germany (Federal Republic of Germany)"), so a fuzzy join would be a silent
source of mislabelled points on a figure whose whole purpose is attribution.

Reads   transfer/raw/gold_panel_top50.parquet
        transfer/raw/gold_partners_top50.csv
Writes  claude/gold-panel/partner_monthly.csv
"""
from pathlib import Path

import pandas as pd

PANEL = Path("transfer/raw/gold_panel_top50.parquet")
NAMES = Path("transfer/raw/gold_partners_top50.csv")
OUT = Path("claude/gold-panel/partner_monthly.csv")

# Census Schedule C code -> ISO 3166-1 alpha-3.
ISO3 = {
    4419: "CHE", 4120: "GBR", 1220: "CAN", 5330: "IND", 5820: "HKG",
    7910: "ZAF", 2010: "MEX", 6021: "AUS", 5081: "ISR", 4759: "ITA",
    4280: "DEU", 4231: "BEL", 5590: "SGP", 4279: "FRA", 5200: "ARE",
    5700: "CHN", 5880: "JPN", 5490: "THA", 3010: "COL", 5800: "KOR",
    4890: "TUR", 4621: "RUS", 2470: "DOM", 5830: "TWN", 3570: "ARG",
    4634: "KAZ", 5110: "JOR", 3510: "BRA", 2190: "NIC", 3330: "PER",
    4550: "POL", 3370: "CHL", 3310: "ECU", 5570: "MYS", 4210: "NLD",
    7930: "BWA", 5520: "VNM", 4330: "AUT", 2774: "SXM", 5230: "OMN",
    4010: "SWE", 5600: "IDN", 2230: "CRI", 4700: "ESP", 2150: "HND",
    5180: "QAT", 5420: "LKA", 5170: "SAU", 4190: "IRL", 2250: "PAN",
}


def main():
    p = pd.read_parquet(PANEL)
    # The API names the code and value fields differently per flow, and the
    # pull kept both sets side by side.
    p["hs6"] = p["I_COMMODITY"].fillna(p["E_COMMODITY"]).astype(str)
    p["value_usd"] = p["GEN_VAL_MO"].fillna(p["ALL_VAL_MO"])
    p = p[p["hs6"].str.startswith(("7108", "7115"))].copy()

    p["cty_code"] = pd.to_numeric(p["CTY_CODE"], errors="coerce").astype("Int64")
    names = pd.read_csv(NAMES).set_index("cty_code")["cty_name"]
    p["cty_name"] = p["cty_code"].map(names)
    p["iso3"] = p["cty_code"].map(ISO3)

    missing = sorted(set(p.loc[p["iso3"].isna(), "cty_code"].dropna().unique()))
    if missing:
        raise SystemExit(f"no ISO3 for Schedule C codes: {missing}")

    out = (p.groupby(["time", "iso3", "cty_name", "flow"], as_index=False)
             ["value_usd"].sum()
             .rename(columns={"time": "ym"}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"  wrote {OUT}: {len(out)} rows, {out.iso3.nunique()} partners, "
          f"{out.ym.min()}..{out.ym.max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
