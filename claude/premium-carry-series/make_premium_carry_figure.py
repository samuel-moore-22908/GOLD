"""
Two panels, one per reported series.

    A. the New York premium, per cent of spot  -- daily, with the monthly mean
    B. the fitted carry against two dollar rates that were never used to build it

Panel B is the sanity check in visual form. The carry line is the slope of the
daily COMEX curve fit; SOFR and the three-month bill are external series that
enter nowhere in its construction. They should move together.

Colours are slots 1-3 of the validated default categorical palette in the
dataviz skill's references/palette.md, used in fixed order and unmodified. The
skill's own validator is a node script and node is not installed on this
machine, which is exactly why the palette is taken as given rather than
invented.

Reads   claude/premium-carry-series/premium_carry_daily.csv
        claude/premium-carry-series/premium_carry_monthly.csv
Writes  claude/premium-carry-series/premium_carry.pdf  (and .png)

Run from the repo root:
    .venv/Scripts/python.exe claude/premium-carry-series/make_premium_carry_figure.py
"""
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

OUT = Path("claude/premium-carry-series")

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
SURFACE = "#fcfcfb"

# A break in the plotted line wherever the series skips more than a week, so a
# hole in the data reads as a hole rather than as a straight line drawn over it.
MAX_GAP_DAYS = 7


def with_gaps(d: pd.DataFrame, col: str,
              max_gap: int = MAX_GAP_DAYS) -> tuple[np.ndarray, np.ndarray]:
    """Insert NaNs where consecutive observations are further apart than max_gap.

    The threshold is per series: a week for the daily series, and a month and a
    half for the monthly one, where consecutive points are a month apart by
    construction and a shorter threshold would break every segment.
    """
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


def main() -> None:
    d = pd.read_csv(OUT / "premium_carry_daily.csv", parse_dates=["date"])
    m = pd.read_csv(OUT / "premium_carry_monthly.csv", parse_dates=["month"])
    m = m.rename(columns={"month": "date"})

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.4, 6.6), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.22})
    fig.patch.set_facecolor(SURFACE)

    # --- Panel A: the premium -------------------------------------------------
    # The daily series is an order of magnitude noisier than the signal in it,
    # so the frame is set to hold the monthly series and the days outside it are
    # marked at the edge and counted rather than dropped quietly.
    LIM = 2.0
    style(ax1)
    ax1.axhline(0, color=MUTED, linewidth=0.8, zorder=1)
    x, y = with_gaps(d, "premium_pct")
    ax1.plot(x, y, color=MUTED, linewidth=0.5, alpha=0.45, zorder=2,
             label="Daily")
    x, y = with_gaps(m, "premium_pct", max_gap=45)
    ax1.plot(x, y, color=BLUE, linewidth=2.2, zorder=4, label="Monthly mean",
             solid_capstyle="round")
    ax1.set_ylim(-LIM, LIM)
    ax1.set_ylabel("Per cent of spot", color=INK2, fontsize=9)
    ax1.set_title("A.  The New York premium", color=INK, fontsize=11,
                  loc="left", pad=8, fontweight="bold")
    leg = ax1.legend(frameon=False, fontsize=8.5, loc="lower left",
                     labelcolor=INK2, handlelength=1.8)
    leg.set_zorder(5)

    out = d[d.premium_pct.abs() > LIM]
    ax1.scatter(out.date, np.clip(out.premium_pct, -LIM * 0.97, LIM * 0.97),
                marker="^", s=14, color=ORANGE, zorder=3, linewidths=0)
    worst = out.loc[out.premium_pct.abs().idxmax()]
    ax1.text(0.995, 0.06,
             f"{len(out)} days outside the frame, largest "
             f"{worst.premium_pct:+.1f}% on {worst.date:%d %b %Y}",
             transform=ax1.transAxes, fontsize=7.5, color=MUTED, ha="right")

    # The two features a reader will ask about, named by date rather than cause.
    for when, text, dx, dy in (("2020-04-01", "Apr 2020", -230, 0.45),
                               ("2025-01-01", "Jan 2025", -30, 0.75)):
        t = pd.Timestamp(when)
        v = float(m.loc[m.date == t, "premium_pct"].iloc[0])
        ax1.annotate(text, xy=(t, v), xytext=(t + pd.Timedelta(days=dx), v + dy),
                     fontsize=8, color=INK2, ha="center", zorder=5,
                     arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7))

    # --- Panel B: carry against rates it never saw ----------------------------
    style(ax2)
    for col, colour, label, lw in (
            ("carry_pct", BLUE, "Fitted carry (curve slope)", 2.0),
            ("short_rate_pct", ORANGE, "SOFR / fed funds", 1.4),
            ("tbill_3m_pct", AQUA, "3-month Treasury bill", 1.4)):
        x, y = with_gaps(d, col)
        ax2.plot(x, y, color=colour, linewidth=lw, label=label,
                 alpha=1.0 if col == "carry_pct" else 0.85)
    ax2.set_ylabel("Per cent a year", color=INK2, fontsize=9)
    ax2.set_title("B.  Fitted carry, and two rates that are not in the fit",
                  color=INK, fontsize=11, loc="left", pad=8, fontweight="bold")
    ax2.legend(frameon=False, fontsize=8.5, loc="upper left", labelcolor=INK2,
               handlelength=1.8)

    r = d[["carry_pct", "short_rate_pct"]].dropna()
    note = (f"Correlation of fitted carry with SOFR "
            f"{r.carry_pct.corr(r.short_rate_pct):.2f} in levels; "
            f"slope {np.polyfit(r.short_rate_pct, r.carry_pct, 1)[0]:.2f}.")
    ax2.text(0.0, -0.20, note, transform=ax2.transAxes, fontsize=8,
             color=MUTED, ha="left")

    src = (f"COMEX settlements and open interest (Databento GLBX.MDP3), LBMA PM, FRED. "
           f"{d.date.min():%b %Y} to {d.date.max():%b %Y}, "
           f"{len(d):,} trading days.")
    fig.text(0.008, 0.012, src, fontsize=7.5, color=MUTED, ha="left")

    fig.subplots_adjust(left=0.085, right=0.985, top=0.955, bottom=0.135)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"premium_carry.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    print(f"wrote {OUT/'premium_carry.pdf'} and .png")


if __name__ == "__main__":
    main()
