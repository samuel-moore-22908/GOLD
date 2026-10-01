"""
Step 7. What the episode cost.

Nobody paid a gold tariff. The duty was never collected, the classification hole
was closed, and the metal went home. The question this step answers is what the
threat cost anyway.

The ledger keeps three kinds of cost apart, because conflating them is how these
numbers get inflated.

  I.  REAL RESOURCES. Aircraft, armoured transport, insurance underwriting,
      refinery furnace time, assay labour. These are burned. The world is poorer
      by this amount and nobody is richer. This is deadweight loss in the strict
      sense.

  II. TRANSFERS. The excess basis is paid by one party to another. It is not a
      resource loss to the system, but it is a very real loss to whoever is on
      the wrong side, and it is the mechanism by which a policy rumour turns
      into margin calls. This is the "it is not free to drop your short" line.
      The exposed population is measured, not assumed: the CFTC's disaggregated
      Commitments of Traders report gives the short positions of producers,
      merchants, processors, users and swap dealers, which is the bucket that
      holds dealer shorts hedged against London metal.

  III.OPPORTUNITY COST. Metal sitting in a COMEX warehouse is metal not in the
      London lending pool. The price of that service is the gold lease rate. It
      is a real efficiency loss but it is not cash out of anyone's pocket, so it
      sits in its own tier.

Two further items are reported without a dollar figure, because putting one on
them would be invention: the tonnage diverted away from consumption markets, and
the contamination of the official statistics.

Inputs:  output/flow_did.json, output/transfer_cost.json, output/event_study.json
         output/tariff_contamination.json
         data/processed/efp_dislocation_v2.csv, comex_contract_daily.csv,
         comex_gold_stocks_daily.csv
Output:  output/cost_ledger.json, output/cost_ledger.csv
"""
import json
import time

import numpy as np
import pandas as pd
import requests

OUT = "claude/tariff-relocation-cost/output"
OZ_PER_TONNE = 32150.7
CONTRACT_OZ = 100.0
UA = {"User-Agent": "gold-flow-deconvolution research"}

# Windows, as established in steps 1 and 3.
SURGE = ("2024-12-01", "2025-03-31")     # metal moving; arbitrage executable
AUGUST = ("2025-08-08", "2025-09-08")    # metal frozen; only the price could move
STOCK_BASELINE_DATE = "2025-01-30"       # first COMEX snapshot after the archive gap

# Gold lease rate: the price of the liquidity service metal provides when it sits
# in a lending vault rather than under a warrant. No free public series exists;
# this is the range the ledger carries through as a sensitivity.
LEASE_RATE = (0.005, 0.030)
STORAGE_RATE = 0.0025


def load_json(name):
    with open(OUT + "/" + name) as f:
        return json.load(f)


def cftc_gold_cot(start="2024-01-01"):
    """Weekly disaggregated Commitments of Traders for COMEX 100 oz gold."""
    r = requests.get(
        "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",
        params={"$where": ("contract_market_name = 'GOLD' and "
                           "report_date_as_yyyy_mm_dd > '{}T00:00:00.000'".format(start)),
                "$limit": 5000,
                "$select": ("report_date_as_yyyy_mm_dd,open_interest_all,"
                            "prod_merc_positions_short,swap__positions_short_all,"
                            "prod_merc_positions_long,swap_positions_long_all")},
        headers=UA, timeout=120)
    r.raise_for_status()
    time.sleep(2.0)
    d = pd.DataFrame(r.json())
    d["date"] = pd.to_datetime(d["report_date_as_yyyy_mm_dd"]).dt.tz_localize(None)
    for c in d.columns:
        if c.endswith(("_all", "_short", "_long")):
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d["hedger_short_contracts"] = (d["prod_merc_positions_short"].fillna(0)
                                   + d["swap__positions_short_all"].fillna(0))
    d["hedger_net_short_contracts"] = (
        d["hedger_short_contracts"]
        - d["prod_merc_positions_long"].fillna(0) - d["swap_positions_long_all"].fillna(0))
    return d.sort_values("date").set_index("date")


def basis_daily():
    b = pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])
    return b[b.days_to_first_notice >= 20].set_index("date").sort_index()


def comex_total_oi():
    c = pd.read_csv("data/processed/comex_contract_daily.csv", parse_dates=["date"])
    oi = c.groupby("date")["open_interest"].sum()
    return oi[oi > 0]


def immobilised_tonne_years(start=STOCK_BASELINE_DATE, end="2026-08-19"):
    """Integrate COMEX stock above its level at the baseline date. Snapshots are
    irregular, so the series is interpolated on a daily grid between observed
    dates; no value is extrapolated beyond the observed range."""
    st = (pd.read_csv("data/processed/comex_gold_stocks_daily.csv", parse_dates=["date"])
          .sort_values("date").set_index("date"))
    s = st.loc[start:end, ["combined_total_tonnes", "registered_tonnes"]]
    s = s[~s.index.duplicated(keep="last")]
    grid = pd.date_range(s.index.min(), s.index.max(), freq="D")
    daily = s.reindex(s.index.union(grid)).interpolate("time").reindex(grid)
    base_total = float(s["combined_total_tonnes"].iloc[0])
    base_reg = float(s["registered_tonnes"].iloc[0])
    excess_total = (daily["combined_total_tonnes"] - base_total).clip(lower=0)
    excess_reg = (daily["registered_tonnes"] - base_reg).clip(lower=0)
    return {
        "window": [str(daily.index[0].date()), str(daily.index[-1].date())],
        "days": int(len(daily)),
        "baseline_total_t": base_total,
        "baseline_registered_t": base_reg,
        "peak_excess_total_t": float(excess_total.max()),
        "peak_excess_registered_t": float(excess_reg.max()),
        "peak_date": str(excess_total.idxmax().date()),
        "tonne_years_total": float(excess_total.sum() / 365.25),
        "tonne_years_registered": float(excess_reg.sum() / 365.25),
        "mean_excess_total_t": float(excess_total.mean()),
        "n_snapshots_in_window": int(len(s)),
        "caveat": ("The CME depository reports were recovered from Internet Archive "
                   "snapshots and are irregular. Between the baseline date and the "
                   "peak there are only three observations, so the integral is "
                   "sensitive to the interpolation. More importantly, no snapshot "
                   "exists between 20 Apr 2023 and 30 Jan 2025, so the true "
                   "pre-episode level is unobserved and 30 Jan 2025 is used instead "
                   "-- by which date a large part of the build had already happened. "
                   "This makes the immobilisation figure a lower bound."),
    }


def main():
    did = load_json("flow_did.json")
    tc = load_json("transfer_cost.json")
    ev = load_json("event_study.json")
    contam = load_json("tariff_contamination.json")

    b = basis_daily()
    oi = comex_total_oi()
    cot = cftc_gold_cot()

    ledger = {"framing": {
        "question": ("The gold tariff was never collected. What did the threat cost "
                     "anyway?"),
        "tiers": ["I real resources consumed (deadweight)",
                  "II transfers forced by the dislocation (real to the payer)",
                  "III opportunity cost of immobilised metal",
                  "IV unpriced items"],
    }}

    # ---------------------------------------------------------------- tier I
    tonnes = did["excess_tonnage_for_ledger"]
    west = tonnes["westbound_surge_t"]["range"]
    east = tonnes["eastbound_return_t"]["range"]
    build = tc["bottom_up_build"]
    per_oz_rr = build["real_resource_total_usd_per_oz"]
    per_oz_all = build["all_in_total_usd_per_oz"]

    legs_oz_lo = (west[0] + east[0]) * OZ_PER_TONNE
    legs_oz_hi = (west[1] + east[1]) * OZ_PER_TONNE

    tier1 = {
        "excess_tonnes_westbound": west,
        "excess_tonnes_eastbound": east,
        "excess_tonnes_round_trip": tonnes["round_trip_t"]["range"],
        "ounces_shipped_range": [legs_oz_lo, legs_oz_hi],
        "unit_cost_usd_per_oz_real_resources": per_oz_rr,
        "unit_cost_usd_per_oz_all_in": per_oz_all,
        "real_resource_cost_usdmn": [legs_oz_lo * per_oz_rr[0] / 1e6,
                                     legs_oz_hi * per_oz_rr[1] / 1e6],
        "all_in_cost_usdmn": [legs_oz_lo * per_oz_all[0] / 1e6,
                              legs_oz_hi * per_oz_all[1] / 1e6],
        "note": ("Both legs are charged the full unit cost, including recasting. "
                 "The westbound leg turned 400 oz London Good Delivery bars into "
                 "COMEX-deliverable kilobars and 100 oz bars; the eastbound leg had "
                 "to turn them back. A round trip destroys and recreates bar form "
                 "twice, which is why the trade footprint of a single relocation is "
                 "a multiple of the metal involved."),
    }
    ledger["tier_I_real_resources"] = tier1

    # ---------------------------------------------------------------- tier II
    def window_stats(lo, hi):
        w = b.loc[lo:hi]
        o = oi.loc[lo:hi]
        c = cot.loc[lo:hi]
        return {
            "start": lo, "end": hi, "n_trading_days": int(len(w)),
            "mean_excess_basis_usd": float(w.excess_basis_usd.mean()),
            "max_excess_basis_usd": float(w.excess_basis_usd.max()),
            "mean_total_oi_contracts": float(o.mean()),
            "mean_total_oi_moz": float(o.mean() * CONTRACT_OZ / 1e6),
            "mean_hedger_short_contracts": float(c.hedger_short_contracts.mean()),
            "mean_hedger_short_moz": float(c.hedger_short_contracts.mean() * CONTRACT_OZ / 1e6),
            "hedger_short_share_of_oi": float(c.hedger_short_contracts.mean() / o.mean()),
        }

    tier2 = {"windows": {}}
    for name, (lo, hi) in (("surge_metal_could_move", SURGE),
                           ("august_2025_metal_could_not_move", AUGUST)):
        s = window_stats(lo, hi)
        hedger_oz = s["mean_hedger_short_contracts"] * CONTRACT_OZ
        s["mean_revaluation_of_hedged_short_book_usdmn"] = (
            hedger_oz * s["mean_excess_basis_usd"] / 1e6)
        s["peak_revaluation_of_hedged_short_book_usdmn"] = (
            hedger_oz * s["max_excess_basis_usd"] / 1e6)
        tier2["windows"][name] = s

    # What the shippers earned on the metal that actually moved: the same dollars,
    # seen from the other side of the trade.
    surge = tier2["windows"]["surge_metal_could_move"]
    tier2["basis_paid_on_relocated_metal_usdmn"] = [
        west[0] * OZ_PER_TONNE * surge["mean_excess_basis_usd"] / 1e6,
        west[1] * OZ_PER_TONNE * surge["mean_excess_basis_usd"] / 1e6]

    aug = tier2["windows"]["august_2025_metal_could_not_move"]
    tier2["headline"] = {
        "surge_mean_revaluation_usdmn": surge["mean_revaluation_of_hedged_short_book_usdmn"],
        "august_mean_revaluation_usdmn": aug["mean_revaluation_of_hedged_short_book_usdmn"],
        "august_peak_revaluation_usdmn": aug["peak_revaluation_of_hedged_short_book_usdmn"],
        "reading": (
            "The two windows are the same shock with the escape route open and then "
            "closed. During the surge the arbitrage was executable -- five months of "
            "runway, no duty in force -- so quantity adjusted and the price stayed "
            "near the cost of shipping. In August the duty was already attached to "
            "the delivery bar, so shipping metal in would have meant paying it; "
            "quantity could not adjust and the price took the entire shock. That is "
            "why the widest basis of the whole era coincides with almost no flow, "
            "and it is the sense in which closing a short was not free."),
        "caveat": (
            "The hedger bucket is producers, merchants, processors and users plus "
            "swap dealers. It is the right population -- it is where dealer shorts "
            "hedged against unallocated London metal sit -- but the CFTC does not "
            "report how much of it is spread against London specifically, so this "
            "is the revaluation of the whole hedged short book, an upper bound on "
            "the London-spread component. It is also a mark-to-market: only "
            "positions actually closed at dislocated levels realised it."),
    }
    ledger["tier_II_transfers"] = tier2

    # ---------------------------------------------------------------- tier III
    imm = immobilised_tonne_years()
    spot = float(b.loc[STOCK_BASELINE_DATE:"2026-08-19", "lbma_pm_usd"].mean())
    for key, ty in (("total", imm["tonne_years_total"]),
                    ("registered", imm["tonne_years_registered"])):
        value_years = ty * OZ_PER_TONNE * spot
        imm[key + "_value_usdbn_years"] = value_years / 1e9
        imm[key + "_opportunity_cost_usdmn"] = [
            value_years * (LEASE_RATE[0] + STORAGE_RATE) / 1e6,
            value_years * (LEASE_RATE[1] + STORAGE_RATE) / 1e6]
    imm["mean_spot_over_window_usd_per_oz"] = spot
    imm["lease_rate_range_assumed"] = list(LEASE_RATE)
    imm["storage_rate_assumed"] = STORAGE_RATE
    imm["preferred_measure"] = "registered"
    imm["why_registered"] = (
        "Registered metal is under warrant and inert. Eligible metal is in the same "
        "warehouse but not committed to delivery and can still be lent, so charging "
        "it the full lease rate would overstate the loss. The registered figure is "
        "the conservative one and is what the headline uses.")
    ledger["tier_III_opportunity_cost"] = imm

    # ---------------------------------------------------------------- tier IV
    interference = did["interference"]
    ledger["tier_IV_unpriced"] = {
        "displaced_from_consumption_markets": {
            "donor_corridors_change_t_per_month": interference["donor_corridors_change_t_per_month"],
            "surge_months": 4,
            "total_tonnes_diverted": interference["donor_corridors_change_t_per_month"] * 4,
            "largest_corridors": dict(list(
                interference["per_donor_change_t_per_month"].items())[:5]),
            "why_unpriced": (
                "Pricing this needs local premiums over London in the Indian and "
                "Chinese markets during the surge. Those series are commercial and "
                "were not pulled, so the tonnage is reported and the cost is not "
                "invented. It is not zero: a consumption market short of metal pays "
                "a premium, and that premium is a transfer from households in "
                "India and China to whoever supplied them."),
        },
        "statistical_contamination": {
            "swiss_reciprocal_rate_range_across_vintages_pp":
                contam["vintage_sensitivity"]["published_rate_range_pp"],
            "same_range_with_gold_removed_pp":
                contam["vintage_sensitivity"]["ex_gold_rate_range_pp"],
            "vintage_sensitivity_ratio": contam["vintage_sensitivity"]["spread_ratio"],
            "peak_quarter_gold_share_of_us_goods_deficit_pct":
                contam["us_goods_deficit"]["peak_quarter"]["share_of_deficit_pct"],
            "why_unpriced": (
                "The welfare cost of a mis-set tariff depends on what was done with "
                "it, and the announced rates were suspended, revised and then "
                "superseded by a negotiated agreement. What can be stated is the "
                "size of the arbitrariness the phantom flow introduced."),
        },
    }

    # ---------------------------------------------------------------- headline
    rr = tier1["real_resource_cost_usdmn"]
    ai = tier1["all_in_cost_usdmn"]
    opp = imm["registered_opportunity_cost_usdmn"]
    trans_lo = min(surge["mean_revaluation_of_hedged_short_book_usdmn"],
                   aug["mean_revaluation_of_hedged_short_book_usdmn"])
    trans_hi = aug["peak_revaluation_of_hedged_short_book_usdmn"]

    # What all of it bought. Swiss-reported flow both ways over the episode: the
    # gross number is the trade footprint, the net number is the position change.
    che = pd.read_csv("data/processed/che_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    che = che[(che.country_iso3 == "USA") & (che.date >= "2024-10-01") & (che.date <= "2026-07-31")]
    legs = che.groupby("flow")["net_mass_kg"].sum() / 1000.0
    gross = float(legs.sum())
    net = float(legs.get("export", 0.0) - legs.get("import", 0.0))
    ledger["what_it_bought"] = {
        "window": "2024-10 to 2026-07",
        "gross_bilateral_flow_t": gross,
        "net_position_change_t": net,
        "gross_to_net_ratio": abs(gross / net) if net else None,
        "cost_per_net_tonne_relocated_usdmn": (
            None if abs(net) < 1e-9 else
            [(rr[0] + opp[0]) / abs(net), (ai[1] + opp[1]) / abs(net)]),
        "reading": ("Over the full episode Switzerland shipped {:.0f} tonnes to the "
                    "United States and took {:.0f} back, for a net position change "
                    "of {:+.1f} tonnes. Everything in this ledger was spent moving "
                    "metal to a vault it subsequently left.").format(
                        float(legs.get("export", 0.0)), float(legs.get("import", 0.0)), net),
    }

    ledger["headline"] = {
        "tier_I_real_resources_usdmn": rr,
        "tier_I_all_in_usdmn": ai,
        "tier_III_opportunity_cost_usdmn": opp,
        "resource_plus_opportunity_usdmn": [rr[0] + opp[0], ai[1] + opp[1]],
        "tier_II_transfers_usdmn": [trans_lo, trans_hi],
        "grand_total_including_transfers_usdmn": [rr[0] + opp[0] + trans_lo,
                                                  ai[1] + opp[1] + trans_hi],
        "duty_actually_collected_on_gold_usd": 0,
        "how_to_read_it": (
            "The first three lines are what the episode consumed or forwent. The "
            "transfer line is what changed hands because of it, which is not the "
            "same thing and should not be added to the others without saying so. "
            "The grand total is given because the question asked was what the "
            "volatility cost, and to a desk on the wrong side of it a transfer is "
            "indistinguishable from a loss. Every component carries a wide range, "
            "and the widest ranges are on the assumed unit costs, not on the "
            "measured quantities."),
    }

    with open(OUT + "/cost_ledger.json", "w") as f:
        json.dump(ledger, f, indent=2, default=float)

    rows = [
        ("I", "Physical relocation, real resources only", *rr),
        ("I", "Physical relocation, all in incl. transit finance", *ai),
        ("II", "Hedged short book revaluation, surge window (mean to peak)",
         surge["mean_revaluation_of_hedged_short_book_usdmn"],
         surge["peak_revaluation_of_hedged_short_book_usdmn"]),
        ("II", "Hedged short book revaluation, Aug 2025 (mean to peak)",
         aug["mean_revaluation_of_hedged_short_book_usdmn"],
         aug["peak_revaluation_of_hedged_short_book_usdmn"]),
        ("II", "Basis paid on the metal that actually moved",
         *tier2["basis_paid_on_relocated_metal_usdmn"]),
        ("III", "Immobilised registered COMEX metal, lease + storage forgone", *opp),
    ]
    pd.DataFrame(rows, columns=["tier", "item", "low_usdmn", "high_usdmn"]).to_csv(
        OUT + "/cost_ledger.csv", index=False)

    print("COST LEDGER, 2024-26 GOLD TARIFF EPISODE   (USD millions)\n")
    print("{:<4} {:<56} {:>12} {:>12}".format("tier", "item", "low", "high"))
    print("-" * 88)
    for t, item, lo, hi in rows:
        print("{:<4} {:<56} {:>12,.0f} {:>12,.0f}".format(t, item, lo, hi))
    print("-" * 88)
    h = ledger["headline"]
    print("{:<4} {:<56} {:>12,.0f} {:>12,.0f}".format(
        "", "resources + opportunity cost", *h["resource_plus_opportunity_usdmn"]))
    print("{:<4} {:<56} {:>12,.0f} {:>12,.0f}".format(
        "", "including transfers", *h["grand_total_including_transfers_usdmn"]))
    print("\nduty actually collected on gold: $0")

    print("\nQUANTITIES")
    print("  excess westbound      {:.0f} - {:.0f} t".format(*west))
    print("  excess eastbound      {:.0f} - {:.0f} t".format(*east))
    print("  immobilised (reg.)    {:.0f} tonne-years, peak excess {:.0f} t on {}".format(
        imm["tonne_years_registered"], imm["peak_excess_registered_t"], imm["peak_date"]))
    print("  hedger short book     {:.1f} Moz mean in Aug 2025 ({:.0%} of open interest)".format(
        aug["mean_hedger_short_moz"], aug["hedger_short_share_of_oi"]))
    print("  diverted from India/China/HK etc: {:.0f} t over 4 months".format(
        -ledger["tier_IV_unpriced"]["displaced_from_consumption_markets"]["total_tonnes_diverted"]))

    w = ledger["what_it_bought"]
    print("\nWHAT IT BOUGHT")
    print("  gross bilateral flow {:.0f} t,  net position change {:+.1f} t "
          "(gross/net = {:,.0f}x)".format(
              w["gross_bilateral_flow_t"], w["net_position_change_t"],
              w["gross_to_net_ratio"]))
    print("  cost per net tonne actually relocated: ${:,.0f}m - ${:,.0f}m".format(
        *w["cost_per_net_tonne_relocated_usdmn"]))

    print("\nTHE TWO REGIMES")
    print("  {:<34} {:>10} {:>12} {:>14}".format("", "days", "mean basis", "excess tonnes"))
    print("  {:<34} {:>10} {:>12.2f} {:>14.0f}".format(
        "surge: arbitrage executable", surge["n_trading_days"],
        surge["mean_excess_basis_usd"], west[1]))
    print("  {:<34} {:>10} {:>12.2f} {:>14.0f}".format(
        "August: arbitrage blocked", aug["n_trading_days"],
        aug["mean_excess_basis_usd"], 0))


if __name__ == "__main__":
    main()
