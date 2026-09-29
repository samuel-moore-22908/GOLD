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

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"


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
        2, 1, figsize=(7.4, 7.0), sharex=True,
        gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.20})
    fig.patch.set_facecolor(SURFACE)

    # --- A: the spread against the composite carry -------------------------
    style(ax1)
    ax1.plot(d.date, d.spread90, color=MUTED, linewidth=0.4, alpha=0.45,
             zorder=2)
    ax1.fill_between(monthly.index, monthly.hurdle_east, monthly.hurdle_west,
                     color=MUTED, alpha=0.30, zorder=3, linewidth=0,
                     label="No-trade band: carry + shipping, both directions")
    ax1.fill_between(monthly.index, monthly.hurdle_west, monthly.spread90,
                     where=monthly.spread90 > monthly.hurdle_west,
                     color=BLUE, alpha=0.30, zorder=4, interpolate=True)
    ax1.fill_between(monthly.index, monthly.hurdle_east, monthly.spread90,
                     where=monthly.spread90 < monthly.hurdle_east,
                     color=ORANGE, alpha=0.30, zorder=4, interpolate=True)
    ax1.plot(monthly.index, monthly.carry90, color=AQUA, linewidth=1.6,
             zorder=5, label="Composite carry: carry to delivery + shipping")
    ax1.plot(monthly.index, monthly.spread90, color=BLUE, linewidth=2.0,
             zorder=6, label="Estimated spread at 90 days")
    ax1.set_ylabel("Dollars per ounce", color=INK2, fontsize=9)
    ax1.set_title("A.  The estimated spread against the cost it has to clear",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    lim = float(np.ceil(monthly.spread90.abs().max() / 10) * 10) + 10
    ax1.set_ylim(min(-10, monthly.spread90.min() - 8), lim)
    ax1.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2,
               handlelength=1.8)
    n_out = int((d.spread90.abs() > lim).sum())
    ax1.text(0.995, 0.03,
             f"daily in grey, {n_out} days outside the frame  ·  blue where the "
             f"westward trade pays, orange where the eastward one does",
             transform=ax1.transAxes, fontsize=7.5, color=MUTED, ha="right")

    # --- B: net metal ------------------------------------------------------
    style(ax2)
    f = monthly.dropna(subset=["net_to_us"])
    ax2.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    colours = np.where(f.net_to_us >= 0, BLUE, ORANGE)
    ax2.bar(f.index, f.net_to_us, width=22, color=colours, linewidth=0, zorder=2)
    ax2.set_ylabel("Tonnes a month", color=INK2, fontsize=9)
    ax2.set_title("B.  Net metal: Switzerland to the United States, "
                  "both directions netted",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    ax2.text(0.008, 0.94,
             f"above zero: net west  ·  below: net east  ·  "
             f"{int((f.net_to_us < 0).sum())} of {len(f)} months are net east",
             transform=ax2.transAxes, fontsize=7.5, color=MUTED, ha="left",
             va="top")

    src = ("Spread and carry from the fitted COMEX curve re-timed to the LBMA "
           "auction; shipping estimated from the flows.\n"
           "Tonnes: Swiss customs, HS 7108 and 7115, both directions netted.")
    fig.text(0.008, 0.010, src, fontsize=7, color=MUTED, ha="left", va="bottom")
    fig.subplots_adjust(left=0.085, right=0.985, top=0.955, bottom=0.115)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"spread_vs_hurdle.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    monthly.reset_index().rename(columns={"index": "month"}).to_csv(
        OUT / "spread_vs_hurdle_monthly.csv", index=False)
    print(f"wrote {OUT / 'spread_vs_hurdle.pdf'}")


if __name__ == "__main__":
    main()
