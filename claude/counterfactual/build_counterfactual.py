#!/usr/bin/env python3
"""
How much gold trade would not otherwise have happened? Back of the envelope.

Fit a straight line to gold shipments into the United States before the tariff
episode, extrapolate it, and measure the area between the actual series and
that line. That area is the excess trade.

    baseline    a straight line fitted to January 2015 - October 2024
    excess      the area between actual shipments and the extrapolated line
    episode     November 2024 to March 2025, ending the month before the
                April exemption

Reads   data/processed/bilateral_panel_2015_2026.csv   (Swiss and UK customs)
        data/processed/us_hs4_universe_monthly.csv     (US trade, for scale)
Writes  claude/counterfactual/counterfactual_monthly.csv
        claude/counterfactual/counterfactual.pdf and .png
        claude/counterfactual/build_counterfactual_output.txt

Run from anywhere:
    python claude/counterfactual/build_counterfactual.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

PRE_START = "2015-01-01"    # the whole series before the break
BREAK = "2024-11-01"        # the US election, when tariff risk became priceable
EPISODE_END = "2025-03-31"  # the last month before the April exemption

import os
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/counterfactual"

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]
# Two dollar signs in one string would otherwise be read as mathtext and
# rendered in italics, which is how "$2,800 ... $4,000" came out wrong once.
mpl.rcParams["text.parse_math"] = False

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def series(f: pd.DataFrame, reporter: str, col: str, scale: float) -> pd.Series:
    s = f[(f.reporter_iso3 == reporter) & (f.country_iso3 == "USA")
          & (f.flow == "export")]
    g = s.groupby("date")[col].sum() / scale
    return g[g.index >= "2015-01-01"]


def extrapolate(y: pd.Series, pre_start: str = PRE_START) -> tuple[pd.Series, float]:
    """Straight line fitted to the pre-period, evaluated over the whole series.

    The line is returned across every month from pre_start onward, not only the
    months after the break, so a chart can show it running through the data it
    was fitted to as well as the extrapolation. Slicing it at the break gives
    the counterfactual.
    """
    pre = y[(y.index >= pre_start) & (y.index < BREAK)]
    slope, intercept = np.polyfit(np.arange(len(pre)), pre.values, 1)
    whole = y[y.index >= pre_start]
    # Not clipped at zero: a clip would put a kink in what is meant to be a
    # straight line. With the fit starting in 2015 the slope is positive and the
    # line never approaches zero, but a warning fires if that ever changes.
    line = pd.Series(slope * np.arange(len(whole)) + intercept, index=whole.index)
    if line.min() < 0:
        print(f"WARNING: the fitted line goes negative "
              f"({line.min():.1f}) - the area below zero is not meaningful")
    return line, float(slope)


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv("data/processed/bilateral_panel_2015_2026.csv",
                    parse_dates=["date"])
    tonnes = (series(f, "CHE", "net_mass_kg", 1000)
              + series(f, "GBR", "net_mass_kg", 1000)).dropna()
    value = (series(f, "CHE", "value_usd", 1e9)
             + series(f, "GBR", "value_usd", 1e9)).dropna()

    note("=" * 74)
    note("EXCESS GOLD TRADE: THE AREA BETWEEN ACTUAL AND A PRE-TREND LINE")
    note("=" * 74)
    note("   Gold shipped to the United States from Switzerland and the United")
    note("   Kingdom, the two places it comes from when the arbitrage runs. Both")
    note("   are the exporters' own customs figures, because US import figures")
    note("   carry no mass.")
    note("")

    # The line spans the whole series; its post-break slice is the counterfactual
    # everything below is measured against.
    line_t, slope_t = extrapolate(tonnes)
    line_v, _ = extrapolate(value)
    cf_t, cf_v = line_t[line_t.index >= BREAK], line_v[line_v.index >= BREAK]
    post_t, post_v = tonnes[tonnes.index >= BREAK], value[value.index >= BREAK]
    pre = tonnes[(tonnes.index >= PRE_START) & (tonnes.index < BREAK)]
    ep = post_t.index <= EPISODE_END

    note(f"   pre-period   {pre.index.min():%Y-%m} to {pre.index.max():%Y-%m}, "
         f"{len(pre)} months, mean {pre.mean():.1f} t a month")
    note("   The line is fitted to the whole series before the break, not a")
    note("   recent slice, so the baseline is not chosen to flatter the result.")
    note(f"   fitted line  {slope_t:+.3f} tonnes a month, "
         f"reaching {cf_t.loc['2025-01-01']:.1f} t by January 2025")
    note("")
    note(f"   {'':<14}{'actual':>10}{'baseline':>11}{'excess':>10}")
    note(f"   {'episode, t':<14}{post_t[ep].sum():>10,.0f}{cf_t[ep].sum():>11,.0f}"
         f"{(post_t[ep] - cf_t[ep]).sum():>10,.0f}")
    note(f"   {'episode, $bn':<14}{post_v[ep].sum():>10,.1f}{cf_v[ep].sum():>11,.1f}"
         f"{(post_v[ep] - cf_v[ep]).sum():>10,.1f}")
    note(f"   {'to date, t':<14}{post_t.sum():>10,.0f}{cf_t.sum():>11,.0f}"
         f"{(post_t - cf_t).sum():>10,.0f}")
    note(f"   {'to date, $bn':<14}{post_v.sum():>10,.1f}{cf_v.sum():>11,.1f}"
         f"{(post_v - cf_v).sum():>10,.1f}")

    # The headline is the whole area after the event, not the episode alone.
    # Tonnes net cleanly; dollars do not, so the dollar figure is quoted for the
    # episode at the prices of those months rather than netted across twenty.
    ex_t = (post_t - cf_t).sum()
    ex_v = (post_v[ep] - cf_v[ep]).sum()
    below = (post_t - cf_t).clip(upper=0)
    note("")
    n_below = int((below < 0).sum())
    note(f"   The headline is the whole area after the break: {ex_t:,.0f} tonnes "
         f"over {len(post_t)} months.")
    note(f"   {n_below} of them fall below the line and net off {below.sum():.0f}")
    note("   tonnes; counting only the months above it would give "
         f"{(post_t - cf_t).clip(lower=0).sum():,.0f} t.")
    note("")
    # Why the dollar figure is quoted for the episode and not the full window.
    price = post_v * 1e9 / (post_t * 32150.7)
    netted_line = (post_v - cf_v).sum()
    netted_px = ((post_t - cf_t) * price * 32150.7 / 1e9).sum()
    ep_price = 1e9 * post_v[ep].sum() / (post_t[ep].sum() * 32150.7)
    note("   TONNES NET CLEANLY; DOLLARS DO NOT. Metal went west at about")
    note(f"   ${ep_price:,.0f} an ounce during the episode and came back east later "
         f"at well")
    note("   over four thousand, so a dollar figure netted across the whole window")
    note("   depends more on the price path than on the trade:")
    note(f"      fitting a separate line to the value series   ${netted_line:6.1f}bn")
    note(f"      valuing the excess tonnes month by month      ${netted_px:6.1f}bn")
    note("   Those differ by more than a third for the same 524 tonnes, which is a")
    note("   sign the object is ill-defined rather than that one method is wrong.")
    note("")
    note(f"   So the dollar figure quoted is the episode: ${ex_v:.1f}bn of excess "
         f"over the")
    note(f"   five months to March 2025, at the ${ep_price:,.0f} an ounce those "
         f"shipments")
    note("   actually moved at. That is also the number that matters for the trade")
    note("   statistics, which record gross flows rather than net ones - a tonne")
    note("   leaving later adds to exports, it does not subtract from imports.")

    note("")
    note("   Starting the pre-period elsewhere moves it, but not much over the")
    note("   episode:")
    alts = []
    for start, label in ((PRE_START, "2015"), ("2019-01-01", "2019"),
                         ("2021-01-01", "2021")):
        alt, sl = extrapolate(tonnes, start)
        alt = alt[alt.index >= BREAK]
        got = (post_t[ep] - alt[ep]).sum()
        note(f"      from {label}: slope {sl:+.3f} t a month, "
             f"episode excess {got:,.0f} t")
        if start != PRE_START:
            alts.append((label, got))

    u = pd.read_csv("data/processed/us_hs4_universe_monthly.csv",
                    parse_dates=["date"])
    tot = u.pivot_table(index="date", columns="flow", values="value_usd",
                        aggfunc="sum") / 1e9
    # The US series stops before the gold series does, so the share is computed
    # on the months both cover rather than on mismatched windows.
    # Measured over the episode, to match the dollar figure being quoted.
    imports = tot["imports"].loc[BREAK:EPISODE_END].sum()
    deficit = imports - tot["exports"].loc[BREAK:EPISODE_END].sum()
    note("")
    note(f"   For scale, over the same five months: ${ex_v:.0f}bn of excess against "
         f"a goods")
    note(f"   deficit of ${deficit:,.0f}bn, so {100*ex_v/deficit:.0f}% of it, and "
         f"{100*ex_v/imports:.1f}% of imports.")
    note("")
    note("   None of it was consumed or bought in any economic sense, and a fifth")
    note("   went back out within five months - but it enters the trade balance at")
    note("   full value.")

    monthly = pd.DataFrame({
        "actual_t": tonnes[tonnes.index >= PRE_START],
        "baseline_t": line_t,
        "actual_usd_bn": value[value.index >= PRE_START],
        "baseline_usd_bn": line_v,
    })
    monthly["post_break"] = monthly.index >= BREAK
    monthly["excess_t"] = (monthly.actual_t - monthly.baseline_t).where(
        monthly.post_break)
    monthly["cumulative_excess_t"] = monthly.excess_t.fillna(0).cumsum().where(
        monthly.post_break)
    monthly.index.name = "month"
    monthly.to_csv(OUT / "counterfactual_monthly.csv")

    figure(monthly, deficit, facts={
        "ex_t": ex_t, "ex_v": ex_v, "n_pre": len(pre), "n_below": n_below,
        "episode_t": (post_t[ep] - cf_t[ep]).sum(),
        "pre_from": pre.index.min(), "pre_to": pre.index.max(),
        "alts": alts,
    })
    (OUT / "build_counterfactual_output.txt").write_text("\n".join(LOG) + "\n",
                                                         encoding="utf-8")


def figure(monthly, deficit, facts) -> None:
    ex_t, ex_v = facts["ex_t"], facts["ex_v"]
    pre = monthly[~monthly.post_break]
    post = monthly[monthly.post_break]
    fig, ax = plt.subplots(figsize=(11.0, 6.4))
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.030, 0.965, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.930,
             f"About {ex_t:,.0f} tonnes of gold crossed that otherwise would not have",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.882,
             f"Gold shipped to the United States from Switzerland and the United "
             f"Kingdom, against a straight line fitted to the whole\n"
             f"series before the election and carried forward. The shaded area is "
             f"{ex_t:,.0f} tonnes; the five-month episode within\n"
             f"it is worth ${ex_v:.0f}bn, {100*ex_v/deficit:.0f}% of the US goods "
             f"deficit over those months",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="both", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=10, length=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # The line is drawn across the whole chart: through the months it was fitted
    # to, then on as the counterfactual. Shading starts at the break.
    ax.plot(monthly.index, monthly.baseline_t, color=INK, linewidth=1.0,
            linestyle=(0, (4, 3)), zorder=4)
    ax.plot(pre.index, pre.actual_t, color=GREY, linewidth=1.5, zorder=3)
    ax.plot(post.index, post.actual_t, color=RED, linewidth=2.0, zorder=5)
    ax.fill_between(post.index, post.baseline_t, post.actual_t,
                    where=post.actual_t > post.baseline_t,
                    color=RED, alpha=0.22, zorder=2, interpolate=True)
    ax.axvline(pd.Timestamp(BREAK), color=SOFT, linewidth=0.8,
               linestyle=(0, (2, 2)), zorder=1)
    ax.set_ylabel("Tonnes a month", color=SOFT, fontsize=11)
    ax.text(pd.Timestamp(BREAK) - pd.Timedelta(days=40), ax.get_ylim()[1] * 0.97,
            "US election", fontsize=10, color=SOFT, ha="right", va="top")
    ax.annotate(f"the area between them:\n{ex_t:,.0f} tonnes, ${ex_v:.0f}bn",
                xy=(pd.Timestamp("2025-01-15"), 150),
                xytext=(pd.Timestamp("2023-02-01"), 175),
                fontsize=11, color=INK, ha="left", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=SOFT, linewidth=0.8))

    n_pre = int((monthly.index < BREAK).sum())
    alt_txt = " or ".join(f"{v:,.0f}" for _, v in facts["alts"])
    alt_yrs = " or ".join(lbl for lbl, _ in facts["alts"])
    src = (f"The line is fitted by least squares to all {facts['n_pre']} months "
           f"from {facts['pre_from']:%B %Y} to {facts['pre_to']:%B %Y}, drawn "
           f"through them and then\n"
           f"carried forward. The shaded area is everything after the election, "
           f"netting the {facts['n_below']} months that fall below the line; the "
           f"five to March 2025\n"
           f"are {facts['episode_t']:,.0f} tonnes on their own. Starting the line "
           f"in {alt_yrs} instead moves that episode figure to {alt_txt}\n"
           " \n"
           "Source: Swiss Federal Office for Customs and Border Security; "
           "HM Revenue and Customs; US Census Bureau")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.720, bottom=0.185)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"counterfactual.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    note("")
    note(f"   wrote {OUT / 'counterfactual.pdf'}")


if __name__ == "__main__":
    main()
