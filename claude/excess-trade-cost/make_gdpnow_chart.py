#!/usr/bin/env python3
"""
GDPNow for 2025Q1, standard against the Atlanta Fed's own gold-adjusted model.

The nowcast is the cleanest place to see a phantom flow move an official
number, because a nowcast has to commit to a reading every few days and cannot
wait for the offsetting entry. On 26 February 2025 GDPNow had 2025Q1 growing at
2.3%. Two data releases later it had the economy shrinking at 2.8%. The Atlanta
Fed then built a second model that strips gold out of the trade data it
extrapolates from, ran the two side by side from 6 March, and on 30 April made
the gold-adjusted version the standard one.

Both paths come from the Atlanta Fed's own published workbook, so this chart is
their numbers, not a reconstruction of them.

WHAT THE TWO ADJUSTMENTS ARE, because they are not the same object:

  Atlanta Fed   subtracts gold imports and exports from the BOP goods
                aggregates the bridge equations are fitted and forecast on, so
                a one-off gold spike is not extrapolated into the months of the
                quarter that have not been observed yet. Observed gold still
                enters GDP. It is a fix to the FORECAST, not to the accounting.

  This project  removes the arithmetic contribution of net gold trade from
                measured GDP growth outright, assuming nothing offsets it. That
                is a bigger cut, and it answers a different question: not "what
                should the nowcast have said" but "how much of the number is
                metal moving between vaults".

Reads   atlantafed.org GDPTrackingModelDataAndForecasts.xlsx  (cached)
        claude/excess-trade-cost/gdp_effect_quarterly.csv
Writes  claude/excess-trade-cost/gdpnow_gold.pdf and .png
        claude/excess-trade-cost/gdpnow_gold_daily.csv

Run from anywhere:
    python claude/excess-trade-cost/make_gdpnow_chart.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
CACHE_DIR = "data/raw/atlanta_fed"          # relative to the repo root
# ============================================================================

XLSX_URL = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
            "research-and-data/data/gdpnow/GDPTrackingModelDataAndForecasts.xlsx")
QUARTER = "2025-03-31"          # the quarter being nowcast
STD_SHEET = "TrackingArchives"
GOLD_SHEET = "25Q1TrackingHistoryGold"
GOLD_ROW = 30                   # the "GDP Nowcast" row in that sheet
# Real GDP growth for the quarter as published now, after revisions. Left here
# rather than refetched because the chart needs one number and the series it
# comes from is already pulled by build_gdp_effect.py.
PUBLISHED_NOW = 0.14

import os
import subprocess
import urllib.request
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
CACHE = ROOT / CACHE_DIR

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]
mpl.rcParams["text.parse_math"] = False


def workbook() -> Path:
    """The Atlanta Fed's tracking workbook, fetched once and kept."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "GDPTrackingModelDataAndForecasts.xlsx"
    if path.exists():
        return path
    print(f"fetching {XLSX_URL}", flush=True)
    try:
        req = urllib.request.Request(
            XLSX_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except Exception:
        body = subprocess.run(
            ["curl", "-sS", "-m", "180", "-L", "-A",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", XLSX_URL],
            check=True, capture_output=True).stdout
    if not body.startswith(b"PK"):
        raise SystemExit("the download is not an xlsx - the Atlanta Fed moved "
                         "the file again. Find the new link on "
                         "atlantafed.org/cqer/research/gdpnow and update XLSX_URL.")
    path.write_bytes(body)
    return path


def paths() -> pd.DataFrame:
    xl = workbook()
    std = pd.read_excel(xl, sheet_name=STD_SHEET, header=0)
    std["Forecast Date"] = pd.to_datetime(std["Forecast Date"])
    std["Quarter being forecasted"] = pd.to_datetime(std["Quarter being forecasted"])
    std = std[std["Quarter being forecasted"] == QUARTER]
    advance = float(std["Advance Estimate From BEA"].dropna().iloc[0])
    std = std.set_index("Forecast Date")["GDP Nowcast"].astype(float)

    g = pd.read_excel(xl, sheet_name=GOLD_SHEET, header=None)
    # The sheet's own title row says 2025q2; the sheet name, the vintage dates
    # and the advance-estimate date all say 2025q1. The title is stale.
    gold = pd.Series(pd.to_numeric(g.iloc[GOLD_ROW, 2:].values, errors="coerce"),
                     index=pd.to_datetime(g.iloc[0, 2:].tolist())).dropna()

    d = pd.DataFrame({"standard": std, "gold_adjusted": gold}).sort_index()
    d["wedge"] = d.gold_adjusted - d.standard
    d.attrs["advance"] = advance
    return d


def main() -> None:
    os.chdir(ROOT)
    d = paths()
    advance = d.attrs["advance"]

    q = pd.read_csv(OUT / "gdp_effect_quarterly.csv", parse_dates=["quarter"],
                    index_col="quarter")
    own = float(q.loc[pd.Timestamp("2025-01-01"), "gold_contrib_pp"])

    both = d.dropna()
    print(f"standard   {len(d.standard.dropna())} vintages, "
          f"{d.standard.dropna().index[0]:%d %b} to {d.standard.dropna().index[-1]:%d %b %Y}, "
          f"final {d.standard.dropna().iloc[-1]:+.2f}%")
    print(f"gold-adj   {len(d.gold_adjusted.dropna())} vintages, "
          f"final {d.gold_adjusted.dropna().iloc[-1]:+.2f}%")
    print(f"wedge      max {both.wedge.max():+.2f}pp on "
          f"{both.wedge.idxmax():%d %b}, final {both.wedge.iloc[-1]:+.2f}pp")
    print(f"outturn    advance {advance:+.2f}%, now published {PUBLISHED_NOW:+.2f}%")
    print(f"this project's accounting term for 2025Q1: {own:+.2f}pp")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.0, 7.8), sharex=True,
                                   gridspec_kw={"height_ratios": [2.15, 1.0]})
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.030, 0.972, TAB, fontsize=11, color=RED, ha="left", va="top")
    march = d.gold_adjusted.dropna().loc["2025-03-01":"2025-03-31"]
    fig.text(0.030, 0.938,
             f"Stripping the gold out moved the nowcast by about "
             f"{both.wedge.median():.0f} points, for two months",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.897,
             f"GDPNow for 2025Q1, every vintage. The standard model fell from "
             f"{d.standard.dropna().loc['2025-02-26']:+.1f}% to "
             f"{d.standard.dropna().loc['2025-03-03']:+.1f}% in three working "
             "days, on two trade releases.\n"
             "The Atlanta Fed's gold-adjusted model, run alongside it from "
             f"6 March and made the standard model on 30 April, spent March "
             f"between {march.min():+.1f}% and {march.max():+.1f}%",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        for side in ax.spines:
            ax.spines[side].set_visible(False)
        ax.grid(True, axis="y", color=RULE, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=SOFT, labelsize=10, length=0)
        ax.axhline(0, color=SOFT, linewidth=0.9)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_minor_locator(mdates.DayLocator(bymonthday=(15,)))

    s, g = d.standard.dropna(), d.gold_adjusted.dropna()
    ax1.fill_between(both.index, both.standard, both.gold_adjusted,
                     color=RED, alpha=0.13, zorder=1)
    ax1.plot(s.index, s.values, color=GREY, linewidth=2.2, zorder=3,
             marker="o", markersize=3.4,
             label="GDPNow, standard model")
    ax1.plot(g.index, g.values, color=RED, linewidth=2.2, zorder=4,
             marker="o", markersize=3.4,
             label="GDPNow, gold-adjusted model")
    ax1.axhline(PUBLISHED_NOW, color=INK, linewidth=1.0, linestyle=(0, (4, 3)),
                zorder=2)
    ax1.annotate(f"what 2025Q1 actually did: {PUBLISHED_NOW:+.1f}%",
                 xy=(s.index[3], PUBLISHED_NOW + 0.16), fontsize=10, color=INK,
                 ha="left", va="bottom")
    ax1.set_ylabel("Annualised real GDP growth, %", color=SOFT, fontsize=11)
    leg = ax1.legend(frameon=False, fontsize=11, loc="lower left",
                     handlelength=1.6, borderaxespad=0.4)
    for t in leg.get_texts():
        t.set_color(INK)

    worst = s.idxmin()
    ax1.annotate(f"trough {s.min():.1f}%", xy=(worst, s.min()),
                 xytext=(worst + pd.Timedelta(days=4), s.min() - 0.02),
                 fontsize=10.5, color=GREY, ha="left", va="center",
                 fontweight="bold")

    ax2.fill_between(both.index, 0, both.wedge, color=RED, alpha=0.22)
    ax2.plot(both.index, both.wedge, color=RED, linewidth=1.8, marker="o",
             markersize=3.0)
    ax2.axhline(-own, color=INK, linewidth=1.1, linestyle=(0, (2, 2)))
    ax2.annotate(f"this project's accounting term, {-own:.1f}pp",
                 xy=(both.index[1], -own + 0.08), fontsize=10, color=INK,
                 ha="left", va="bottom")
    ax2.set_ylabel("The gold wedge, pp", color=SOFT, fontsize=11)
    ax2.set_ylim(0, max(both.wedge.max(), -own) + 0.55)

    src = ("The wedge is the gold-adjusted nowcast minus the standard one. The "
           "two adjustments are not the same object: the Atlanta Fed strips gold "
           "out of the trade data its\n"
           "bridge equations extrapolate from, so an unrepeatable spike is not "
           "carried into the unobserved months, while observed gold still enters "
           "GDP; this project removes the\n"
           "arithmetic contribution of net gold trade outright. The second is the "
           "larger cut and answers the different question of how much of the "
           "number is metal moving between vaults\n"
           " \n"
           "Source: Federal Reserve Bank of Atlanta, GDPNow tracking workbook; "
           "Bureau of Economic Analysis")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.078, right=0.985, top=0.800, bottom=0.205, hspace=0.14)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"gdpnow_gold.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    d.round(4).to_csv(OUT / "gdpnow_gold_daily.csv", index_label="vintage")
    print(f"wrote {OUT / 'gdpnow_gold.pdf'}")


if __name__ == "__main__":
    main()
