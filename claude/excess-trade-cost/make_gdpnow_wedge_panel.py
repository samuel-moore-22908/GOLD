#!/usr/bin/env python3
"""
The gold wedge in GDPNow, on the counterfactual figure's axis.

One panel, one series: GDPNow minus the Atlanta Fed's gold-adjusted GDPNow,
drawn over the same window as claude/counterfactual/whole_chain.py so the two
can be read against each other. The gold surge goes up in that panel; the
distortion it put into the nowcast goes down in this one, which is the
mechanism - metal arriving is an import, and imports subtract.

Why almost the whole axis is empty. The Atlanta Fed ran a gold-adjusted model
alongside the standard one only for 2025Q1, from 6 March to 29 April 2025. On
30 April the gold-adjusted model BECAME GDPNow and the old one was
discontinued, so before and after that window there is no second model to
difference against. The gap is drawn as a gap rather than as zero, because zero
would be a claim the data does not make: it is not that the adjustment was nil,
it is that nobody computed one.

Reads   claude/excess-trade-cost/gdpnow_gold_daily.csv     (both nowcast paths)
        claude/counterfactual/counterfactual_monthly.csv   (for the window only)
Writes  claude/excess-trade-cost/gdpnow_wedge.pdf and .png

Run make_gdpnow_chart.py first; it writes the input.

Run from anywhere:
    python claude/excess-trade-cost/make_gdpnow_wedge_panel.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

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
OUT = ROOT / "claude/excess-trade-cost"

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]
mpl.rcParams["text.parse_math"] = False


def main() -> None:
    os.chdir(ROOT)
    src = OUT / "gdpnow_gold_daily.csv"
    if not src.exists():
        raise SystemExit(f"missing {src}\nrun make_gdpnow_chart.py first")
    d = pd.read_csv(src, parse_dates=["vintage"], index_col="vintage").dropna()

    # "The spread between GDPNow and the gold-adjusted GDPNow", in that order,
    # so it is negative: the headline nowcast ran this far below the model that
    # strips the gold out.
    d["spread"] = d.standard - d.gold_adjusted

    # The window comes from the counterfactual panel rather than being typed in,
    # so the two figures stay aligned if that one is ever refitted.
    cf = pd.read_csv(ROOT / "claude/counterfactual/counterfactual_monthly.csv",
                     parse_dates=["month"], index_col="month")
    x0, x1 = cf.index[0], cf.index[-1]

    fig, ax = plt.subplots(figsize=(11.0, 5.2))
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.030, 0.962, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.922,
             f"For two months the Fed's own nowcast ran {abs(d.spread.median()):.1f} points low on gold "
             f"alone",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.868,
             "GDPNow for 2025Q1 minus the Atlanta Fed's gold-adjusted GDPNow, "
             "every vintage, on the same axis as the excess-trade panel.\n"
             "Negative means the headline nowcast was that much weaker than the "
             "model that takes the gold out",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="y", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=10, length=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(x0 - pd.Timedelta(days=40), x1 + pd.Timedelta(days=40))
    ax.axhline(0, color=SOFT, linewidth=1.0, zorder=2)
    # The same election marker the excess-trade panel carries, so the eye can
    # line the two up without counting gridlines.
    ax.axvline(pd.Timestamp("2024-11-01"), color=SOFT, linewidth=0.8,
               linestyle=(0, (2, 2)), zorder=1)

    ax.fill_between(d.index, 0, d.spread, color=RED, alpha=0.30, zorder=3)
    ax.plot(d.index, d.spread, color=RED, linewidth=1.6, zorder=4)
    ax.set_ylim(d.spread.min() - 0.55, 0.95)
    ax.set_ylabel("GDPNow minus the gold-adjusted model, pp", color=SOFT,
                  fontsize=11)

    mid = d.index[len(d) // 2]
    ax.annotate(f"{d.spread.min():.1f}pp at its widest,\n"
                f"{abs(d.spread.iloc[-1]):.1f} still there at the final vintage",
                xy=(mid, d.spread.min() * 0.62),
                xytext=(pd.Timestamp("2022-06-01"), d.spread.min() * 0.62),
                fontsize=11, color=INK, ha="left", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=SOFT, linewidth=0.9))
    # To the right of the spike, so it clears the election marker on its left.
    ax.annotate("6 March to\n29 April 2025",
                xy=(d.index[-1] + pd.Timedelta(days=25), 0.60), fontsize=10,
                color=SOFT, ha="left", va="top", linespacing=1.3)
    ax.text(pd.Timestamp("2024-10-20"), d.spread.min() - 0.30, "US election",
            fontsize=10, color=SOFT, ha="right", va="bottom")

    src_note = ("Drawn only where both models exist. The Atlanta Fed ran a "
                "gold-adjusted GDPNow beside the standard one for 2025Q1 alone; "
                "on 30 April 2025 the gold-adjusted model became\n"
                "GDPNow and the old one was discontinued, so outside that window "
                "there is no second model to difference and the line is left as "
                "a gap rather than drawn at zero\n"
                " \n"
                "Source: Federal Reserve Bank of Atlanta, GDPNow tracking workbook")
    fig.text(0.030, 0.015, src_note, fontsize=9, color=SOFT, ha="left",
             va="bottom", linespacing=1.35)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.700, bottom=0.270)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"gdpnow_wedge.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    print(f"window {x0:%Y-%m} to {x1:%Y-%m}, "
          f"wedge drawn {d.index[0]:%d %b} to {d.index[-1]:%d %b %Y} "
          f"({len(d)} vintages)")
    print(f"spread: widest {d.spread.min():.2f}pp, median {d.spread.median():.2f}pp, "
          f"final {d.spread.iloc[-1]:.2f}pp")
    print(f"wrote {OUT / 'gdpnow_wedge.pdf'}")


if __name__ == "__main__":
    main()
