#!/usr/bin/env python3
"""
The monthly US trade deficit, as reported and with the gold taken out.

The FT-900 goods-and-services balance is the number that makes the headline,
moves markets and feeds the nowcasts. Unlike GDP, it carries nonmonetary gold in
full: BEA removes gold from the national accounts, but nobody removes it from
the trade release. So the trade deficit is where the phantom flow actually lands.

The adjustment is one line. Reported balance = X - M. Take the gold out of both
sides and the balance becomes X - X_gold - (M - M_gold) = balance + net gold
imports. Metal arriving makes the deficit look bigger; the same metal leaving a
few months later makes it look smaller.

Both series are BEA's own: the balance is theirs, and the gold is subtracted
from it rather than a deficit being rebuilt from scratch, so the adjusted line
differs from the published one by exactly the gold and by nothing else.

Reads   fred.stlouisfed.org BOPGSTB                     (the FT-900 balance)
        data/processed/us_hs4_universe_monthly.csv      (Census HS 7108 + 7115)
Writes  claude/deficit-gold-adjusted/deficit_gold_monthly.csv
        claude/deficit-gold-adjusted/deficit_gold.pdf and .png
        claude/deficit-gold-adjusted/build_deficit_gold_output.txt

Run from anywhere:
    python claude/deficit-gold-adjusted/build_deficit_gold.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
CACHE_DIR = "data/raw/fred_cache"     # relative to the repo root
# ============================================================================

# Both headings, because the bars went in under 7115 over the winter of 2024-25
# and 7108 alone would miss the episode. BEA reclassifies 7115900530 as
# nonmonetary gold on a BOP basis, so the pair is the right match to the
# concept the balance is built on.
HS_GOLD = (7108, 7115)
ROLL = 12             # months in the rolling total
REQUEST_SPACING_S = 1.5

import io
import os
import subprocess
import time
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
OUT = ROOT / "claude/deficit-gold-adjusted"
CACHE = ROOT / CACHE_DIR

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]
mpl.rcParams["text.parse_math"] = False

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


def fred(series_id: str) -> pd.Series:
    """Any FRED series, via the keyless CSV endpoint, cached on first fetch."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"fred_{series_id}.csv"
    if not path.exists():
        time.sleep(REQUEST_SPACING_S)
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except Exception:
            body = subprocess.run(
                ["curl", "-sS", "-m", "90", "-A", "GOLD-research/1.0", url],
                check=True, capture_output=True).stdout
        if not body:
            raise RuntimeError(f"empty response for {series_id}")
        path.write_bytes(body)
    d = pd.read_csv(io.BytesIO(path.read_bytes()))
    d.columns = ["date", series_id]
    d["date"] = pd.to_datetime(d.date)
    return pd.to_numeric(d.set_index("date")[series_id], errors="coerce").dropna()


def build() -> tuple[pd.DataFrame, pd.Series]:
    heading("THE TRADE DEFICIT, REPORTED AND WITH THE GOLD TAKEN OUT")
    balance = fred("BOPGSTB") / 1000.0          # $mn -> $bn, negative = deficit
    note(f"   BOPGSTB, the FT-900 goods-and-services balance, {len(balance)} months,")
    note(f"   {balance.index[0]:%b %Y} to {balance.index[-1]:%b %Y}. Negative is a deficit.")

    u = pd.read_csv(ROOT / "data/processed/us_hs4_universe_monthly.csv",
                    parse_dates=["date"])
    g = u[u.hs4.isin(HS_GOLD)].pivot_table(index="date", columns="flow",
                                           values="value_usd", aggfunc="sum") / 1e9
    net_gold = (g["imports"] - g["exports"]).rename("net_gold")
    note(f"   Gold covers {len(net_gold)} months, {net_gold.index[0]:%b %Y} to "
         f"{net_gold.index[-1]:%b %Y}, all partners.")

    d = pd.DataFrame({"reported": balance.reindex(net_gold.index),
                      "net_gold": net_gold}).dropna()
    d["adjusted"] = d.reported + d.net_gold
    d["deficit"] = -d.reported
    d["deficit_adj"] = -d.adjusted
    d["gold_share_pct"] = 100 * d.net_gold / d.deficit
    return d, -balance


def narrate(d: pd.DataFrame, deficit_all: pd.Series) -> None:
    heading("STEP 1  The months everyone reacted to")
    note("   The three largest monthly deficits ever recorded, and the smallest")
    note("   in six years, all fall inside this episode. Here they are with the")
    note("   gold taken out:")
    note("")
    note(f"   {'month':>10}{'reported':>11}{'gold':>9}{'adjusted':>11}{'gold %':>9}")
    note("   " + "-" * 50)
    worst = d.deficit.nlargest(3).index.tolist() + [d.deficit.idxmin()]
    for m in sorted(worst):
        r = d.loc[m]
        note(f"   {m:%Y-%m}{r.deficit:>11.1f}{r.net_gold:>9.1f}"
             f"{r.deficit_adj:>11.1f}{r.gold_share_pct:>9.1f}")
    note("")
    top = deficit_all.nlargest(3)
    note(f"   On the reported series the record book reads {top.index[0]:%b %Y}, "
         f"{top.index[1]:%b %Y}")
    note(f"   and {top.index[2]:%b %Y} - the top three deficits since the series")
    note("   begins in 1992, consecutive, all in the episode.")
    note("")
    pre = deficit_all[:"2023-09-01"].max()
    pre_m = deficit_all[:"2023-09-01"].idxmax()
    still = [m for m in d.deficit_adj.nlargest(3).index if d.deficit_adj[m] > pre]
    note(f"   Adjusted, only {len(still)} of those three still clears the pre-episode")
    note(f"   record of ${pre:.1f}bn in {pre_m:%b %Y}: "
         f"{', '.join(f'{m:%b %Y}' for m in sorted(still))}.")
    note("   Two of the three record months were records because of metal that")
    note("   was in a vault in London in the morning and a vault in New York by")
    note("   the evening.")
    note("")
    note("   That comparison uses unadjusted figures before October 2023, which")
    note("   is where the gold series starts. Monthly net gold ran between -$3bn")
    note("   and +$2bn in the year before the episode, so it is indicative rather")
    note("   than exact, and the direction is not in doubt.")

    heading("STEP 2  The month the deficit 'collapsed'")
    oct25 = d.loc[pd.Timestamp("2025-10-01")]
    prior = deficit_all[:"2025-09-01"]
    last = prior[prior <= oct25.deficit].index[-1]
    note(f"   October 2025 printed a deficit of ${oct25.deficit:.1f}bn, the smallest since")
    note(f"   {last:%B %Y} and widely read as a structural improvement.")
    note(f"   With the gold put back it is ${oct25.deficit_adj:.1f}bn. "
         f"{abs(oct25.gold_share_pct):.0f}% of the")
    note("   'improvement' was bullion leaving the country.")
    note("")
    note("   This is the symmetry that matters. The same mechanism that produced")
    note("   three record deficits produced, seven months later, the best trade")
    note("   month in six years. Neither was trade.")

    heading("STEP 3  It does not net out quickly")
    gap = d.net_gold.rolling(ROLL).sum().dropna()
    r12 = -d.reported.rolling(ROLL).sum()
    peak, peak_m = gap.max(), gap.idxmax()
    note("   A round trip nets to nothing eventually. The question is how long")
    note("   'eventually' takes, and the answer is longer than a year - so the")
    note(f"   annual deficit was wrong too, not just the monthly one.")
    note("")
    note(f"   Rolling {ROLL}-month deficit, overstatement from gold:")
    note("")
    note(f"      peak        ${peak:,.0f}bn in {peak_m:%B %Y}, "
         f"{100 * peak / r12[peak_m]:.1f}% of the trailing-year deficit")
    note(f"      latest      ${gap.iloc[-1]:,.0f}bn in {gap.index[-1]:%B %Y}, "
         f"{100 * gap.iloc[-1] / r12.iloc[-1]:.1f}%")
    note("")
    surge = pd.Timestamp("2024-12-01")
    months = (gap.index[-1].year - surge.year) * 12 + gap.index[-1].month - surge.month
    note(f"   At the March 2025 peak every tonne had gone in and none had come")
    note(f"   back, so a full year of data carried the whole surge and none of the")
    note(f"   reversal. {months} months after the metal started moving the twelve-month")
    note(f"   deficit was STILL overstated by ${gap.iloc[-1]:,.0f}bn, and the series ends there")
    note("   rather than at zero.")
    note("")
    note("   So the reassuring version of this - 'it nets out over a year, only")
    note("   the monthly print was distorted' - is wrong, and it is worth saying")
    note("   plainly because it is the first thing anyone reaches for. For most")
    note("   of 2025 the twelve-month deficit was overstated by tens of billions.")
    note("")
    sd_r, sd_a = d.deficit.std(), d.deficit_adj.std()
    note(f"   The monthly series is distorted in a second way that survives any")
    note(f"   netting - how volatile the trade balance appeared to be. Standard")
    note(f"   deviation of the monthly deficit over these {len(d)} months:")
    note(f"      reported   ${sd_r:.1f}bn")
    note(f"      adjusted   ${sd_a:.1f}bn")
    note(f"   Taking the gold out cuts it by {100 * (1 - sd_a / sd_r):.0f}%. Range high to low: "
         f"reported ${d.deficit.max() - d.deficit.min():.0f}bn,")
    note(f"   adjusted ${d.deficit_adj.max() - d.deficit_adj.min():.0f}bn.")

    heading("WHAT THIS MEANS FOR HOW THE DEFICIT WAS READ")
    note("   Nothing here is a claim that BEA published a wrong number. The gold")
    note("   crossed the border and the balance of payments is supposed to record")
    note("   goods crossing borders. The point is narrower and harder to dismiss:")
    note("")
    note("   a reader of the monthly release in early 2025 saw a deficit")
    note("   exploding to successive records, and in late 2025 saw it collapsing")
    note("   to a six-year low. Neither movement was a change in what America")
    note("   buys or sells. It was one pile of metal moving to a different vault")
    note("   and then moving back, and the reader had no way to see that from the")
    note("   headline figure.")
    note("")
    note("   BEA already takes this view for GDP: nonmonetary gold is removed")
    note("   from the national accounts because a bar bought as a store of value")
    note("   is not consumption or investment. The trade release applies no such")
    note("   filter, so the same metal is excluded from one official statistic")
    note("   and headlined in another.")


def figure(d: pd.DataFrame) -> None:
    """One panel: the monthly deficit, as published and with the gold removed.

    The rolling twelve-month comparison lives in step 3 of the narration rather
    than here. It is a separate claim on a different axis, and putting it in a
    second panel made the figure argue two things at once.
    """
    fig, ax = plt.subplots(figsize=(11.0, 6.2))
    fig.patch.set_facecolor(SURFACE)

    jan = d.loc[pd.Timestamp("2025-01-01")]
    oct25 = d.loc[pd.Timestamp("2025-10-01")]
    fig.text(0.030, 0.968, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.928,
             "The record deficits, and the collapse that followed, were both "
             "largely bullion",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.880,
             f"US goods and services deficit as published each month, and with "
             f"nonmonetary gold taken out of both sides. Gold is "
             f"{jan.gold_share_pct:.0f}% of the\n"
             f"January 2025 record and {abs(oct25.gold_share_pct):.0f}% of "
             f"October 2025, the smallest deficit in six years",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="y", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=10, length=0)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    ax.fill_between(d.index, d.deficit_adj, d.deficit,
                    where=d.deficit >= d.deficit_adj, color=RED, alpha=0.20,
                    interpolate=True, zorder=1)
    ax.fill_between(d.index, d.deficit_adj, d.deficit,
                    where=d.deficit < d.deficit_adj, color=GREY, alpha=0.32,
                    interpolate=True, zorder=1)
    ax.plot(d.index, d.deficit, color=RED, linewidth=2.4, zorder=4,
            label="As published")
    ax.plot(d.index, d.deficit_adj, color=INK, linewidth=1.9, zorder=5,
            linestyle=(0, (5, 2)), label="With nonmonetary gold removed")
    ax.set_ylabel("Monthly deficit, $bn", color=SOFT, fontsize=11)
    ax.set_ylim(0, d.deficit.max() * 1.20)
    leg = ax.legend(frameon=False, fontsize=11, loc="upper left",
                    handlelength=1.8, borderaxespad=0.6)
    for t in leg.get_texts():
        t.set_color(INK)

    ax.annotate(f"${jan.deficit:.0f}bn reported\n${jan.deficit_adj:.0f}bn without the gold",
                xy=(pd.Timestamp("2025-01-01"), jan.deficit),
                xytext=(pd.Timestamp("2023-11-20"), jan.deficit * 0.88),
                fontsize=10.5, color=INK, ha="left", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=SOFT, linewidth=0.9))
    ax.annotate(f"${oct25.deficit:.0f}bn reported\n${oct25.deficit_adj:.0f}bn without the gold",
                xy=(pd.Timestamp("2025-10-01"), oct25.deficit),
                xytext=(pd.Timestamp("2025-01-20"), 16),
                fontsize=10.5, color=INK, ha="left", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=SOFT, linewidth=0.9))

    gap = d.net_gold.rolling(ROLL).sum()
    src_note = (f"The published balance is BEA and Census, FT-900, goods and "
                f"services, balance-of-payments basis. Gold is US imports minus "
                f"exports of HS 7108 and 7115, all\n"
                f"partners, and is subtracted from both sides of that same "
                f"balance, so the two lines differ by the gold and by nothing "
                f"else. It nets out only slowly: the rolling\n"
                f"twelve-month deficit was overstated by ${gap.max():,.0f}bn at its worst "
                f"in {gap.idxmax():%B %Y}. The gold series starts in October "
                f"2023, where the customs pull starts\n"
                " \n"
                "Source: US Census Bureau; Bureau of Economic Analysis")
    fig.text(0.030, 0.012, src_note, fontsize=9, color=SOFT, ha="left",
             va="bottom", linespacing=1.35)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.755, bottom=0.240)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"deficit_gold.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    note("")
    note(f"   wrote {OUT / 'deficit_gold.pdf'}")


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    d, deficit_all = build()
    narrate(d, deficit_all)
    figure(d)
    d.round(4).to_csv(OUT / "deficit_gold_monthly.csv", index_label="month")
    (OUT / "build_deficit_gold_output.txt").write_text(
        "\n".join(LOG) + "\n", encoding="utf-8")
    note(f"   wrote {OUT / 'deficit_gold_monthly.csv'}")


if __name__ == "__main__":
    main()
