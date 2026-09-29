#!/usr/bin/env python3
"""
The spread against everything it has to clear, and the metal that then moves.

Panel A puts the estimated spread and the composite carry on one axis, in
dollars an ounce at a fixed ninety-day horizon. The composite carry is the
all-in cost of the trade: carrying the metal to the delivery date plus the
one-off cost of flying and recasting it. Where the spread is above it, the
westward trade pays; where it is below the eastward line, the reverse does.

    spread   = S * (exp(p_hat + 90b) - 1)          the fitted curve at 90 days
    hurdle   = S * (exp(90b) - 1) + kappa          carry plus shipping

Panel B is the net flow between Switzerland and the United States, which is
where the metal physically goes. Both directions come from Swiss customs
rather than one side from each: US export figures carry no mass at all, so a
net series built from both reporters would be exports from Switzerland minus
nothing. Both HS headings are included, 7108 and 7115, because US classification
moved kilo and 100 oz bars between them during the episode.

Reads   claude/spread-series/spread_daily.csv
        data/processed/bilateral_panel_2015_2026.csv
Writes  claude/spread-vs-hurdle/spread_vs_hurdle.pdf and .png
        claude/spread-vs-hurdle/spread_vs_hurdle_monthly.csv

Run from anywhere:
    python claude/spread-vs-hurdle/make_spread_vs_hurdle.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

HORIZON = 90                              # days, the constant-maturity convention
KAPPA_WEST, KAPPA_EAST = 0.78, -0.95      # estimated in claude/carry-threshold

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
OUT = ROOT / "claude/spread-vs-hurdle"

# The project's house style, taken from claude/gold-panel/gold_panel.do so the
# two figures sit together: masthead red for the series in focus, a neutral
# slate for everything else, near-black type, soft grey for decks and sources.
RED = "#E3120B"        # the masthead red, and the series in focus
GREY = "#758D99"       # the neutral series colour
INK = "#121212"        # type
RULE = "#E0E4E7"       # gridlines
SOFT = "#707070"       # deck and source type
SURFACE = "#FFFFFF"
TAB = "███"      # the red masthead tab

mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="both", color=RULE, linewidth=0.8, linestyle="solid")
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=9, length=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def panel_head(ax, title: str, deck: str) -> None:
    """Title and deck at the top left of a panel, the masthead's order."""
    ax.set_title(title, color=INK, fontsize=13, loc="left", pad=22)
    ax.text(0.0, 1.035, deck, transform=ax.transAxes, fontsize=9.5,
            color=SOFT, ha="left", va="bottom")


def load_spread() -> pd.DataFrame:
    d = pd.read_csv(ROOT / "claude/spread-series/spread_daily.csv",
                    parse_dates=["date"])
    d = d[d.usable].copy()
    p = d.spread_pct / 100.0                       # the premium, as a log level
    b = d.carry_pct / 100.0 / 365.0                # carry, log points a day
    d["spread90"] = d.lbma_pm_usd * np.expm1(p + b * HORIZON)
    d["carry90"] = d.lbma_pm_usd * np.expm1(b * HORIZON)
    d["hurdle_west"] = d.carry90 + KAPPA_WEST
    d["hurdle_east"] = d.carry90 + KAPPA_EAST
    d["clears_west"] = d.spread90 > d.hurdle_west
    d["clears_east"] = d.spread90 < d.hurdle_east
    return d


def load_flows() -> pd.DataFrame:
    f = pd.read_csv(ROOT / "data/processed/bilateral_panel_2015_2026.csv",
                    parse_dates=["date"])
    che = f[(f.reporter_iso3 == "CHE") & (f.country_iso3 == "USA")]
    w = che.pivot_table(index="date", columns="flow", values="net_mass_kg",
                        aggfunc="sum") / 1000.0
    w["net_to_us"] = w["export"] - w["import"]
    return w[w.index >= "2015-01-01"]


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_spread()
    flows = load_flows()

    m = d.set_index("date")
    monthly = pd.DataFrame({
        "spread90": m.spread90.resample("MS").mean(),
        "hurdle_west": m.hurdle_west.resample("MS").mean(),
        "hurdle_east": m.hurdle_east.resample("MS").mean(),
        "carry90": m.carry90.resample("MS").mean(),
        "days_west": m.clears_west.resample("MS").sum(),
        "days_east": m.clears_east.resample("MS").sum(),
        "n_days": m.spread90.resample("MS").count(),
    })
    monthly = monthly[monthly.n_days > 0].join(flows[["net_to_us"]], how="left")

    print(f"{len(d):,} days, {len(monthly)} months")
    print(f"days clearing westward {int(d.clears_west.sum()):,} "
          f"({100*d.clears_west.mean():.1f}%), eastward "
          f"{int(d.clears_east.sum()):,} ({100*d.clears_east.mean():.1f}%)")
    got = monthly.dropna(subset=["net_to_us"])
    print(f"net flow: mean {got.net_to_us.mean():+.1f} t a month, "
          f"{int((got.net_to_us < 0).sum())} of {len(got)} months net eastward")
    for label, sub in (("months clearing west on 5+ days",
                        got[got.days_west >= 5]),
                       ("months clearing east on 5+ days",
                        got[got.days_east >= 5]),
                       ("months clearing neither", got[(got.days_west == 0)
                                                       & (got.days_east == 0)])):
        if len(sub):
            print(f"   {label:<34} n={len(sub):>3}  median net "
                  f"{sub.net_to_us.median():+7.1f} t")

    # The episode, netted. The gross series shows metal going west and then
    # stopping; the net series shows some of it coming back, which is the
    # distinction between relocation and absorption.
    ep_west = got.loc["2024-12-01":"2025-03-31", "net_to_us"]
    ep_back = got.loc["2025-04-01":"2025-08-31", "net_to_us"]
    print()
    print(f"episode  Dec 2024 - Mar 2025: {ep_west.sum():+7.1f} t net west "
          f"over {len(ep_west)} months")
    print(f"after    Apr 2025 - Aug 2025: {ep_back.sum():+7.1f} t net "
          f"over {len(ep_back)} months")
    if ep_west.sum() > 0:
        print(f"         {100*abs(min(ep_back.sum(), 0))/ep_west.sum():.0f}% of "
              f"the westward move reversed within five months")
    print("         metal that has been absorbed does not come back")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11.0, 8.2), sharex=True,
        gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.34})
    fig.patch.set_facecolor(SURFACE)

    # --- the masthead: red tab, bold headline, plain deck ------------------
    fig.text(0.030, 0.972, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.944, "Gold moves only when the spread clears the cost",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.906,
             "The estimated COMEX–London spread against carry plus "
             "shipping, and the net metal that crossed.\n"
             "Above the band the westward trade pays; below it the eastward "
             "one does",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    # --- A: the spread against the composite carry -------------------------
    style(ax1)
    ax1.plot(d.date, d.spread90, color=GREY, linewidth=0.4, alpha=0.35,
             zorder=2)
    ax1.fill_between(monthly.index, monthly.hurdle_east, monthly.hurdle_west,
                     color=GREY, alpha=0.35, zorder=3, linewidth=0,
                     label="No-trade band: carry + shipping, both directions")
    ax1.fill_between(monthly.index, monthly.hurdle_west, monthly.spread90,
                     where=monthly.spread90 > monthly.hurdle_west,
                     color=RED, alpha=0.22, zorder=4, interpolate=True)
    ax1.fill_between(monthly.index, monthly.hurdle_east, monthly.spread90,
                     where=monthly.spread90 < monthly.hurdle_east,
                     color=GREY, alpha=0.45, zorder=4, interpolate=True)
    ax1.plot(monthly.index, monthly.carry90, color=GREY, linewidth=1.5,
             zorder=5, label="Composite carry: carry to delivery + shipping")
    ax1.plot(monthly.index, monthly.spread90, color=RED, linewidth=1.8,
             zorder=6, label="Estimated spread at 90 days")
    ax1.set_ylabel("Dollars per ounce", color=SOFT, fontsize=10)
    panel_head(ax1, "The spread, and what it has to clear",
               "Dollars an ounce at a fixed ninety-day horizon; daily in the "
               "background, monthly means drawn")
    lim = float(np.ceil(monthly.spread90.abs().max() / 10) * 10) + 10
    ax1.set_ylim(min(-10, monthly.spread90.min() - 8), lim)
    leg = ax1.legend(frameon=False, fontsize=10, loc="upper left",
                     labelcolor=SOFT, handlelength=2.2, borderpad=0.2,
                     labelspacing=0.35)
    leg.set_zorder(8)
    n_out = int((d.spread90.abs() > lim).sum())
    ax1.text(0.998, 0.03,
             f"{n_out} days fall outside the frame",
             transform=ax1.transAxes, fontsize=9, color=SOFT, ha="right")

    # --- B: net metal ------------------------------------------------------
    style(ax2)
    f = monthly.dropna(subset=["net_to_us"])
    ax2.axhline(0, color=SOFT, linewidth=0.8, zorder=3)
    colours = np.where(f.net_to_us >= 0, RED, GREY)
    ax2.bar(f.index, f.net_to_us, width=22, color=colours, linewidth=0, zorder=2)
    ax2.set_ylabel("Tonnes a month", color=SOFT, fontsize=10)
    panel_head(ax2, "Net metal shipped",
               f"Switzerland to the United States, both directions netted. "
               f"Red is net west, grey net east; "
               f"{int((f.net_to_us < 0).sum())} of {len(f)} months are net east")

    src = ("Both legs are Swiss customs, HS 7108 and 7115: US export figures "
           "carry no mass, so a net series taking\n"
           "one leg from each reporter would be Swiss exports minus nothing\n"
           " \n"
           "Source: Databento GLBX.MDP3 re-timed to the LBMA auction; LBMA; "
           "Swiss Federal Office for Customs and Border Security")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.780, bottom=0.140)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"spread_vs_hurdle.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    monthly.reset_index().rename(columns={"index": "month"}).to_csv(
        OUT / "spread_vs_hurdle_monthly.csv", index=False)
    print(f"wrote {OUT / 'spread_vs_hurdle.pdf'}")


if __name__ == "__main__":
    main()
