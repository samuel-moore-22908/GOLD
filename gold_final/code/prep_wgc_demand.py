"""Extract quarterly gold demand by country from the World Gold Council tables.

WHY THIS IS A SEPARATE STEP. Everything else in gold_final/data/raw comes from
an API and regenerates by running a pull script. The WGC Gold Demand Trends
workbook does not: it is a manual download from Goldhub, it is licensed, and it
is not redistributable, so it lives outside gold_final and this script lifts
only the series the figure needs into a tidy CSV.

WHAT IT TAKES. Two sheets of the workbook:
    Jewellery      jewellery demand by country, tonnes, quarterly
    Bar and Coin   retail investment demand by country, tonnes, quarterly

and six countries: the United States, plus the five largest destinations for US
gold exports - Switzerland, the United Kingdom, Hong Kong, Singapore and India.

ONE GAP WORTH KNOWING. WGC does not break out Swiss JEWELLERY demand; it sits
inside "Other Europe". Switzerland therefore contributes bar and coin only, and
the partner total is a little understated. Swiss jewellery consumption is a few
tonnes a quarter against partner totals in the hundreds, so it does not move
anything - but the figure's note says so rather than leaving it silent.

Run:  .venv\\Scripts\\python.exe gold_final\\code\\prep_wgc_demand.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ============================ EDIT THIS IF YOU MOVE THE PROJECT ==============
REPO_ROOT = r"C:\Users\smoor\GitHub\GOLD"
# Where the manually downloaded WGC workbook lives. A glob, because the file
# name carries the vintage (GDT_Tables_Q2'26_EN.xlsx) and changes each quarter.
WGC_GLOB = r"data/wgc/GDT_Tables*.xlsx"
OUT_DIR = r"gold_final/data/raw"
# ============================================================================

# The US, plus every plausible candidate for its five largest gold export
# destinations. The figure picks the actual top five from the Census data
# rather than assuming them, so this list is deliberately wider than five -
# on a 2022 window Canada displaces India in fifth place, and the point is
# that the figure should follow the data rather than a guess.
COUNTRIES = {
    "United States": "united_states",
    "Switzerland": "switzerland",
    "United Kingdom": "united_kingdom",
    "Hong Kong SAR": "hong_kong",
    "Singapore": "singapore",
    "India": "india",
    "Canada": "canada",
    "Australia": "australia",
    "UAE": "uae",
    "Turkey": "turkey",
    "Japan": "japan",
    "Germany": "germany",
}
SHEETS = {"Jewellery": "jewellery_t", "Bar and Coin": "barcoin_t"}

ROOT = Path(REPO_ROOT).expanduser().resolve()


def quarter_start(label: str) -> str | None:
    """'Q1'22' -> '2022-01-01'. Anything else -> None."""
    s = str(label).strip()
    if len(s) < 4 or not s.startswith("Q"):
        return None
    try:
        q = int(s[1])
        yy = int(s.split("'")[1][:2])
    except (ValueError, IndexError):
        return None
    if q not in (1, 2, 3, 4):
        return None
    return f"{2000 + yy}-{3 * (q - 1) + 1:02d}-01"


def main() -> None:
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas is required: .venv/Scripts/python.exe -m pip install pandas")

    matches = sorted(ROOT.glob(WGC_GLOB))
    if not matches:
        sys.exit(
            f"No WGC workbook found at {ROOT / WGC_GLOB}.\n"
            "It is a manual download from https://www.gold.org/goldhub "
            "(Gold Demand Trends > full dataset) and is not redistributable, "
            "so it is not in the repo. Download it and put it there."
        )
    book = matches[-1]            # latest vintage if several are present
    print(f"   reading {book.relative_to(ROOT)}")

    frames = []
    for sheet, col in SHEETS.items():
        raw = pd.read_excel(book, sheet_name=sheet, header=None)
        header = raw.iloc[4]
        qcols = {i: quarter_start(h) for i, h in header.items()}
        qcols = {i: d for i, d in qcols.items() if d}
        if not qcols:
            sys.exit(f"No quarterly columns found on sheet '{sheet}'.")
        names = raw.iloc[:, 1].astype(str).str.strip()

        for wgc_name, slug in COUNTRIES.items():
            hits = names[names == wgc_name]
            if hits.empty:
                print(f"   {sheet}: {wgc_name} not listed - recorded as missing")
                continue
            row = hits.index[0]
            for i, date in qcols.items():
                frames.append(
                    {"date": date, "country": slug, "series": col,
                     "tonnes": pd.to_numeric(raw.iat[row, i], errors="coerce")}
                )

    tidy = pd.DataFrame(frames)
    wide = (tidy.pivot_table(index=["date", "country"], columns="series",
                             values="tonnes", aggfunc="first")
                .reset_index()
                .sort_values(["date", "country"]))
    for col in SHEETS.values():
        if col not in wide:
            wide[col] = float("nan")
    wide = wide[["date", "country", "jewellery_t", "barcoin_t"]]

    out = ROOT / OUT_DIR / "wgc_demand_quarterly.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(out, index=False)
    print(f"   wrote {out.relative_to(ROOT)}  ({len(wide):,} rows, "
          f"{wide.date.min()} to {wide.date.max()})")

    # India's GROSS BULLION IMPORTS, needed to scale its demand by the share
    # the United States actually supplies. India is the only destination among
    # the five where this matters: it is a large consumption market that
    # sources its gold overwhelmingly from elsewhere, so comparing US exports
    # to its FULL demand is apples to oranges.
    ind = pd.read_excel(book, sheet_name="India Supply", header=None)
    hdr = ind.iloc[4]
    yrs = {i: int(h) for i, h in hdr.items()
           if isinstance(h, (int, float)) and not pd.isna(h) and 2000 < h < 2100}
    lab = ind.iloc[:, 1].astype(str).str.strip()
    hits = ind.index[lab.str.startswith("Gross Bullion Imports")]
    if len(hits) and yrs:
        r = hits[0]
        rows = [{"year": y,
                 "gross_bullion_imports_t": pd.to_numeric(ind.iat[r, i],
                                                          errors="coerce")}
                for i, y in sorted(yrs.items(), key=lambda kv: kv[1])]
        out2 = ROOT / OUT_DIR / "wgc_india_supply_annual.csv"
        pd.DataFrame(rows).to_csv(out2, index=False)
        print(f"   wrote {out2.relative_to(ROOT)}  ({len(rows)} years)")
    else:
        print("   WARNING: could not find India gross bullion imports; "
              "the India scaling in fig15 will fall back to unscaled")

    miss = wide[wide.jewellery_t.isna()].country.unique()
    if len(miss):
        print(f"   note: no jewellery series for {', '.join(miss)} "
              "(WGC reports it inside a regional aggregate)")


if __name__ == "__main__":
    main()
