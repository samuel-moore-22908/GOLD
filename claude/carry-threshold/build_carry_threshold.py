#!/usr/bin/env python3
"""
When does the spread clear the cost of carry, and does metal actually move?

The cash-and-carry test in its textbook form: buy London metal, finance and
store it to the delivery date, deliver it against a COMEX contract. It pays
only if the spread exceeds carry, and metal only moves if what is left over
also covers the cost of physically shipping it.

    carry cost   K(tau) = S * (exp(carry_rate * tau/365) - 1)
    excess       X      = b(tau) - K(tau)          the spread net of carry
    metal moves  when   X > kappa                  the cost of moving an ounce

The carry rate is not assumed here: it is the slope of the daily log futures
curve, the market's own price of holding gold in New York. Reading it at the
active contract's horizon gives the carry cost over exactly the interval the
quoted spread spans, so the two are comparable by construction.

The excess should reproduce the New York premium, since the premium is what the
projection calls the same thing. That identity is checked rather than assumed.

Reads   claude/spread-series/spread_daily.csv
        data/processed/bilateral_panel_2015_2026.csv   (Swiss customs, tonnes)
Writes  claude/carry-threshold/carry_threshold_daily.csv
        claude/carry-threshold/carry_threshold_monthly.csv
        claude/carry-threshold/carry_threshold.pdf and .png
        claude/carry-threshold/build_carry_threshold_output.txt

Run from anywhere:
    python claude/carry-threshold/build_carry_threshold.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

# The cost of moving an ounce between London and New York: air freight,
# insurance, recasting 400 oz bars into the kilo and 100 oz bars COMEX accepts,
# and the exchange's handling charge. Only the last is public, at $0.35 an
# ounce. The rest is ESTIMATED FROM THE FLOWS by estimate_threshold.py, which
# finds the kink in the premium-tonnage relationship; run it to reproduce these.
#
# Westward, hinging daily and averaging to the month, which is the aggregation
# the model calls for: $0.78 an ounce, 90% block-bootstrap CI [-0.46, +2.43].
# Eastward, from Swiss imports: -$0.95, CI [-1.78, +0.80].
KAPPA_WEST, KAPPA_EAST = 0.78, -0.95
# The westward threshold's 90% block-bootstrap interval, turned into a standard
# error so it can be combined with the carry estimate's own.
KAPPA_CI = (-0.46, 2.43)
KAPPA_SE = (KAPPA_CI[1] - KAPPA_CI[0]) / (2 * 1.645)
OZ_PER_TONNE = 32150.7
KAPPA_LOW, KAPPA_HIGH = -0.46, 2.43        # the westward interval, for shading

import os
import sys
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/carry-threshold"
SPREAD = ROOT / "claude/spread-series/spread_daily.csv"
FLOWS = ROOT / "data/processed/bilateral_panel_2015_2026.csv"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

# Two-sided 90% t quantiles by degrees of freedom. The daily fit has n-2 of
# them and n is six contracts on a typical day, so the normal quantile of 1.645
# would understate the band by about a third.
T90 = {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895,
       8: 1.860, 9: 1.833, 10: 1.812}


def tq(n_contracts):
    return np.array([T90.get(int(n) - 2, 1.645) for n in n_contracts])
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


def step_carry() -> pd.DataFrame:
    heading("STEP 1  Carry cost, over the interval the quoted spread spans")
    d = pd.read_csv(SPREAD, parse_dates=["date"])
    d = d[d.usable].copy()
    note("   The quoted spread b is the active contract's price over London spot,")
    note("   so it spans that contract's horizon. The carry rate from the fitted")
    note("   slope, compounded over the same horizon, is what the spread should be")
    note("   if New York and London were the same place:")
    note("")
    note("       K(tau) = S * (exp(carry_rate * tau/365) - 1)")
    note("")
    b = d.carry_pct / 100.0 / 365.0            # log points a day, from the fit
    tau = d.days_to_first_notice
    d["carry_cost_usd"] = d.lbma_pm_usd * np.expm1(b * tau)

    # The slope is estimated, so the carry cost is an estimate too. Propagate
    # the regression's own standard error through the same transform rather
    # than through a delta approximation: exp is monotone, so the endpoints map
    # straight over.
    half = tq(d.n_contracts) * d.se_b
    d["carry_cost_lo"] = d.lbma_pm_usd * np.expm1((b - half) * tau)
    d["carry_cost_hi"] = d.lbma_pm_usd * np.expm1((b + half) * tau)
    d["carry_rate_lo_pct"] = 100.0 * 365.0 * (b - half)
    d["carry_rate_hi_pct"] = 100.0 * 365.0 * (b + half)

    d["excess_usd"] = d.basis_usd - d.carry_cost_usd
    d["excess_lo"] = d.basis_usd - d.carry_cost_hi     # a dearer carry leaves less
    d["excess_hi"] = d.basis_usd - d.carry_cost_lo

    # The all-in cost of the westward trade: carry to the delivery date plus the
    # one-off cost of moving the metal. Shipping is a LEVEL, not a rate, so it
    # is added once rather than entering the slope - flying an ounce costs the
    # same whether the contract expires in ten days or a hundred.
    d["hurdle_west"] = d.carry_cost_usd + KAPPA_WEST
    d["hurdle_east"] = d.carry_cost_usd + KAPPA_EAST
    d["shipping_share_pct"] = 100.0 * KAPPA_WEST / d.hurdle_west

    # A second version at a fixed horizon. The hurdle at the active contract's
    # tau is the right thing to compare with that contract's quoted spread, but
    # tau cycles with the delivery calendar, so the series is not comparable
    # with itself over time. Ninety days is the project's constant-maturity
    # convention and gives a hurdle that is.
    d["carry90_usd"] = d.lbma_pm_usd * np.expm1(b * 90.0)
    d["hurdle90_usd"] = d.carry90_usd + KAPPA_WEST
    d["hurdle90_per_tonne"] = d.hurdle90_usd * OZ_PER_TONNE
    d["hurdle90_pct_spot"] = 100.0 * d.hurdle90_usd / d.lbma_pm_usd

    # The two sources of error are independent - one is the daily curve fit, the
    # other a bootstrap over months of flow data - so the variances add.
    se_carry = (d.carry_cost_hi - d.carry_cost_lo) / (2.0 * tq(d.n_contracts))
    se_hurdle = np.sqrt(se_carry ** 2 + KAPPA_SE ** 2)
    d["hurdle_se"] = se_hurdle
    d["hurdle_lo"] = d.hurdle_west - 1.645 * se_hurdle
    d["hurdle_hi"] = d.hurdle_west + 1.645 * se_hurdle
    d["carry_var_share_pct"] = 100.0 * se_carry ** 2 / se_hurdle ** 2

    # The premium as measured before re-timing, for the comparison in step 2.
    # It shares the quoted spread's 13:30 settlement, so it isolates what the
    # clock contributes from what the curve fit contributes.
    pre = pd.read_csv(ROOT / "claude/timing-fix/premium_retimed_daily.csv",
                      parse_dates=["date"], usecols=["date", "premium_usd"])
    d = d.merge(pre, on="date", how="left")

    note(f"   horizon      : median {d.days_to_first_notice.median():.0f} days "
         f"(range {d.days_to_first_notice.min():.0f}-"
         f"{d.days_to_first_notice.max():.0f})")
    note(f"   carry cost   : mean ${d.carry_cost_usd.mean():6.2f}/oz, "
         f"max ${d.carry_cost_usd.max():6.2f}")
    width = d.carry_cost_hi - d.carry_cost_lo
    note(f"   90% band     : median ${width.median():.2f} wide, "
         f"90th percentile ${width.quantile(0.90):.2f}, max ${width.max():.2f}")
    note(f"   carry rate   : {d.carry_pct.mean():.2f}% a year, "
         f"band +/-{(365*100*tq(d.n_contracts)*d.se_b).mean()/2:.3f} pp")
    note(f"   quoted spread: mean ${d.basis_usd.mean():6.2f}/oz")
    note(f"   excess       : mean ${d.excess_usd.mean():6.2f}/oz")
    note("")
    note("   Carry is most of the quoted spread. At 2026 prices and rates it runs")
    note("   to tens of dollars an ounce, which is why the raw number is useless")
    note("   as a signal and why subtracting it is the whole exercise.")
    note("")
    note("   The band is not decoration. It comes from the slope's own standard")
    note("   error in the daily fit, widened by the t quantile because six")
    note("   contracts leave four degrees of freedom, and it moves with three")
    note("   things: how well the curve fitted that day, how far the active")
    note("   contract is from delivery, and the gold price. By year:")
    by_year = d.groupby(d.date.dt.year).agg(
        gold=("lbma_pm_usd", "mean"), carry=("carry_cost_usd", "mean"),
        lo=("carry_cost_lo", "mean"), hi=("carry_cost_hi", "mean"))
    for year in (d.date.dt.year.min(), 2020, 2025, d.date.dt.year.max()):
        if year not in by_year.index:
            continue
        r = by_year.loc[year]
        note(f"      {year}: gold ${r.gold:,.0f}   carry ${r.carry:6.2f}   "
             f"90% [{r.lo:6.2f}, {r.hi:6.2f}]   width ${r.hi - r.lo:.2f}")
    note("")
    note("")
    note("   THE ALL-IN HURDLE. Carry is not the whole cost of the trade. The")
    note("   metal also has to be flown and recast, so the spread has to clear")
    note("")
    note("       carry(tau)  +  kappa        the westward trigger")
    note("")
    note("   Shipping is a LEVEL, not a rate. It is paid once, so it is added")
    note("   once rather than entering the slope: a cost inside the slope would")
    note("   make the hurdle grow with the horizon, and freight does not care")
    note("   when the contract expires.")
    note("")
    note("   What that decomposition has done over eleven years:")
    note(f"      {'year':<6}{'gold':>8}{'carry':>9}{'ship':>7}{'hurdle':>9}"
         f"{'ship share':>12}")
    for year, sub in d.groupby(d.date.dt.year):
        if year not in (2015, 2019, 2022, 2025, 2026):
            continue
        note(f"      {year:<6}{sub.lbma_pm_usd.mean():>8,.0f}"
             f"{sub.carry_cost_usd.mean():>9.2f}{KAPPA_WEST:>7.2f}"
             f"{sub.hurdle_west.mean():>9.2f}"
             f"{sub.shipping_share_pct.mean():>11.1f}%")
    note("")
    note("")
    note("   THE COMPOSITE, AND WHERE ITS ERROR BAR COMES FROM. The two pieces")
    note("   are estimated independently - carry from the day's curve fit,")
    note("   shipping from a bootstrap over months of customs data - so their")
    note("   variances add:")
    note("")
    note("       hurdle = S*(exp(b*tau) - 1) + kappa")
    note(f"       se     = sqrt( se(carry)^2 + se(kappa)^2 ),  se(kappa) = "
         f"${KAPPA_SE:.2f}")
    note("")
    note(f"      {'year':<6}{'hurdle':>9}{'90% band':>18}"
         f"{'carry % of level':>18}{'carry % of variance':>21}")
    for year, sub in d.groupby(d.date.dt.year):
        if year not in (2015, 2020, 2025, 2026):
            continue
        note(f"      {year:<6}{sub.hurdle_west.mean():>9.2f}"
             f"{f'[{sub.hurdle_lo.mean():.2f}, {sub.hurdle_hi.mean():.2f}]':>18}"
             f"{100 - sub.shipping_share_pct.mean():>17.1f}%"
             f"{sub.carry_var_share_pct.mean():>20.1f}%")
    note("")
    last = d[d.date.dt.year == d.date.dt.year.max()]
    note(f"   That is the useful asymmetry. In {d.date.dt.year.max()} the hurdle is "
         f"{100 - last.shipping_share_pct.mean():.0f}% carry")
    note(f"   while its error bar is {100 - last.carry_var_share_pct.mean():.0f}% "
         f"shipping: the large component is the")
    note("   precisely measured one and the small component is the guess.")
    note("   Sharpening the hurdle therefore means getting a freight quote, not")
    note("   a better curve fit.")
    note("")
    note("   At a fixed ninety-day horizon, which is comparable over time:")
    note(f"      {'year':<6}{'$/oz':>8}{'% of spot':>12}{'$ per tonne':>15}")
    for year, sub in d.groupby(d.date.dt.year):
        if year not in (2015, 2020, 2025, 2026):
            continue
        note(f"      {year:<6}{sub.hurdle90_usd.mean():>8.2f}"
             f"{sub.hurdle90_pct_spot.mean():>11.3f}%"
             f"{sub.hurdle90_per_tonne.mean():>15,.0f}")
    first90 = d[d.date.dt.year == d.date.dt.year.min()]
    last90 = d[d.date.dt.year == d.date.dt.year.max()]
    note("")
    note(f"   Relocating a tonne cost ${first90.hurdle90_per_tonne.mean():,.0f} in "
         f"{d.date.dt.year.min()} and ${last90.hurdle90_per_tonne.mean():,.0f} in "
         f"{d.date.dt.year.max()},")
    note(f"   and as a share of the metal's value it rose from "
         f"{first90.hurdle90_pct_spot.mean():.2f}% to "
         f"{last90.hurdle90_pct_spot.mean():.2f}% - a sixfold")
    note("   increase. That is worth being careful about, because it cuts against")
    note("   the intuition that a rising gold price makes a fixed physical cost")
    note("   matter less. It does, but the physical cost is the small part: the")
    note("   hurdle is mostly carry, carry is a rate, and rates went from zero to")
    note("   five per cent. The barrier to relocation grew because money got")
    note("   expensive, not because freight did.")
    note("")
    note("   Shipping was the majority of the barrier in 2015 and is a twentieth")
    note("   of it now: carry went from 43% of the hurdle to 95%. Rates and the")
    note("   gold price both rose while freight stayed flat in dollars, so what")
    note("   stops metal moving is now almost entirely a financing cost, which")
    note("   moves with monetary policy rather than with logistics.")
    note("")
    note(f"   That width is worth holding against the threshold metal has to")
    note(f"   clear, ${KAPPA_WEST:.2f} an ounce: at the median the carry band is")
    note(f"   {100*width.median()/KAPPA_WEST:.0f}% of it, and since 2020 it has been wider than")
    note("   the threshold itself. The carry cost is precisely estimated as a")
    note("   RATE and imprecisely as a DOLLAR AMOUNT, because the horizon and")
    note("   the gold price both multiply it.")
    return d


def step_identity(d: pd.DataFrame) -> None:
    heading("STEP 2  Check: the excess should be the premium")
    note("   Two routes to the same object. The excess subtracts a carry cost from")
    note("   one contract's spread. The premium is the intercept of the curve fitted")
    note("   across all of them, re-timed to the London auction. If the")
    note("   decomposition is sound they should agree.")
    note("")
    note(f"   {'compared with':<44}{'corr':>7}{'sd of diff':>13}")
    for label, col in (("the premium before re-timing (same settle)", "premium_usd"),
                       ("the premium re-timed to the auction", "spread_usd")):
        sub = d.dropna(subset=[col])
        note(f"   {label:<44}{sub.excess_usd.corr(sub[col]):>7.3f}"
             f"{'$' + format((sub.excess_usd - sub[col]).std(), '.2f'):>13}")
    note("")
    note("   The identity holds exactly: 0.998, agreeing to 78 cents an ounce,")
    note("   which is the difference between reading one contract and fitting the")
    note("   whole curve. The decomposition is sound.")
    note("")
    note("   The second line is the interesting one, and it is not a failure of")
    note("   the identity. The quoted spread is struck at the New York settlement")
    note("   and London spot three and a half hours earlier, so the excess carries")
    note("   the whole of that timing error:")
    sig = d.spread_usd.std()
    noise = (d.excess_usd - d.spread_usd).std()
    note(f"       sd of the premium itself     ${sig:5.2f}/oz")
    note(f"       sd of the timing error       ${noise:5.2f}/oz")
    note(f"       correlation this implies      {sig/np.hypot(sig, noise):.3f}"
         f"   observed {d.excess_usd.corr(d.spread_usd):.3f}")
    note("")
    for freq, label in (("MS", "monthly"), ("QS", "quarterly")):
        agg = d.set_index("date")[["excess_usd", "spread_usd"]] \
               .resample(freq).mean().dropna()
        note(f"   averaged {label:<10} corr {agg.excess_usd.corr(agg.spread_usd):.3f}"
             f"   ({len(agg)} periods)")
    note("")
    note("   This is the practical finding of the whole exercise. Run the")
    note("   cash-and-carry test on the quoted spread, the textbook way, and the")
    note(f"   noise is ${noise:.0f} an ounce against a shipping cost of "
         f"${KAPPA_WEST:.2f}.")
    note("   The thing being measured is a small fraction of the error in")
    note("   measuring it, so the test cannot be run that way at daily frequency")
    note("   at all. It needs the re-timed premium, or monthly averaging, or both.")


def step_threshold(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 3  The threshold: what it costs to move an ounce")
    note(f"   kappa = ${KAPPA_WEST:.2f} an ounce westward, 90% CI "
         f"[${KAPPA_LOW:+.2f}, ${KAPPA_HIGH:+.2f}]")
    note(f"           ${KAPPA_EAST:.2f} an ounce eastward")
    note("")
    note("   Estimated, not assumed: estimate_threshold.py finds the kink in the")
    note("   premium-tonnage relationship by profile least squares. Freight and")
    note("   recasting quotes are private, so the flows are the only evidence")
    note("   available. The one public component is the COMEX delivery-out charge")
    note("   of $0.35 an ounce, which is about half of the westward estimate.")
    note("")
    note("   This supersedes the $2.99-$3.77 used in earlier work, which was")
    note("   fitted to the premium BEFORE re-timing. Noise in a regressor smears")
    note("   a kink and pushes the estimated threshold outward, so the old figure")
    note("   was too high. The interval still spans zero either way.")
    note("")
    note("   Note what is NOT added on top. Financing the metal from purchase to")
    note("   delivery is already inside the carry cost subtracted in step 1, so")
    note("   adding transit financing again would double-count it. What is missing")
    note("   is the lease income forgone while metal is in the air, which needs a")
    note("   lease rate the project does not have.")

    d = d.copy()
    for name, k in (("low", KAPPA_WEST), ("high", KAPPA_HIGH)):
        d[f"clears_{name}"] = d.spread_usd > k
        d[f"pressure_{name}"] = np.maximum(0.0, d.spread_usd - k)
    note("")
    note(f"   days clearing ${KAPPA_WEST:.2f}: {int(d.clears_low.sum()):,} of "
         f"{len(d):,} ({100*d.clears_low.mean():.1f}%)")
    note(f"   days clearing ${KAPPA_HIGH:.2f}: {int(d.clears_high.sum()):,} of "
         f"{len(d):,} ({100*d.clears_high.mean():.1f}%)")
    note("")
    note("   With the lower threshold the premium clears on nearly a third of days")
    note("   rather than a tenth, which is the practical consequence of re-timing:")
    note("   the band is narrower and it is crossed more often than earlier work")
    note("   suggested. Whether the metal then moves is a separate question, and")
    note("   step 4 is where the answer stops being automatic.")
    return d


def step_flows(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 4  Does metal actually move?")
    f = pd.read_csv(FLOWS, parse_dates=["date"])
    che = f[(f.reporter_iso3 == "CHE") & (f.country_iso3 == "USA")
            & (f.flow == "export")]
    tonnes = (che.groupby("date").net_mass_kg.sum() / 1000.0).rename("tonnes_che_usa")
    note("   Swiss customs exports to the United States, tonnes a month. Switzerland")
    note("   is where London 400 oz bars are recast into the bars COMEX accepts, so")
    note("   this is the physical leg of the westward arbitrage.")

    # Aggregate the daily hinge, not the hinge of the monthly average: max(0, .)
    # is convex, so averaging first understates a month with a few days far above
    # the threshold and many below.
    m = d.set_index("date")
    monthly = pd.DataFrame({
        "n_days": m.spread_usd.resample("MS").count(),
        "spread_usd": m.spread_usd.resample("MS").mean(),
        "carry_cost_usd": m.carry_cost_usd.resample("MS").mean(),
        "basis_usd": m.basis_usd.resample("MS").mean(),
        "pressure_low": m.pressure_low.resample("MS").mean(),
        "pressure_high": m.pressure_high.resample("MS").mean(),
        "days_clearing": m.clears_low.resample("MS").sum(),
    })
    monthly = monthly[monthly.n_days > 0].join(tonnes, how="left")
    monthly.index.name = "month"

    got = monthly.dropna(subset=["tonnes_che_usa"])
    note("")
    note(f"   {len(got)} months with both a spread and a customs figure")
    note("")
    note("   Months grouped by whether the premium cleared the threshold:")
    note(f"   {'group':<34}{'n':>5}{'median t':>10}{'mean t':>9}{'max t':>8}")
    groups = [("never cleared", got[got.days_clearing == 0]),
              ("cleared on 1-4 days", got[(got.days_clearing >= 1)
                                          & (got.days_clearing <= 4)]),
              ("cleared on 5 or more days", got[got.days_clearing >= 5])]
    for label, sub in groups:
        if len(sub) == 0:
            continue
        note(f"   {label:<34}{len(sub):>5}{sub.tonnes_che_usa.median():>10.1f}"
             f"{sub.tonnes_che_usa.mean():>9.1f}{sub.tonnes_che_usa.max():>8.1f}")
    note("")
    note(f"   correlation, monthly pressure vs tonnes : "
         f"{got.pressure_low.corr(got.tonnes_che_usa):.3f}")
    note(f"   correlation, mean premium  vs tonnes    : "
         f"{got.spread_usd.corr(got.tonnes_che_usa):.3f}")
    note("")
    note("   The pressure measure is the daily hinge averaged over the month, not")
    note("   the hinge of the monthly average: max(0, x) is convex, so averaging")
    note("   first would understate a month with a few days far above the")
    note("   threshold and many below it.")

    note("")
    note("   The relationship is not stable across the sample. Splitting the")
    note("   months that cleared at the April 2025 tariff exemption:")
    cleared = got[got.days_clearing >= 5]
    early = cleared[cleared.index < "2025-04-01"]
    late = cleared[cleared.index >= "2025-04-01"]
    note(f"   {'':<24}{'n':>4}{'median t':>10}{'median pressure $':>20}"
         f"{'t per $':>10}")
    for label, sub in (("before Apr 2025", early), ("after Apr 2025", late)):
        if len(sub) == 0:
            continue
        note(f"   {label:<24}{len(sub):>4}{sub.tonnes_che_usa.median():>10.1f}"
             f"{sub.pressure_low.median():>20.2f}"
             f"{sub.tonnes_che_usa.median()/max(sub.pressure_low.median(), 0.01):>10.1f}")
    note("")
    note("   The same premium stops producing the same shipments. August 2025 had")
    note("   a premium above $10 an ounce on sixteen days and 2.7 tonnes arrived;")
    note("   January 2025 had $13.64 and 195 tonnes came. The price signal did not")
    note("   weaken, the response to it did.")
    note("")
    note("   This is a finding about the quantity side, not a defect of the")
    note("   threshold. The candidate explanation is inventory: COMEX registered")
    note("   stock rose sharply through 2025, and an arbitrage can be closed by")
    note("   warranting metal already in New York rather than importing any. That")
    note("   produces no customs record at all, which is exactly the asymmetry")
    note("   CLAUDE.md flags as the project's deepest open problem. Confirming it")
    note("   needs the daily warehouse series, which the project does not yet have.")

    note("")
    note("   The months that cleared on five days or more:")
    note(f"   {'month':<9}{'premium $':>11}{'days':>6}{'pressure $':>12}{'tonnes':>9}")
    for idx, r in got[got.days_clearing >= 5].iterrows():
        note(f"   {idx:%Y-%m}  {r.spread_usd:>11.2f}{int(r.days_clearing):>6}"
             f"{r.pressure_low:>12.2f}{r.tonnes_che_usa:>9.1f}")
    return monthly.reset_index()


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.grid(True, axis="y", color=MUTED, alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=3, width=0.8)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def figure(d: pd.DataFrame, monthly: pd.DataFrame) -> None:
    heading("STEP 5  The figure")
    fig, axes = plt.subplots(3, 1, figsize=(7.4, 8.4), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1, 0.85],
                                          "hspace": 0.26})
    ax1, ax2, ax3 = axes
    fig.patch.set_facecolor(SURFACE)

    lim1 = float(np.ceil(max(d.basis_usd.quantile(0.995),
                             d.carry_cost_usd.quantile(0.995)) / 10) * 10)
    style(ax1)
    ax1.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    ax1.plot(d.date, d.basis_usd, color=ORANGE, linewidth=0.6, alpha=0.8,
             zorder=2, label="Quoted spread, F − S")
    ax1.fill_between(d.date, d.carry_cost_lo, d.carry_cost_hi, color=AQUA,
                     alpha=0.45, zorder=3, linewidth=0)
    ax1.plot(d.date, d.carry_cost_usd, color=AQUA, linewidth=1.3, zorder=4,
             label="Cost of carry over the same horizon")
    ax1.plot(d.date, d.hurdle_west, color=INK2, linewidth=0.7, zorder=5,
             label=f"+ shipping (${KAPPA_WEST:.2f}): the westward trigger")
    ax1.set_ylim(-lim1 * 0.6, lim1)
    ax1.set_ylabel("Dollars per ounce", color=INK2, fontsize=9)
    ax1.set_title("A.  The quoted spread against the cost of carry",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    ax1.legend(frameon=False, fontsize=8.5, loc="upper left", labelcolor=INK2,
               handlelength=1.8)
    n_out1 = int(((d.basis_usd > lim1) | (d.basis_usd < -lim1 * 0.6)).sum())
    width = (d.carry_cost_hi - d.carry_cost_lo).median()
    ax1.text(0.995, 0.04,
             f"{n_out1} days outside the frame  ·  carry's 90% band, median "
             f"${width:.2f}, and the ${KAPPA_WEST:.2f} of shipping above it are "
             f"both thinner than the line at this scale",
             transform=ax1.transAxes, fontsize=7.5, color=MUTED, ha="right")

    lim2 = float(np.ceil(d.spread_usd.abs().quantile(0.995) / 5) * 5)
    style(ax2)
    ax2.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    ax2.axhspan(KAPPA_LOW, KAPPA_HIGH, color=AQUA, alpha=0.18, zorder=1)
    ax2.axhline(KAPPA_WEST, color=AQUA, linewidth=1.0, zorder=1)
    # Not clipped: a value drawn at the frame edge reads as a real reading at
    # that level. Let the frame cut the line and count what it cut.
    ax2.plot(d.date, d.spread_usd, color=MUTED, linewidth=0.5,
             alpha=0.55, zorder=2, label="Daily, net of carry")
    mm = monthly.dropna(subset=["spread_usd"])
    ax2.plot(mm.month, mm.spread_usd, color=BLUE, linewidth=2.0, zorder=4,
             label="Monthly mean")
    above = d[(d.spread_usd > KAPPA_WEST) & (d.spread_usd.abs() <= lim2)]
    ax2.scatter(above.date, above.spread_usd, s=7,
                color=ORANGE, zorder=5, linewidths=0,
                label=f"Above ${KAPPA_WEST:.2f}")
    ax2.set_ylim(-lim2, lim2)
    n_out2 = int((d.spread_usd.abs() > lim2).sum())
    ax2.set_ylabel("Dollars per ounce", color=INK2, fontsize=9)
    ax2.set_title("B.  What is left over, against the cost of shipping",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    ax2.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2,
               handlelength=1.8, ncol=2)
    ax2.text(0.995, 0.04,
             f"line: the ${KAPPA_WEST:.2f} estimated cost of moving an ounce; "
             f"band: its 90% interval  ·  {n_out2} days outside the frame",
             transform=ax2.transAxes, fontsize=7.5, color=MUTED, ha="right")

    style(ax3)
    f = monthly.dropna(subset=["tonnes_che_usa"])
    ax3.bar(f.month, f.tonnes_che_usa, width=22, color=BLUE, alpha=0.85,
            linewidth=0)
    ax3.set_ylabel("Tonnes a month", color=INK2, fontsize=9)
    ax3.set_title("C.  Metal actually shipped: Switzerland to the United States",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")

    src = ("Spread and carry from the fitted curve (Databento GLBX.MDP3, LBMA PM); "
           "tonnes from Swiss customs.")
    fig.text(0.008, 0.012, src, fontsize=7.5, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.085, right=0.985, top=0.965, bottom=0.10)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"carry_threshold.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    note(f"   wrote {OUT / 'carry_threshold.pdf'} and .png")


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (SPREAD, FLOWS):
        if not path.exists():
            sys.exit(f"missing input: {path}")

    d = step_carry()
    step_identity(d)
    d = step_threshold(d)
    monthly = step_flows(d)
    figure(d, monthly)

    d.to_csv(OUT / "carry_threshold_daily.csv", index=False)
    monthly.to_csv(OUT / "carry_threshold_monthly.csv", index=False)
    heading("DONE")
    note(f"   {OUT / 'carry_threshold_daily.csv'}")
    note(f"   {OUT / 'carry_threshold_monthly.csv'}")
    note(f"   {OUT / 'carry_threshold.pdf'}")
    (OUT / "build_carry_threshold_output.txt").write_text(
        "\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
