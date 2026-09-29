#!/usr/bin/env python3
"""
Construct the paper's spread, in reduced form, narrating each step as it goes.

The chain is the one in claude/spread-reduced-form/REDUCED_FORM_MODEL.pdf:
start from the number the market quotes, show the three ways it breaks,
remove the time dimension by estimating carry instead of assuming it, and read
off the level that is left. Every step prints the numbers that justify it, so
the log is an argument rather than a progress bar.

    quoted spread      b(tau) = F(tau) - S
    the projection     ln F(tau_i) = a + b*tau_i           (each day)
    the spread         p_hat = a - ln S                    (a level)
    excess carry       omega_hat = 365*b - r               (a rate)

Reads   claude/timing-fix/premium_retimed_daily.csv     (the projection, re-timed)
        data/processed/efp_dislocation_v2.csv           (the quoted spread)
Writes  claude/spread-series/spread_daily.csv
        claude/spread-series/spread_monthly.csv
        claude/spread-series/spread.pdf  and  .png
        claude/spread-series/build_spread_output.txt

Run from anywhere:
    python claude/spread-series/build_spread.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

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
OUT = ROOT / "claude/spread-series"

RETIMED = ROOT / "claude/timing-fix/premium_retimed_daily.csv"
QUOTED = ROOT / "data/processed/efp_dislocation_v2.csv"

# Palette slots 1-3 of the validated default in the dataviz skill, in order.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
# Where metal starts moving, in dollars an ounce, estimated from the flows by
# claude/carry-threshold/estimate_threshold.py. Positive is westward.
KAPPA_WEST, KAPPA_EAST = 0.78, -0.95
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"
MAX_GAP_DAYS = 7

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


# --- the construction --------------------------------------------------------

def load() -> pd.DataFrame:
    heading("STEP 0  What is on disk")
    r = pd.read_csv(RETIMED, parse_dates=["date"])
    q = pd.read_csv(QUOTED, parse_dates=["date"])
    note(f"   projection, re-timed : {len(r):,} days  "
         f"{r.date.min():%Y-%m-%d} to {r.date.max():%Y-%m-%d}")
    note(f"   quoted spread        : {len(q):,} days, front contract by open interest")

    d = r.merge(q[["date", "active_contract", "comex_settle", "basis_usd",
                   "days_to_first_notice"]], on="date", how="inner")
    note(f"   merged               : {len(d):,} days")
    note("")
    note("   The two come from the same settlements. The quoted spread reads one")
    note("   contract; the projection reads the whole curve that day.")
    return d


def step_quoted(d: pd.DataFrame) -> None:
    heading("STEP 1  The number the market quotes:  b = F - S")
    note(f"   mean   ${d.basis_usd.mean():7.2f}/oz")
    note(f"   sd     ${d.basis_usd.std():7.2f}/oz")
    note(f"   range  ${d.basis_usd.min():7.2f} to ${d.basis_usd.max():7.2f}")
    note("")
    note("   If New York is dear relative to London by more than it costs to ship")
    note("   metal, metal ships. That is the intuition the paper needs. But this")
    note("   number cannot carry it, for three reasons.")


def step_breaks(d: pd.DataFrame) -> None:
    heading("STEP 2  Why it breaks")

    note("   (a) It is denominated in a unit that is not comparable over time.")
    by_year = d.groupby(d.date.dt.year).agg(
        gold=("lbma_pm_usd", "mean"), spread_sd=("basis_usd", "std"))
    first, last = by_year.iloc[0], by_year.iloc[-1]
    # Compare dispersion rather than means: the mean spread passes through zero,
    # so a ratio of means is arithmetic rather than evidence.
    note(f"       {by_year.index[0]}: gold ${first.gold:,.0f}, "
         f"spread sd ${first.spread_sd:5.2f}   "
         f"(0.1% of spot = ${first.gold*0.001:.2f})")
    note(f"       {by_year.index[-1]}: gold ${last.gold:,.0f}, "
         f"spread sd ${last.spread_sd:5.2f}   "
         f"(0.1% of spot = ${last.gold*0.001:.2f})")
    note(f"       gold x{last.gold/first.gold:.1f}, dispersion "
         f"x{last.spread_sd/first.spread_sd:.1f}. The same proportional gap is")
    note(f"       worth {last.gold/first.gold:.1f} times the dollars at the end of the "
         f"sample as at")
    note(f"       the start, so pooling the two pools incomparable units.")
    note(f"       corr(spread, gold price) = {d.basis_usd.corr(d.lbma_pm_usd):+.3f}")

    note("")
    note("   (b) It contains carry, and carry moves with the delivery calendar.")
    note("       The front contract's horizon cycles from about two months to zero")
    note("       and resets. Carry is proportional to it, so the spread inherits a")
    note("       sawtooth made by the calendar and nothing else:")
    buckets = pd.cut(d.days_to_first_notice, [0, 15, 30, 45, 60, 90, 200])
    tab = d.groupby(buckets, observed=True).basis_usd.agg(["mean", "size"])
    for idx, row in tab.iterrows():
        note(f"       tau {str(idx):<12} mean spread ${row['mean']:6.2f}   "
             f"({int(row['size']):,} days)")
    note(f"       corr(spread, days to delivery) = "
         f"{d.basis_usd.corr(d.days_to_first_notice):+.3f}")

    note("")
    note("   (c) It mixes a level with a rate. Location, bar form and counterparty")
    note("       trust are paid once. Financing, storage and the forgone lease rate")
    note("       accrue per day. Any single summary of b must pick a horizon at")
    note("       which to compare them, and the pick decides the answer.")
    note("")
    note("   So b is a function of the horizon, not a variable. The object the")
    note("   paper needs is a feature of that function.")


def step_projection(d: pd.DataFrame) -> None:
    heading("STEP 3  Estimate carry instead of assuming it")
    note("   Each day the listed contracts trace a curve. Fitting")
    note("       ln F(tau_i) = a + b*tau_i          weighted by open interest")
    note("   splits it into a level and a rate, and the rate is the market's own")
    note("   carry - revealed by prices, not asserted.")
    note("")
    note(f"   contracts in the fit : median {d.n_contracts.median():.0f} a day "
         f"(range {d.n_contracts.min():.0f}-{d.n_contracts.max():.0f})")
    note(f"   fit quality          : median R2 {d.r2.median():.4f}, "
         f"residual {1e4*d.rmse_logpts.median():.1f} bp of price")
    note(f"   fitted carry         : mean {d.carry_pct.mean():.2f}% a year, "
         f"correlation with SOFR {d.carry_pct.corr(d.short_rate_pct):.3f}")
    note("")
    note("   No interest rate enters that fit. Carry tracking SOFR at 0.95 is")
    note("   therefore a check on the projection, not an input to it.")


def step_spread(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 4  The spread:  p_hat = a - ln S")
    note("   The intercept is the curve extrapolated to zero horizon: the price")
    note("   today of New-York-deliverable metal. Against London spot, that is")
    note("   the premium - a level, in per cent of spot.")
    note("")
    note("   Carry has gone, because it loads on the horizon and the intercept")
    note("   does not. The test is whether the delivery calendar still shows:")
    note(f"       corr(quoted spread, days to delivery) = "
         f"{d.basis_usd.corr(d.days_to_first_notice):+.3f}")
    note(f"       corr(premium,       days to delivery) = "
         f"{d.premium_pct_retimed.corr(d.days_to_first_notice):+.3f}")
    note("   The sawtooth is gone. That is the whole point of the projection.")

    note("")
    note("   The New York leg is read at the London auction rather than at its own")
    note("   settlement three and a half hours later, which removed 55% of the")
    note(f"   daily variance: sd {d.premium_pct.std():.3f} -> "
         f"{d.premium_pct_retimed.std():.3f} pp of spot.")

    d = d.copy()
    d["spread_pct"] = d.premium_pct_retimed
    d["spread_usd"] = d.premium_usd_retimed
    d["excess_carry_pp"] = d.carry_pct - d.short_rate_pct
    d["usable"] = d.retimed & d.fit_ok
    note("")
    note(f"   usable days          : {int(d.usable.sum()):,} of {len(d):,} "
         f"({100*d.usable.mean():.1f}%)")
    note(f"      not re-timed      : {int((~d.retimed).sum())} (market holidays)")
    note(f"      curve fit broken  : {int((~d.fit_ok).sum())} (all in 2020)")
    note("   Both are flagged rather than dropped, so a user can choose.")
    return d


def step_describe(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 5  What the spread looks like")
    u = d[d.usable]
    note(f"   {'':<22}{'mean':>9}{'sd':>9}{'min':>9}{'max':>9}")
    for label, col in (("spread, % of spot", "spread_pct"),
                       ("spread, $/oz", "spread_usd"),
                       ("excess carry, pp", "excess_carry_pp")):
        s = u[col]
        note(f"   {label:<22}{s.mean():>9.3f}{s.std():>9.3f}"
             f"{s.min():>9.3f}{s.max():>9.3f}")
    note("")
    note("   A mean of essentially zero over eleven years is the first thing to")
    note("   check: arbitrage pins New York to London, as it should.")

    m = u.set_index("date")
    monthly = pd.DataFrame({
        "n_days": m.spread_pct.resample("MS").count(),
        "spread_pct": m.spread_pct.resample("MS").mean(),
        "spread_usd": m.spread_usd.resample("MS").mean(),
        "excess_carry_pp": m.excess_carry_pp.resample("MS").mean(),
        "lbma_pm_usd": m.lbma_pm_usd.resample("MS").mean(),
    }).reset_index().rename(columns={"date": "month"})
    monthly = monthly[monthly.n_days > 0]

    note("")
    note("   The ten largest monthly readings:")
    for _, r in monthly.nlargest(10, "spread_pct").iterrows():
        note(f"      {r.month:%Y-%m}   {r.spread_pct:+6.3f}%   "
             f"${r.spread_usd:+7.2f}/oz   ({int(r.n_days)} days)")
    return monthly


# --- the figure --------------------------------------------------------------

def with_gaps(d: pd.DataFrame, col: str, max_gap: int = MAX_GAP_DAYS):
    x, y = list(d["date"]), list(d[col])
    xs, ys = [], []
    for i in range(len(x)):
        if i and (x[i] - x[i - 1]).days > max_gap:
            xs.append(x[i - 1] + pd.Timedelta(days=1))
            ys.append(np.nan)
        xs.append(x[i])
        ys.append(y[i])
    return np.array(xs), np.array(ys)


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
    heading("STEP 6  The figure")
    u = d[d.usable]
    lim = float(np.ceil(u.spread_pct.abs().quantile(0.995) * 2) / 2)
    outside = u[u.spread_pct.abs() > lim]
    note(f"   frame set to +/-{lim:.1f} pp, the 99.5th percentile rounded up")
    note(f"   no-trade band: +${KAPPA_WEST:.2f} westward, ${KAPPA_EAST:.2f} eastward,")
    note(f"   which at {u.lbma_pm_usd.iloc[0]:,.0f} dollar gold is "
         f"{100*KAPPA_WEST/u.lbma_pm_usd.iloc[0]:.3f} per cent of spot and at "
         f"{u.lbma_pm_usd.iloc[-1]:,.0f} is "
         f"{100*KAPPA_WEST/u.lbma_pm_usd.iloc[-1]:.3f} per cent")
    note(f"   {len(outside)} days fall outside it and are marked at the edge")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.4, 6.6), sharex=True,
        gridspec_kw={"height_ratios": [1, 1.15], "hspace": 0.24})
    fig.patch.set_facecolor(SURFACE)

    # Panel A is framed the same way as panel B rather than by its single worst
    # day: a -$237 print in January 2026 otherwise sets the scale and flattens
    # eleven years into a line.
    lim_a = float(np.ceil(d.basis_usd.abs().quantile(0.995) / 10) * 10)
    out_a = d[d.basis_usd.abs() > lim_a]
    style(ax1)
    ax1.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    x, y = with_gaps(d, "basis_usd")
    ax1.plot(x, y, color=ORANGE, linewidth=0.6, alpha=0.85, zorder=2)
    ax1.set_ylim(-lim_a, lim_a)
    ax1.scatter(out_a.date, np.clip(out_a.basis_usd, -lim_a * 0.97, lim_a * 0.97),
                marker="^", s=14, color=INK2, zorder=3, linewidths=0)
    ax1.set_ylabel("Dollars per ounce", color=INK2, fontsize=9)
    ax1.set_title("A.  What the market quotes:  F − S",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    ax1.text(0.005, 0.06,
             f"Scales with the gold price (corr "
             f"{d.basis_usd.corr(d.lbma_pm_usd):.2f}); saws with the delivery "
             f"calendar (corr {d.basis_usd.corr(d.days_to_first_notice):.2f})",
             transform=ax1.transAxes, fontsize=7.5, color=MUTED, va="bottom")
    ax1.text(0.995, 0.06, f"{len(out_a)} days outside the frame",
             transform=ax1.transAxes, fontsize=7.5, color=MUTED,
             va="bottom", ha="right")
    note(f"   panel A framed at +/-${lim_a:.0f}, {len(out_a)} days outside it")

    style(ax2)
    ax2.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    x, y = with_gaps(u, "spread_pct")
    ax2.plot(x, y, color=MUTED, linewidth=0.5, alpha=0.5, zorder=2, label="Daily")

    # Direction, by sign, filled between the monthly line and zero. The
    # thresholds are dollars an ounce while this panel is per cent of spot, so
    # the no-trade band is not a constant here: it narrows as gold rises, which
    # is worth seeing rather than hiding behind a horizontal line.
    mo = monthly.rename(columns={"month": "date"}).copy()
    west_pct = 100.0 * KAPPA_WEST / mo.lbma_pm_usd
    east_pct = 100.0 * KAPPA_EAST / mo.lbma_pm_usd
    ax2.fill_between(mo.date, 0, mo.spread_pct, where=mo.spread_pct >= 0,
                     color=BLUE, alpha=0.16, zorder=2, interpolate=True)
    ax2.fill_between(mo.date, 0, mo.spread_pct, where=mo.spread_pct < 0,
                     color=ORANGE, alpha=0.16, zorder=2, interpolate=True)
    ax2.fill_between(mo.date, east_pct, west_pct, color=MUTED, alpha=0.22,
                     zorder=3, linewidth=0)
    ax2.plot(mo.date, west_pct, color=INK2, linewidth=0.7, zorder=3)
    ax2.plot(mo.date, east_pct, color=INK2, linewidth=0.7, zorder=3)

    x, y = with_gaps(mo, "spread_pct", 45)
    ax2.plot(x, y, color=BLUE, linewidth=2.2, zorder=4, label="Monthly mean",
             solid_capstyle="round")
    ax2.text(0.008, 0.95, f"above the band: metal moves west to New York   "
                          f"(+${KAPPA_WEST:.2f}/oz)",
             transform=ax2.transAxes, fontsize=8, color=BLUE, va="top")
    ax2.text(0.008, 0.04, f"below the band: metal moves east to London   "
                          f"(${KAPPA_EAST:.2f}/oz)",
             transform=ax2.transAxes, fontsize=8, color=ORANGE, va="bottom")
    ax2.text(0.008, 0.885,
             "grey band: the estimated no-trade region",
             transform=ax2.transAxes, fontsize=7.5, color=MUTED, va="top")
    ax2.set_ylim(-lim, lim)
    ax2.set_ylabel("Per cent of spot", color=INK2, fontsize=9)
    ax2.set_title("B.  The spread the paper uses:  the New York premium",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    # Direct labels rather than a legend box: two series, and the corners of
    # this panel are all spoken for.
    ax2.text(pd.Timestamp("2018-03-01"), lim * 0.46, "Daily",
             fontsize=8.5, color=MUTED, ha="center")
    ax2.text(pd.Timestamp("2021-10-01"), lim * 0.42, "Monthly mean",
             fontsize=8.5, color=BLUE, ha="center", fontweight="bold")
    if len(outside):
        ax2.scatter(outside.date, np.clip(outside.spread_pct, -lim * 0.97, lim * 0.97),
                    marker="^", s=14, color=ORANGE, zorder=3, linewidths=0)
        worst = outside.loc[outside.spread_pct.abs().idxmax()]
        ax2.text(0.995, 0.05,
                 f"{len(outside)} days outside the frame, largest "
                 f"{worst.spread_pct:+.1f}% on {worst.date:%d %b %Y}",
                 transform=ax2.transAxes, fontsize=7.5, color=MUTED, ha="right")

    # Label the two peaks, keeping the text inside the frame: the monthly series
    # runs past the top of it in April 2020.
    for month, label in ((monthly.loc[monthly.spread_pct.idxmax(), "month"], None),
                         (pd.Timestamp("2025-01-01"), "Jan 2025")):
        row = monthly.loc[monthly.month == month]
        if row.empty:
            continue
        value = float(row.spread_pct.iloc[0])
        label = label or f"{month:%b %Y}"
        ax2.annotate(label, xy=(month, min(value, lim * 0.98)),
                     xytext=(month - pd.Timedelta(days=260),
                             min(value, lim * 0.98) - lim * 0.30),
                     fontsize=8, color=INK2, ha="center", zorder=5,
                     arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7))

    src = (f"COMEX settlements re-timed to the LBMA auction (Databento GLBX.MDP3); "
           f"LBMA PM.  {d.date.min():%Y}–{d.date.max():%Y}, {len(u):,} usable days.")
    fig.text(0.008, 0.012, src, fontsize=7.5, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.085, right=0.985, top=0.955, bottom=0.135)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"spread.{ext}", dpi=200, facecolor=fig.get_facecolor())
    note(f"   wrote {OUT / 'spread.pdf'} and .png")


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (RETIMED, QUOTED):
        if not path.exists():
            sys.exit(f"missing input: {path}")

    d = load()
    step_quoted(d)
    step_breaks(d)
    step_projection(d)
    d = step_spread(d)
    monthly = step_describe(d)
    figure(d, monthly)

    cols = ["date", "lbma_pm_usd", "spread_pct", "spread_usd", "excess_carry_pp",
            "carry_pct", "short_rate_pct", "basis_usd", "days_to_first_notice",
            "active_contract", "n_contracts", "r2", "retimed", "fit_ok", "usable"]
    d[cols].to_csv(OUT / "spread_daily.csv", index=False)
    monthly.to_csv(OUT / "spread_monthly.csv", index=False)

    heading("DONE")
    note(f"   {OUT / 'spread_daily.csv'}")
    note(f"   {OUT / 'spread_monthly.csv'}")
    note(f"   {OUT / 'spread.pdf'}")
    (OUT / "build_spread_output.txt").write_text("\n".join(LOG) + "\n",
                                                 encoding="utf-8")


if __name__ == "__main__":
    main()
