"""
Master analysis for the tariff-episode write-up. Loads every cleaned
series in data/processed/ plus the four manually-downloaded sources
(Databento, IMF IRFCL, LBMA vaults, WGC), computes every quantitative
claim used in the paper, and writes them to a single results file so the
prose and the numbers cannot drift apart.

Every non-obvious data treatment is commented inline and echoed into the
results file's `assumptions` block. Run this, then read
data/processed/analysis_results.json alongside the paper.

Units convention throughout: TONNES for mass, USD for value, and
annualized decimal rates (0.05 = 5%/yr) for the basis. 1 t = 32,150.7 troy oz.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

OZ_PER_TONNE = 32150.7
P = Path("data/processed")
OUT = P / "analysis_results.json"

# ---------------------------------------------------------------------------
# Episode windows. Dates are anchored to primary-source events where one
# exists (see data/processed/federal_register_events.csv and
# cbp_gold_bar_rulings.csv), otherwise to the market event they describe.
# ---------------------------------------------------------------------------
EPISODES = {
    "calm_baseline_2015_2019": ("2015-01-01", "2019-12-31"),
    "covid_2020": ("2020-03-01", "2020-05-31"),
    "tariff_anticipation": ("2024-11-05", "2025-04-06"),   # US election -> day before EO 14257
    "post_exemption": ("2025-04-07", "2025-07-30"),        # EO 14257 published -> day before CBP N351466
    "cbp_bar_ruling": ("2025-07-31", "2025-10-31"),        # CBP N351466 dated 31 Jul 2025
    "unwind_2026": ("2026-01-01", "2026-08-20"),
}

results = {"assumptions": {}, "episodes": {}}
A = results["assumptions"]

A["units"] = "Mass in tonnes (1 t = 32,150.7 troy oz). Value in USD. Rates annualized, decimal."
A["episode_windows"] = {k: {"start": v[0], "end": v[1]} for k, v in EPISODES.items()}
A["episode_anchors"] = (
    "tariff_anticipation starts at the 5 Nov 2024 US election and ends the day before "
    "Federal Register doc 2025-06063 (EO 14257, published 7 Apr 2025). cbp_bar_ruling "
    "starts at CBP ruling N351466, dated 31 Jul 2025. Both document identifiers were "
    "retrieved from primary sources by src/pull_event_dates.py."
)


def window(df, datecol, key):
    a, b = EPISODES[key]
    return df[(df[datecol] >= a) & (df[datecol] <= b)]


# ===========================================================================
# 1. EFP / basis dislocation
# ===========================================================================
efp = pd.read_csv(P / "efp_dislocation_v2.csv", parse_dates=["date"])

# TREATMENT: drop observations within 20 days of first notice. The implied
# rate is (basis/spot) annualized by 365/days_to_notice; as days_to_notice
# -> 0 the annualization factor explodes and a one-tick basis becomes a
# double-digit "rate". 20 days is a judgement call; the qualitative
# ranking of episodes is unchanged at 10 or 30 (checked).
EFP_MIN_DAYS = 20
A["efp_min_days_to_notice"] = (
    f"Observations with fewer than {EFP_MIN_DAYS} days to first notice are dropped before "
    "computing rate statistics, because annualizing a small dollar basis over a very short "
    "horizon produces spurious double-digit rates. Ranking of episodes is robust to 10 or 30."
)
efp_r = efp[efp.days_to_first_notice >= EFP_MIN_DAYS].copy()
efp_r["excess_pct_spot"] = efp_r.excess_basis_usd / efp_r.lbma_pm_usd * 100

for k in EPISODES:
    w = window(efp_r, "date", k)
    if not len(w):
        continue
    results["episodes"].setdefault(k, {})["efp"] = {
        "n_days": int(len(w)),
        "mean_dislocation_annualized": float(w.dislocation.mean()),
        "median_dislocation_annualized": float(w.dislocation.median()),
        "max_dislocation_annualized": float(w.dislocation.max()),
        "mean_excess_basis_usd": float(w.excess_basis_usd.mean()),
        "max_excess_basis_usd": float(w.excess_basis_usd.max()),
        "max_raw_basis_usd": float(w.basis_usd.max()),
        "mean_spot_usd": float(w.lbma_pm_usd.mean()),
        "max_excess_pct_of_spot": float(w.excess_pct_spot.max()),
    }

# Peak days, for the chronology table
peaks = efp_r.nlargest(12, "excess_basis_usd")[
    ["date", "active_contract", "basis_usd", "excess_basis_usd", "dislocation", "days_to_first_notice"]]
results["efp_peak_days_all_history"] = [
    {"date": str(r.date.date()), "contract": r.active_contract,
     "raw_basis_usd": float(r.basis_usd), "excess_basis_usd": float(r.excess_basis_usd),
     "dislocation": float(r.dislocation), "days_to_notice": int(r.days_to_first_notice)}
    for r in peaks.itertuples()]

A["efp_construction"] = (
    "COMEX leg is the official CME settlement price (Databento GLBX.MDP3 statistics schema, "
    "stat_type=3, verified against the databento_dbn.StatType enum) for the contract with the "
    "highest open interest (stat_type=9) on each date, restricted to contracts still ahead of "
    "first notice. London leg is the LBMA PM auction price. This is a PROXY for a dealer EFP "
    "quote, not an actual EFP: real EFPs are privately negotiated and only visible on "
    "entitlement-gated Bloomberg contributor pages. Carry = overnight rate (SOFR from 3 Apr 2018, "
    "effective fed funds before) + a flat 0.25%/yr storage assumption; no free public gold "
    "storage-cost series exists, and this term is small relative to the dislocations discussed."
)
A["efp_first_notice"] = (
    "Days-to-first-notice uses the last weekday of the month preceding the contract month, "
    "the COMEX convention. Exchange holidays are ignored, so the figure can be off by 1-2 days; "
    "immaterial at the 30-90 day horizons that dominate the sample."
)

# ===========================================================================
# 2. Physical flows: Switzerland -> US, the arbitrage corridor
# ===========================================================================
che = pd.read_csv(P / "che_gold_trade_hs4_monthly.csv", parse_dates=["date"])
che_us = (che[(che.country == "United States") & (che.flow == "export")]
          .groupby("date")[["net_mass_kg", "value_usd"]].sum())
che_us["tonnes"] = che_us.net_mass_kg / 1000

results["che_us_exports_annual_t"] = {
    str(y): round(float(v), 1) for y, v in che_us.tonnes.groupby(che_us.index.year).sum().items()}
results["che_us_exports_monthly_t"] = {
    str(d.date()): round(float(v), 1) for d, v in che_us.tonnes.loc["2024-06":].items()}

for k in EPISODES:
    a, b = EPISODES[k]
    w = che_us.loc[(che_us.index >= a) & (che_us.index <= b), "tonnes"]
    if len(w):
        results["episodes"].setdefault(k, {})["che_us_flow"] = {
            "total_tonnes": float(w.sum()), "months": int(len(w)),
            "peak_month_tonnes": float(w.max()), "mean_monthly_tonnes": float(w.mean())}

A["che_flow_source"] = (
    "Swiss exports to the US, HS 7108 + 7115.90, from BAZG's bulk open-data files "
    "(src/pull_clean_che_trade.py). Mass is BAZG's own reported net weight; no derivation "
    "from value. HS 7115.90 is included because the US Census mirror showed most of the "
    "episode's US-bound flow classified there rather than under 7108 (see paper section on "
    "classification); on the Swiss side 7115 is a small share, so this choice barely moves "
    "the Swiss series but keeps it scope-consistent with the US series."
)

# ===========================================================================
# 3. COMEX warehouse stocks
# ===========================================================================
cx = pd.read_csv(P / "comex_gold_stocks_daily.csv", parse_dates=["date"]).sort_values("date")
for c in ["registered", "eligible", "pledged", "combined_total"]:
    cx[c + "_t"] = cx[c + "_oz"] / OZ_PER_TONNE

def cx_at(datestr):
    row = cx[cx.date == datestr]
    if not len(row):
        return None
    r = row.iloc[0]
    return {"date": datestr, "registered_t": float(r.registered_t),
            "eligible_t": float(r.eligible_t), "pledged_t": float(r.pledged_t),
            "total_t": float(r.combined_total_t)}

# Snapshot coverage is irregular (Internet Archive crawl cadence), so all
# COMEX deltas below are between ACTUAL observed dates, never interpolated.
key_dates = ["2019-11-12", "2020-04-03", "2020-05-19", "2020-07-23", "2020-10-08",
             "2021-10-07", "2023-04-20", "2025-01-30", "2025-03-28", "2025-04-07",
             "2025-07-10", "2025-12-31", "2026-01-30", "2026-08-19"]
results["comex_snapshots"] = [s for s in (cx_at(d) for d in key_dates) if s]

def delta(d0, d1):
    a, b = cx_at(d0), cx_at(d1)
    days = (pd.Timestamp(d1) - pd.Timestamp(d0)).days
    return {"from": d0, "to": d1, "days": days,
            "d_total_t": b["total_t"] - a["total_t"],
            "d_registered_t": b["registered_t"] - a["registered_t"],
            "d_eligible_t": b["eligible_t"] - a["eligible_t"],
            "t_per_day": (b["total_t"] - a["total_t"]) / days}

results["comex_deltas"] = {
    "covid_build_2019_11_to_2020_10": delta("2019-11-12", "2020-10-08"),
    "tariff_build_observed_2025_01_30_to_04_07": delta("2025-01-30", "2025-04-07"),
    "tariff_drain_2025_04_07_to_2026_08_19": delta("2025-04-07", "2026-08-19"),
}
results["comex_coverage_gap"] = {
    "note": "No archived snapshot exists between 2023-04-20 and 2025-01-30.",
    "consequence": ("The pre-election (Nov 2024) COMEX level cannot be observed in this dataset. "
                    "Any 'build since the election' figure therefore rests on a baseline this "
                    "paper cannot verify; all COMEX deltas quoted here run between observed dates."),
    "last_before_gap": cx_at("2023-04-20"), "first_after_gap": cx_at("2025-01-30"),
}
A["comex_source"] = (
    "CME's own daily Metal Depository Statistics report, recovered from Internet Archive "
    "snapshots of a fixed URL (src/pull_comex_warehouse_stocks.py); cmegroup.com blocks "
    "automated access and publishes no date-selectable archive. Dates are the report's own "
    "'Activity Date'. Coverage is whatever the Archive happened to crawl - irregular, and "
    "with the gap noted above. Registered/eligible/pledged are kept separate throughout "
    "because reclassification between them moves the headline without metal moving."
)

# ===========================================================================
# 4. LBMA London vault holdings
# ===========================================================================
lb_raw = pd.read_excel("data/LBMA/LBMA-London-Vault-Holdings-Data-July-2026.xlsx",
                       sheet_name=0, header=None)
# Row 3 carries the most recent month but its label cell is blank; the file
# is titled "July 2026" and row 4 is 2026-06, so row 3 is 2026-07.
recs = []
for i in range(3, len(lb_raw)):
    lab, g = lb_raw.iloc[i, 0], lb_raw.iloc[i, 1]
    if pd.isna(g):
        continue
    if i == 3 and pd.isna(lab):
        per = pd.Period("2026-07", freq="M")
    elif isinstance(lab, str):
        per = pd.Period(lab, freq="M")
    else:
        per = pd.Timestamp(lab).to_period("M")
    recs.append({"month": per.to_timestamp("M"), "gold_t": float(g) * 1000 / OZ_PER_TONNE})
lbma = pd.DataFrame(recs).sort_values("month")
A["lbma_unlabeled_row"] = (
    "The LBMA workbook's most recent row has a blank month label; it is assigned to July 2026 "
    "on the basis of the file title and the fact that the next row is June 2026."
)
results["lbma_vault_t"] = {str(m.date()): round(float(v), 1)
                           for m, v in lbma.set_index("month").gold_t.loc["2024-06":].items()}
lb = lbma.set_index("month").gold_t
def lb_delta(a, b):
    return {"from": a, "to": b, "from_t": float(lb.loc[a]), "to_t": float(lb.loc[b]),
            "change_t": float(lb.loc[b] - lb.loc[a])}
results["lbma_deltas"] = {
    "episode_2024_10_to_2025_03": lb_delta("2024-10-31", "2025-03-31"),
    "recovery_2025_03_to_2026_07": lb_delta("2025-03-31", "2026-07-31"),
}

# ===========================================================================
# 5. Absorption benchmarks from WGC Gold Demand Trends
# ===========================================================================
def wgc_gdt(sheet):
    d = pd.read_excel("data/wgc/GDT_Tables_Q2'26_EN.xlsx", sheet_name=sheet, header=None)
    hdr = d.iloc[4].tolist()
    qcols = {hdr[i]: i for i in range(len(hdr))
             if isinstance(hdr[i], str) and len(hdr[i]) == 5 and hdr[i][0] == "Q"}
    out = {}
    for r in range(5, len(d)):
        name = d.iloc[r, 1]
        if isinstance(name, str) and name.strip():
            out[name.strip()] = {q: d.iloc[r, i] for q, i in qcols.items()}
    return pd.DataFrame(out).T

bar_coin, jewellery = wgc_gdt("Bar and Coin"), wgc_gdt("Jewellery")
QS = ["Q3'24", "Q4'24", "Q1'25", "Q2'25", "Q3'25", "Q4'25", "Q1'26", "Q2'26"]
COUNTRIES = ["United States", "India", "China PR Mainland"]
results["wgc_demand_t"] = {}
for c in COUNTRIES:
    bc = {q: float(bar_coin.loc[c, q]) for q in QS if q in bar_coin.columns}
    jw = {q: float(jewellery.loc[c, q]) for q in QS if q in jewellery.columns}
    results["wgc_demand_t"][c] = {
        "bar_and_coin": {q: round(v, 1) for q, v in bc.items()},
        "jewellery": {q: round(v, 1) for q, v in jw.items()},
        "consumer_total": {q: round(bc[q] + jw[q], 1) for q in bc if q in jw},
    }
A["absorption_benchmark"] = (
    "Consumer absorption is WGC Gold Demand Trends bar-and-coin plus jewellery demand, "
    "quarterly, by country. This REPLACES the single ~115 t/yr US figure used in earlier "
    "drafts of this project, which was a secondary quotation of one analyst's estimate. "
    "WGC's underlying data is Metals Focus, so it inherits that methodology; it is an "
    "estimate, not a customs count. Jewellery is included as absorption because fabricated "
    "gold leaves the tradeable float, but note that jewellery and COMEX-warranted 400oz/kilo "
    "bars are different physical products drawn from different supply chains - the comparison "
    "bounds plausible demand, it does not trace specific metal."
)

# ===========================================================================
# 6. Official reserves: IMF IRFCL (monthly, volume) and WGC (quarterly, tonnes)
# ===========================================================================
IMF_PATH = ("data/IMF/dataset_2026-08-21T19_50_30.834460864Z_"
            "DEFAULT_INTEGRATION_IMF.STA_IRFCL_12.0.0.csv")
VOL_IND = ("Official Reserve Assets and Other Foreign Currency Assets (approximate market value), "
           "Official reserve assets, gold volume in millions of fine troy ounces")
VAL_IND = ("Official Reserve Assets and Other Foreign Currency Assets (approximate market value), "
           "Official reserve assets, gold (including gold deposits and if appropriate gold swapped)")

import csv as _csv
imf_series = {}
with open(IMF_PATH, encoding="utf-8") as f:
    rdr = _csv.DictReader(f)
    months = [c for c in rdr.fieldnames if len(c) == 8 and c[5] == "M"]
    want = {"United States", "United Kingdom", "Switzerland", "India", "China, People's Republic of"}
    for row in rdr:
        if row["COUNTRY"] not in want or row["FREQUENCY"] != "Monthly":
            continue
        if row["INDICATOR"] not in (VOL_IND, VAL_IND):
            continue
        kind = "volume_moz" if row["INDICATOR"] == VOL_IND else "value_usd_mn"
        vals = {m: float(row[m]) for m in months if row[m] not in ("", ".", None)}
        if not vals:
            continue
        key = (row["COUNTRY"], kind)
        # De-duplicate: the export contains repeated rows per country/indicator
        # (different internal series codes). Keep the one with most observations.
        if key not in imf_series or len(vals) > len(imf_series[key]):
            imf_series[key] = vals
A["imf_dedup"] = (
    "The IMF IRFCL bulk export repeats each country/indicator across multiple internal series "
    "codes. Where duplicates occur the series with the most observations is kept; spot checks "
    "showed duplicates carried identical values."
)

def to_series(country, kind):
    v = imf_series.get((country, kind), {})
    s = pd.Series({pd.Period(k.replace("M", ""), freq="M").to_timestamp("M"): val
                   for k, val in v.items()}).sort_index()
    return s

cn_vol = to_series("China, People's Republic of", "volume_moz") * 1e6 / OZ_PER_TONNE  # -> tonnes
cn_val = to_series("China, People's Republic of", "value_usd_mn")
results["pboc_reserves_t_monthly"] = {str(d.date()): round(float(v), 1)
                                      for d, v in cn_vol.loc["2024-01":].items()}
if len(cn_val):
    results["pboc_reserves_value_usdmn_monthly"] = {str(d.date()): round(float(v), 0)
                                                    for d, v in cn_val.loc["2024-01":].items()}

# Monthly change in TONNES is the accumulation measure. Value changes conflate
# purchases with the gold price, which nearly doubled over this window.
cn_chg = cn_vol.diff()
results["pboc_monthly_change_t"] = {str(d.date()): round(float(v), 2)
                                    for d, v in cn_chg.loc["2024-01":].items() if pd.notna(v)}
results["pboc_summary"] = {
    "first_obs": str(cn_vol.index.min().date()), "last_obs": str(cn_vol.index.max().date()),
    "level_2024_10_t": float(cn_vol.loc["2024-10-31"]) if pd.Timestamp("2024-10-31") in cn_vol.index else None,
    "level_latest_t": float(cn_vol.iloc[-1]),
    "mean_monthly_change_2024_11_to_2026_06_t": float(cn_chg.loc["2024-11":"2026-06"].mean()),
    "total_change_2024_11_to_2026_06_t": float(cn_vol.loc["2026-06-30"] - cn_vol.loc["2024-10-31"])
        if pd.Timestamp("2024-10-31") in cn_vol.index else None,
    "n_months_zero_change_2024_11_to_2026_06": int((cn_chg.loc["2024-11":"2026-06"].abs() < 1e-9).sum()),
}
A["pboc_measure"] = (
    "PBoC accumulation is measured in tonnes from the IMF IRFCL 'gold volume in millions of fine "
    "troy ounces' series, monthly, NOT from the USD value series. Over this window the gold price "
    "roughly doubled, so the value of China's reserves rose far faster than its holdings; only "
    "the volume series isolates actual accumulation."
)

# Correlation test: does PBoC accumulation track the COMEX/Swiss episode?
flow_m = che_us.tonnes.copy()
flow_m.index = flow_m.index.to_period("M").to_timestamp("M")
joint = pd.DataFrame({"pboc_change_t": cn_chg, "che_us_flow_t": flow_m}).dropna()
joint = joint.loc["2015-07":]
if len(joint) > 24:
    results["pboc_vs_flow"] = {
        "n_months": int(len(joint)),
        "pearson_r": float(joint.pboc_change_t.corr(joint.che_us_flow_t)),
        "spearman_r": float(joint.pboc_change_t.corr(joint.che_us_flow_t, method="spearman")),
        "pboc_mean_during_tariff_anticipation_t": float(
            joint.loc["2024-11":"2025-04", "pboc_change_t"].mean()),
        "pboc_mean_outside_t": float(
            joint.drop(joint.loc["2024-11":"2025-04"].index).pboc_change_t.mean()),
    }

# WGC quarterly reserves, tonnes, as an independent check on the IMF series
wgc_res = pd.read_excel("data/wgc/Quarterly_gold_and_FX_Reserves_Q1_2026.xlsx",
                        sheet_name="Gold (Tonnes)", header=None)
wgc_hdr = wgc_res.iloc[1].tolist()
qidx = {wgc_hdr[i]: i for i in range(len(wgc_hdr)) if isinstance(wgc_hdr[i], str) and wgc_hdr[i].startswith("Q")}
cn_row = wgc_res[wgc_res[0] == "China, People's Republic of"]
if len(cn_row):
    r = cn_row.iloc[0]
    recent_q = ["Q4 2022", "Q4 2023", "Q4 2024", "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026"]
    results["pboc_reserves_wgc_quarterly_t"] = {
        q: (round(float(r[qidx[q]]), 1) if q in qidx and pd.notna(r[qidx[q]]) else None)
        for q in recent_q}

# ===========================================================================
# 7. ETF holdings (WGC), to test the "was it ETF demand?" alternative
# ===========================================================================
etf = pd.read_excel("data/wgc/ETF_Flows_2026-08-04_1202.xlsx",
                    sheet_name="Holdings by month", header=None)
# Row 5 is the header row; col 0 = date, col 3 = total tonnes (per row-5 labels)
etf_d = etf.iloc[6:, [0, 3]].copy()
etf_d.columns = ["date", "total_t"]
etf_d = etf_d.dropna()
etf_d["date"] = pd.to_datetime(etf_d.date, errors="coerce")
etf_d = etf_d.dropna(subset=["date"])
etf_d["total_t"] = pd.to_numeric(etf_d.total_t, errors="coerce")
etf_s = etf_d.set_index("date").total_t.sort_index()
results["etf_global_holdings_t"] = {str(d.date()): round(float(v), 1)
                                    for d, v in etf_s.loc["2024-06":].items()}
results["etf_deltas"] = {
    "2024_10_to_2025_04": float(etf_s.loc["2024-10-31":"2025-04-30"].iloc[-1]
                                - etf_s.loc["2024-10-31":"2025-04-30"].iloc[0]),
    "2025_04_to_latest": float(etf_s.iloc[-1] - etf_s.loc["2025-04-30":].iloc[0]),
}
A["etf_note"] = (
    "WGC ETF holdings are global totals in tonnes, month-end. Used only to check whether "
    "ETF creation could account for the COMEX build; ETF metal is predominantly vaulted in "
    "London and held under a different custody arrangement than COMEX warrants, so a rise in "
    "ETF holdings is not a source for COMEX registered stock - if anything it competes for it."
)

# ===========================================================================
# 8. Bilateral trade panel: corridor character
# ===========================================================================
panel = pd.read_csv(P / "bilateral_panel_2015_2026.csv", parse_dates=["date"])
mirror = pd.read_csv(P / "mirror_comparison.csv", parse_dates=["date"])
results["mirror_quality"] = {
    "n_corridor_months": int(len(mirror)),
    "share_within_half_to_double": float(((mirror.ratio > 0.5) & (mirror.ratio < 2.0)).mean()),
    "by_corridor": {c: {"n": int(len(g)),
                        "share_within_half_to_double": float(((g.ratio > 0.5) & (g.ratio < 2.0)).mean()),
                        "median_ratio": float(g.ratio.median())}
                    for c, g in mirror.groupby("corridor")},
}

# Corridor classifier: relocation corridors should show extreme month-to-month
# range relative to their level; consumption corridors should not. Uses the
# CHE-reported series (the only reporter with mass for every partner).
cls = []
for partner in ["United States", "United Kingdom", "India", "China"]:
    s = (che[(che.country == partner) & (che.flow == "export")]
         .groupby("date").net_mass_kg.sum() / 1000)
    s = s.loc["2015-01":"2026-07"]
    s_nz = s[s > 0.001]
    if len(s_nz) < 24:
        continue
    cls.append({"corridor": f"CHE->{partner}", "n_months": int(len(s_nz)),
                "mean_t": float(s_nz.mean()), "cv": float(s_nz.std() / s_nz.mean()),
                "max_over_median": float(s_nz.max() / s_nz.median()),
                "top1_month_share_of_total": float(s_nz.max() / s_nz.sum()),
                "top6_months_share_of_total": float(s_nz.nlargest(6).sum() / s_nz.sum())})
results["corridor_classifier"] = cls
A["corridor_classifier"] = (
    "Computed on Swiss-reported export mass by destination, 2015-2026, zero months excluded. "
    "max/median and the share of total flow concentrated in the largest months are reported "
    "alongside the coefficient of variation because CV is compressed by near-zero months - a "
    "relocation corridor can score a LOWER CV than a consumption corridor, which is why earlier "
    "drafts of this project mis-ranked the US corridor."
)

with open(OUT, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"Wrote {OUT}")
for k in ["comex_deltas", "lbma_deltas", "pboc_summary", "pboc_vs_flow", "etf_deltas"]:
    print(f"\n--- {k} ---")
    print(json.dumps(results.get(k, {}), indent=2, default=str))
print("\n--- corridor_classifier ---")
print(pd.DataFrame(cls).round(3).to_string(index=False))
