"""
Apply BACI-derived balancing heuristics to the bilateral panel built by
build_bilateral_panel.py, producing one authoritative value per physical
corridor-month instead of two disagreeing reporter/partner rows.

Evidentiary basis (see RESEARCH_DOSSIER.md §4 for the full writeup): BACI's
reconciled GBR<->CHE gold flows, 2017-2023 (the only corridor and years
checked), land close to whichever country is the *importer* in a given
direction in 5 of 7 years each way. 2019 is an exception where BACI
diverges from BOTH raw reporters in both directions - flagged, not
silently trusted.

**This rule (trust the importer) is only validated on one corridor over
seven years. Applying it to every other corridor and to years outside
2017-2023 is an explicit, documented extrapolation, not a second
validated finding** - there was no BACI cross-check run for USA/IND/CHN
pairs or for 2015-16/2024-26. Treat the balanced panel as "best available
default," not "verified."

Heuristics applied (see also the summary printed at the end of this run):
1. Where both sides of a corridor-month exist, keep the IMPORTER's row
   and drop the exporter's — this collapses each of the six two-sided
   pairs from 2 rows/month/direction to 1.
2. Where only one side exists (every CHN pair, since CHN never reports),
   keep that single row as-is, flagged 'unbalanced-single-source' - trust
   here is unavoidably lower and this rule doesn't change that.
3. 2019 rows are flagged 'baci-anomalous-year' (not dropped) wherever the
   corridor is GBR<->CHE, since that's the one year+corridor combination
   where BACI itself disagreed with both raw reporters.
4. Rule 1 is extrapolated to all pairs/years beyond where it was checked
   (GBR<->CHE, 2017-2023) - flagged 'extrapolated' vs 'baci-validated' in
   the output so this is never silently indistinguishable from a checked
   result.

Output: data/processed/bilateral_panel_balanced.csv
"""
import pandas as pd

PANEL_IN = "data/processed/bilateral_panel_2015_2026.csv"
OUT = "data/processed/bilateral_panel_balanced.csv"

BACI_VALIDATED_PAIR = {"GBR", "CHE"}
BACI_VALIDATED_YEARS = set(range(2017, 2024))
BACI_ANOMALOUS_YEAR = 2019


def main():
    d = pd.read_csv(PANEL_IN, parse_dates=["date"])
    d["year"] = d["date"].dt.year

    reporters = set(d["reporter_iso3"].unique())

    def has_mirror(row):
        # True if the partner also reports (i.e. isn't CHN) - meaning a
        # competing importer/exporter declaration exists for this physical
        # flow.
        return row["country_iso3"] in reporters

    d["mirror_exists"] = d.apply(has_mirror, axis=1)

    # Rule 1 + 2: keep import rows always; keep export rows only where no
    # mirror exists (partner == CHN, i.e. the only data for that physical
    # direction).
    keep = (d["flow"] == "import") | (~d["mirror_exists"])
    balanced = d[keep].copy()

    def method(row):
        if not row["mirror_exists"]:
            return "unbalanced-single-source"  # CHN pairs
        # mirror_exists and flow == import here (export-with-mirror was dropped)
        pair_validated = {row["reporter_iso3"], row["country_iso3"]} == BACI_VALIDATED_PAIR
        if pair_validated and row["year"] == BACI_ANOMALOUS_YEAR:
            return "baci-anomalous-year"
        if pair_validated and row["year"] in BACI_VALIDATED_YEARS:
            return "baci-validated-importer-rule"
        return "extrapolated-importer-rule"

    balanced["balance_method"] = balanced.apply(method, axis=1)

    balanced = balanced.drop(columns=["mirror_exists"]).sort_values(
        ["reporter_iso3", "country_iso3", "flow", "date"]
    ).reset_index(drop=True)
    balanced.to_csv(OUT, index=False)

    print(f"Wrote {len(balanced)} rows to {OUT} (from {len(d)} raw panel rows)")
    print()
    print(balanced["balance_method"].value_counts())
    print()
    print("Rows dropped as redundant exporter-side declarations:", (~keep).sum())


if __name__ == "__main__":
    main()
