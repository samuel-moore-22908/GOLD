"""
Step 2. Rebuild the Swiss gold trade panel keeping EVERY partner country.

data/processed/che_gold_trade_hs4_monthly.csv keeps only the four project
partners (USA, GBR, IND, CHN). That is the right scope for the main paper, but
it leaves no donor pool: the difference-in-differences in step 4 needs
untreated Swiss export corridors to form a counterfactual for CHE->USA, and
four series (three of them controls) is too thin to say anything about whether
the US corridor is an outlier.

This re-streams the same BAZG bulk zips with the country filter removed. It
takes several minutes per file -- each zip expands to roughly 8.5 GB of CSV --
so it is a separate step, run once, and its output is cached.

Input:  data/raw/bazg/TN8_EXP_en.zip, TN8_IMP_en.zip
Output: output/che_gold_trade_all_partners_monthly.csv
"""
import csv
import io
import zipfile

import pandas as pd

OUT = "claude/tariff-relocation-cost/output/che_gold_trade_all_partners_monthly.csv"
HS4_WANTED = {"7108", "7115"}

ZIPS = {
    "import": ("data/raw/bazg/TN8_IMP_en.zip", "TN8_IMP_en.csv"),
    "export": ("data/raw/bazg/TN8_EXP_en.zip", "TN8_EXP_en.csv"),
}


def stream_filter(zip_path, member, flow):
    """Keep every partner country, HS 7108 and 7115 (excluding the 7115.10
    platinum-catalyst subheading), aggregating to partner x month x hs4 as we
    go so the row list stays small."""
    acc = {}
    with zipfile.ZipFile(zip_path) as z, z.open(member) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter=";")
        for row in reader:
            if row["Tariffnumber4"] not in HS4_WANTED:
                continue
            if row["Tariffnumber6"] == "7115.10":
                continue
            key = (int(row["year"]), int(row["month"]),
                   row["Country_isoAlpha2"], row["Country_txt"], row["Tariffnumber4"])
            v, q = acc.get(key, (0.0, 0.0))
            acc[key] = (v + float(row["Value_USD"] or 0.0),
                        q + float(row["Quantity_kg"] or 0.0))
    return [
        {
            "date": pd.Timestamp(year=y, month=m, day=1),
            "reporter_iso3": "CHE",
            "partner_iso2": iso2,
            "partner": name,
            "flow": flow,
            "hs4": int(hs4),
            "value_usd": v,
            "net_mass_kg": q,
        }
        for (y, m, iso2, name, hs4), (v, q) in acc.items()
    ]


def main():
    rows = []
    for flow, (zip_path, member) in ZIPS.items():
        print("Streaming {} ...".format(zip_path), flush=True)
        got = stream_filter(zip_path, member, flow)
        print("  kept {} aggregated rows".format(len(got)), flush=True)
        rows.extend(got)

    d = pd.DataFrame(rows).sort_values(["flow", "date", "partner"])
    d["source"] = "BAZG open data, Foreign trade by tariff number / country"
    d.to_csv(OUT, index=False)

    exp = d[(d.flow == "export") & (d.date >= "2015-01-01")]
    top = (exp.groupby("partner_iso2")["net_mass_kg"].sum() / 1000).sort_values(ascending=False)
    print("\nTop Swiss gold export destinations 2015-2026 (t):")
    print(top.head(30).round(1).to_string())
    print("\npartners with any export flow since 2015:", exp.partner_iso2.nunique())


if __name__ == "__main__":
    main()
