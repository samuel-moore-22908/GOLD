#!/usr/bin/env python3
"""
How much gold trade would not otherwise have happened? Back of the envelope.

Fit a straight line to gold shipments into the United States before the tariff
episode, extrapolate it, and measure the area between the actual series and
that line. That area is the excess trade.

    baseline    a straight line fitted to January 2021 - October 2024
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

PRE_START = "2021-01-01"    # after the covid distortion
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
    line = pd.Series(np.clip(slope * np.arange(len(whole)) + intercept, 0, None),
                     index=whole.index)
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
    ex_t, ex_v = (post_t - cf_t).sum(), (post_v - cf_v).sum()
    below = (post_t - cf_t).clip(upper=0)
    note("")
    note(f"   The headline is the whole area after the break: {ex_t:,.0f} tonnes and "
         f"${ex_v:.1f}bn")
    note(f"   over {len(post_t)} months. Seven of them fall below the line and net off "
         f"{below.sum():.0f}")
    note("   tonnes; counting only the months above it would give "
         f"{(post_t - cf_t).clip(lower=0).sum():,.0f} t.")
    note("")
    note(f"   implied price of the excess ${1e9*ex_v/(ex_t*32150.7):,.0f} an ounce,")
    note("   which is where gold traded over those months - so the tonnage and")
    note("   the value agree rather than telling two stories.")

    note("")
    note("   Starting the pre-period elsewhere moves it, but not much over the")
    note("   episode:")
    for start, label in ((PRE_START, "2021"), ("2019-01-01", "2019"),
                         ("2015-01-01", "2015")):
        alt, sl = extrapolate(tonnes, start)
        alt = alt[alt.index >= BREAK]
        note(f"      from {label}: slope {sl:+.3f} t a month, "
             f"episode excess {(post_t[ep] - alt[ep]).sum():,.0f} t")

    u = pd.read_csv("data/processed/us_hs4_universe_monthly.csv",
                    parse_dates=["date"])
    tot = u.pivot_table(index="date", columns="flow", values="value_usd",
                        aggfunc="sum") / 1e9
    # The US series stops before the gold series does, so the share is computed
    # on the months both cover rather than on mismatched windows.
    overlap_end = min(post_t.index.max(), tot.index.max())
    imports = tot["imports"].loc[BREAK:overlap_end].sum()
    deficit = imports - tot["exports"].loc[BREAK:overlap_end].sum()
    ex_overlap = (post_v - cf_v).loc[BREAK:overlap_end].sum()
    note("")
    note(f"   For scale, over the {len(tot.loc[BREAK:overlap_end])} months where US "
         f"trade figures also exist")
    note(f"   ({BREAK[:7]} to {overlap_end:%Y-%m}): ${ex_overlap:.0f}bn of excess "
         f"against a goods")
    note(f"   deficit of ${deficit:,.0f}bn, so {100*ex_overlap/deficit:.1f}% of it, "
         f"and {100*ex_overlap/imports:.1f}% of imports.")
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

    figure(monthly, ex_t, ex_v, deficit)
    (OUT / "build_counterfactual_output.txt").write_text("\n".join(LOG) + "\n",
                                                         encoding="utf-8")


def figure(monthly, ex_t, ex_v, deficit) -> None:
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
             f"Kingdom, against a straight line fitted to\n"
             f"January 2021 - October 2024 and carried forward. The shaded area "
             f"is worth ${ex_v:.0f}bn - {100*ex_v/deficit:.0f}% of the US goods "
             f"deficit over the months both series cover",
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

    src = (f"The line is fitted to the 46 months before the election, drawn "
           f"through them and then carried forward. The shaded area is "
           f"everything\n"
           f"after the election, netting the seven months below the line; the "
           f"five to March 2025 account for 699 of the {ex_t:,.0f} tonnes. "
           f"Starting\n"
           f"the line in 2019 or 2015 instead moves that episode figure to 693 "
           f"or 645\n"
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
