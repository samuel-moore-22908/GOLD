#!/usr/bin/env python3
"""
The whole argument in one panel.

Shipments into the United States, the line they would have followed, the area
between the two, and underneath it the months when the spread actually cleared
the cost of moving metal. Price signal, physical response and excess trade on
one axis.

Reads   data/processed/bilateral_panel_2015_2026.csv          (shipments)
        claude/counterfactual/counterfactual_monthly.csv      (the baseline)
        claude/spread-vs-hurdle/spread_vs_hurdle_monthly.csv  (days clearing)
Writes  claude/counterfactual/whole_chain.pdf and .png

Run from anywhere:
    python claude/counterfactual/make_whole_chain_panel.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

START = "2021-01-01"        # where the chart and the fitted line both begin
BREAK = "2024-11-01"
EPISODE_END = "2025-03-31"
CLEARED_DAYS = 5            # a month "cleared" if the spread beat the hurdle on
                            # this many days; the same rule used elsewhere

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


def shipments() -> pd.Series:
    f = pd.read_csv(ROOT / "data/processed/bilateral_panel_2015_2026.csv",
                    parse_dates=["date"])
    out = None
    for rep in ("CHE", "GBR"):
        s = f[(f.reporter_iso3 == rep) & (f.country_iso3 == "USA")
              & (f.flow == "export")]
        g = s.groupby("date").net_mass_kg.sum() / 1000.0
        out = g if out is None else out.add(g, fill_value=np.nan)
    return out.dropna()


def main() -> None:
    os.chdir(ROOT)
    t = shipments()
    t = t[t.index >= START]
    cf = pd.read_csv(OUT / "counterfactual_monthly.csv", parse_dates=["month"],
                     index_col="month")
    spread = pd.read_csv(ROOT / "claude/spread-vs-hurdle/spread_vs_hurdle_monthly.csv",
                         parse_dates=["date"], index_col="date")

    ep = cf.index <= EPISODE_END
    excess_t = (cf.actual_t - cf.baseline_t)[ep].sum()
    excess_v = (cf.actual_usd_bn - cf.baseline_usd_bn)[ep].sum()
    cleared = spread[spread.days_west >= CLEARED_DAYS].index
    cleared = cleared[cleared >= START]

    fig, ax = plt.subplots(figsize=(11.0, 6.6))
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.030, 0.965, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.930,
             f"About {excess_t:,.0f} tonnes of gold crossed that otherwise "
             f"would not have",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.882,
             f"Gold shipped to the United States from Switzerland and the United "
             f"Kingdom, against a line fitted to the 46 months before the "
             f"election;\n"
             f"the shaded area is worth ${excess_v:.0f}bn, or 10% of the US goods "
             f"trade deficit over those months. The spread cleared the cost of "
             f"shipping in\n"
             f"{len(cleared)} of these months but the metal moved in bulk in five: "
             f"clearing pays for a shipment, it does not compel one",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="both", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=10, length=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # The strip of cleared months sits below zero, so the data never runs into it.
    top = float(np.ceil(t.max() / 50) * 50)
    strip_top, strip_bottom = -14.0, -30.0
    ax.set_ylim(strip_bottom - 6, top + 20)
    ax.set_yticks([y for y in ax.get_yticks() if y >= 0])

    ax.plot(t.index, t.values, color=GREY, linewidth=1.5, zorder=3)
    ax.plot(cf.index, cf.actual_t, color=RED, linewidth=2.0, zorder=5)
    ax.plot(cf.index, cf.baseline_t, color=INK, linewidth=1.0,
            linestyle=(0, (4, 3)), zorder=4)
    ax.fill_between(cf.index, cf.baseline_t, cf.actual_t,
                    where=(cf.actual_t > cf.baseline_t) & ep,
                    color=RED, alpha=0.22, zorder=2, interpolate=True)
    ax.axvline(pd.Timestamp(BREAK), color=SOFT, linewidth=0.8,
               linestyle=(0, (2, 2)), zorder=1)
    ax.axhline(0, color=RULE, linewidth=1.0, zorder=1)

    # The price signal, as a strip: one block per month the spread cleared the
    # cost of shipping. It is the mechanism the shipments above are a response
    # to, so it belongs on the same axis rather than in a panel of its own.
    for month in cleared:
        colour = RED if month >= pd.Timestamp(BREAK) else GREY
        ax.add_patch(plt.Rectangle((mdates.date2num(month), strip_bottom), 24,
                                   strip_top - strip_bottom, color=colour,
                                   alpha=0.85, linewidth=0, zorder=3))
    ax.text(mdates.date2num(pd.Timestamp(START)) - 20, (strip_top + strip_bottom) / 2,
            "spread cleared the\ncost of shipping",
            fontsize=9, color=SOFT, ha="right", va="center", linespacing=1.3)

    ax.set_ylabel("Tonnes a month", color=SOFT, fontsize=11)
    ax.text(pd.Timestamp(BREAK) - pd.Timedelta(days=40), top + 14,
            "US election", fontsize=10, color=SOFT, ha="right", va="top")
    ax.annotate(f"{excess_t:,.0f} tonnes, ${excess_v:.0f}bn\n"
                f"more than the line implies",
                xy=(pd.Timestamp("2025-01-20"), 150),
                xytext=(pd.Timestamp("2022-11-01"), 185),
                fontsize=11, color=INK, ha="left", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=SOFT, linewidth=0.8))

    src = (f"A month counts as cleared when the premium beat carry plus shipping "
           f"on {CLEARED_DAYS} days or more. Only the episode is shaded: months "
           f"after March 2025\nadd a further 87 tonnes\n"
           " \n"
           "Source: Swiss Federal Office for Customs and Border Security; "
           "HM Revenue and Customs; Databento; LBMA; US Census Bureau")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.720, bottom=0.185)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"whole_chain.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    print(f"excess {excess_t:,.0f} t, ${excess_v:.1f}bn")
    print(f"{len(cleared)} months cleared since {START[:7]}, "
          f"{int((cleared >= pd.Timestamp(BREAK)).sum())} of them after the break")
    print(f"wrote {OUT / 'whole_chain.pdf'}")


if __name__ == "__main__":
    main()
