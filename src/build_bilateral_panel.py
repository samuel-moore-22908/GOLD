"""
Combine the four independently-pulled reporter files (USA/Census, GBR/HMRC,
CHE/BAZG, IND/FTSPCC) into one harmonized bilateral panel, plus a reporter-
vs-partner mirror comparison for every pair where both sides were pulled.

There is no CHN-reported file (see RESEARCH_DOSSIER.md §2) — CHN's legs
exist in this panel only as the *partner* column in the other four
countries' rows, never as CHN's own reported figures. This is a known,
documented asymmetry, not a bug.

Harmonization decisions (see RESEARCH_DOSSIER.md for the full writeup of
why these were necessary):
- Currency: everything converted to USD. GBR is natively GBP; converted
  using FRED's DEXUSUK monthly-average rate. A few of the earliest/latest
  months may fall outside FRED's cached window and are dropped with a
  warning rather than silently left in GBP.
- US flow split: US's `export_domestic` and `export_reexport` are collapsed
  into the panel's single `export` (using the pre-computed `export_total`
  row) so the four countries share one flow vocabulary. The domestic/
  re-export split is only in the source file, not the panel.
- HS scope: US/GBR/CHE carry hs4 in {7108, 7115}. IND carries no HS
  breakdown at all (FTSPCC's only commodity axis is a predefined "GOLD"
  bucket ~= 7108.12/13 + 7118.90 coin, confirmed to exclude 7115 entirely)
  - IND rows have hs4 = NaN and are flagged via hs_scope instead. IND's
    totals are NOT scope-comparable to the other three's hs4-summed totals.
- Quantity: only GBR and CHE have net_mass_kg. US and IND are value-only.

Output: data/processed/bilateral_panel_2015_2026.csv
        data/processed/mirror_comparison.csv
"""
import pandas as pd

PROCESSED = "data/processed"
OUT_PANEL = f"{PROCESSED}/bilateral_panel_2015_2026.csv"
OUT_MIRROR = f"{PROCESSED}/mirror_comparison.csv"

FX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK&cosd=2015-01-01&coed=2026-07-31"


def load_fx():
    fx = pd.read_csv(FX_URL, na_values=".")
    fx["observation_date"] = pd.to_datetime(fx["observation_date"])
    fx["month"] = fx["observation_date"].values.astype("datetime64[M]")
    monthly = fx.groupby("month")["DEXUSUK"].mean().rename("usd_per_gbp")
    return monthly


def load_us():
    d = pd.read_csv(f"{PROCESSED}/us_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    d = d[d["flow"].isin(["import", "export_total"])].copy()
    d["flow"] = d["flow"].replace({"export_total": "export"})
    d["value_usd"] = d["value_usd"].astype(float)
    d["net_mass_kg"] = pd.NA
    return d[["date", "reporter_iso3", "country_iso3", "flow", "hs4", "value_usd", "net_mass_kg", "quality"]]


def load_gbr(fx_monthly):
    d = pd.read_csv(f"{PROCESSED}/gbr_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    d["month"] = d["date"].values.astype("datetime64[M]")
    before = len(d)
    d = d.merge(fx_monthly, left_on="month", right_index=True, how="left")
    missing_fx = d["usd_per_gbp"].isna().sum()
    if missing_fx:
        print(f"  GBR: dropping {missing_fx}/{len(d)} rows with no FX rate available for that month")
        d = d.dropna(subset=["usd_per_gbp"])
    d["value_usd"] = d["value_gbp"] * d["usd_per_gbp"]
    return d[["date", "reporter_iso3", "country_iso3", "flow", "hs4", "value_usd", "net_mass_kg", "quality"]]


def load_che():
    d = pd.read_csv(f"{PROCESSED}/che_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    return d[["date", "reporter_iso3", "country_iso3", "flow", "hs4", "value_usd", "net_mass_kg", "quality"]]


def load_ind():
    d = pd.read_csv(f"{PROCESSED}/ind_gold_trade_monthly.csv", parse_dates=["date"])
    d["hs4"] = pd.NA
    d["net_mass_kg"] = pd.NA
    return d[["date", "reporter_iso3", "country_iso3", "flow", "hs4", "value_usd", "net_mass_kg", "quality"]]


def build_mirror_comparison(panel):
    """For every (reporter, partner) pair where the partner also has its own
    reported file, compare reporter's import from partner vs partner's
    export to reporter (and vice versa) on total value, summed across hs4."""
    totals = (
        panel.groupby(["reporter_iso3", "country_iso3", "flow", "date"], as_index=False)["value_usd"].sum()
    )
    reporters = set(totals["reporter_iso3"].unique())

    rows = []
    for _, r in totals.iterrows():
        reporter, partner, flow, date, value = (
            r["reporter_iso3"], r["country_iso3"], r["flow"], r["date"], r["value_usd"]
        )
        if partner not in reporters:
            continue  # no mirror possible (this is CHN's situation)
        mirror_flow = "export" if flow == "import" else "import"
        mirror = totals[
            (totals.reporter_iso3 == partner)
            & (totals.country_iso3 == reporter)
            & (totals.flow == mirror_flow)
            & (totals.date == date)
        ]
        if len(mirror):
            rows.append(
                {
                    "date": date,
                    "corridor": f"{reporter}->{partner}" if flow == "export" else f"{partner}->{reporter}",
                    "reporter": reporter,
                    "reporter_flow": flow,
                    "reporter_value_usd": value,
                    "partner_reporting_same_flow_value_usd": mirror["value_usd"].iloc[0],
                }
            )
    m = pd.DataFrame(rows).drop_duplicates(subset=["date", "corridor"])
    m["ratio"] = m["reporter_value_usd"] / m["partner_reporting_same_flow_value_usd"]
    return m


def main():
    print("Loading FX rates ...")
    fx_monthly = load_fx()

    print("Loading and harmonizing sources ...")
    parts = {
        "US": load_us(),
        "GBR": load_gbr(fx_monthly),
        "CHE": load_che(),
        "IND": load_ind(),
    }
    for name, d in parts.items():
        print(f"  {name}: {len(d)} rows")

    panel = pd.concat(parts.values(), ignore_index=True)
    panel["hs_scope"] = panel["hs4"].apply(
        lambda x: "7108/7115 (HS-code level)" if pd.notna(x) else "GOLD bucket, excludes 7115 (see note)"
    )
    panel = panel.sort_values(["reporter_iso3", "country_iso3", "flow", "date"]).reset_index(drop=True)
    panel.to_csv(OUT_PANEL, index=False)
    print(f"\nWrote {len(panel)} rows to {OUT_PANEL}")

    print("\nBuilding mirror comparison ...")
    mirror = build_mirror_comparison(panel)
    mirror.to_csv(OUT_MIRROR, index=False)
    print(f"Wrote {len(mirror)} rows to {OUT_MIRROR}")

    print("\nMirror discrepancy summary by corridor (median ratio, reporter/partner):")
    print(mirror.groupby("corridor")["ratio"].agg(["count", "median", "min", "max"]))


if __name__ == "__main__":
    main()
