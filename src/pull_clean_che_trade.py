"""
Clean Switzerland's gold trade with USA, UK, India and China from BAZG's
(Federal Office for Customs and Border Security) open-data bulk exports.

BAZG publishes "Goods: Foreign trade by tariff number / country" as two
~600MB zipped CSVs (all tariff codes, all partner countries, monthly,
2002-2026) — one for imports, one for exports. There's no standalone
gold-only export product (only a gold-only *import* one, which this script
cross-checks against). This streams each ~8.5GB uncompressed CSV directly
out of the zip (never extracting it to disk) and keeps only rows for our
four partner countries and HS 7108/7115.

Input:  data/raw/bazg/TN8_IMP_en.zip  (BAZG "imports" = CHE importing FROM partner)
        data/raw/bazg/TN8_EXP_en.zip  (BAZG "exports" = CHE exporting TO partner)
Source (both): https://ocean.nivel.bazg.admin.ch/open-data-reports/TN8_{IMP,EXP}_en/TN8_{IMP,EXP}_en.zip
             via https://opendata.swiss/en/dataset/waren-aussenhandel-nach-tarifnummer-land
Output: data/processed/che_gold_trade_hs4_monthly.csv
"""
import csv
import io
import zipfile

import pandas as pd

PARTNERS = {"US": "United States", "GB": "United Kingdom", "IN": "India", "CN": "China"}
ISO3 = {"United States": "USA", "United Kingdom": "GBR", "India": "IND", "China": "CHN"}
HS4_WANTED = {"7108", "7115"}

ZIPS = {
    "import": ("data/raw/bazg/TN8_IMP_en.zip", "TN8_IMP_en.csv"),
    "export": ("data/raw/bazg/TN8_EXP_en.zip", "TN8_EXP_en.csv"),
}

OUT = "data/processed/che_gold_trade_hs4_monthly.csv"


def stream_filter(zip_path, member, flow):
    rows = []
    with zipfile.ZipFile(zip_path) as z, z.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8")
        reader = csv.DictReader(text, delimiter=";")
        for row in reader:
            if row["Tariffnumber4"] not in HS4_WANTED:
                continue
            if row["Tariffnumber6"] == "7115.10":  # platinum catalysts, not gold
                continue
            if row["Country_isoAlpha2"] not in PARTNERS:
                continue
            rows.append(
                {
                    "date": pd.Timestamp(year=int(row["year"]), month=int(row["month"]), day=1),
                    "reporter_iso3": "CHE",
                    "country": PARTNERS[row["Country_isoAlpha2"]],
                    "country_iso3": ISO3[PARTNERS[row["Country_isoAlpha2"]]],
                    "flow": flow,
                    "hs4": int(row["Tariffnumber4"]),
                    "value_usd": float(row["Value_USD"]),
                    "net_mass_kg": float(row["Quantity_kg"]) if row["Quantity_kg"] else None,
                }
            )
    return rows


def main():
    all_rows = []
    for flow, (zip_path, member) in ZIPS.items():
        print(f"Streaming {zip_path} ...")
        rows = stream_filter(zip_path, member, flow)
        print(f"  kept {len(rows)} rows")
        all_rows.extend(rows)

    d = pd.DataFrame(all_rows)
    out = (
        d.groupby(["date", "reporter_iso3", "country", "country_iso3", "flow", "hs4"], as_index=False)
        [["value_usd", "net_mass_kg"]].sum()
    )
    out["quality"] = "reported"
    out["source"] = "BAZG open data — Foreign trade by tariff number / country"
    out["note"] = (
        "value_usd is BAZG's own USD conversion (Value_USD field), not derived. "
        "net_mass_kg is a genuine quantity field. hs4=7115 covers only the "
        "7115.90 subheading (7115.10 platinum catalysts explicitly excluded "
        "by Tariffnumber6), on the same non-gold-specific-code caveat as the "
        "US/UK pulls — 7115.90 isn't gold-specific by description."
    )

    out = out.sort_values(["country", "flow", "date"]).reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {len(out)} rows to {OUT}")
    print(out.groupby(["country", "flow"])[["value_usd", "net_mass_kg"]].agg(["count", "sum"]))


if __name__ == "__main__":
    main()
