"""
Static paper figure: the three-phase path on the trade-balance plane.

Matplotlib counterpart of scatter_phase_path.html, following the conventions in
src/make_paper_figures.py so it sits alongside the other paper figures rather
than looking like it came from somewhere else.

Reads   claude/inflow-scatter/phase_path_points.csv
Writes  claude/inflow-scatter/figures/phase_path.{pdf,png}
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SRC = Path("claude/inflow-scatter/phase_path_points.csv")
FIG = Path("claude/inflow-scatter/figures")
FIG.mkdir(parents=True, exist_ok=True)
GOLD = "7108+7115"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False,
})

INK, ACCENT, MUTED = "#1a1a1a", "#b5482a", "#7a8b99"
PHASES = ["baseline\nNov 23–Oct 24", "surge\nNov 24–Mar 25",
          "reversal\nApr–Nov 25"]


def main():
    d = pd.read_csv(SRC)
    # phase_path_points.csv stores raw dollars per month; convert to $bn.
    cols = [("m_baseline", "x_baseline"), ("m_surge", "x_surge"),
            ("m_reversal", "x_reversal")]
    for m, x in cols:
        d[m] = d[m] / 1e9
        d[x] = d[x] / 1e9

    g = d[d.hs4 == GOLD].iloc[0]
    others = d[d.hs4 != GOLD]

    fig, ax = plt.subplots(figsize=(7.2, 6.4))

    # Balance diagonal. Everything above it is import-dominated.
    lo = min(d[[c for p in cols for c in p]].min()) * 0.6
    hi = max(d[[c for p in cols for c in p]].max()) * 1.7
    ax.plot([lo, hi], [lo, hi], ls="--", lw=1.1, color=INK, alpha=0.45, zorder=1)
    ax.text(hi * 0.42, hi * 0.46, "M = X", fontsize=8, color=INK, alpha=0.6,
            ha="right", va="bottom", rotation=45, rotation_mode="anchor")

    # The other 99 headings, faint. Each is two segments, drawn once so the
    # legend does not repeat.
    for _, r in others.iterrows():
        xs = [r[x] for _, x in cols]
        ys = [r[m] for m, _ in cols]
        ax.plot(xs, ys, "-", lw=0.7, color=MUTED, alpha=0.35, zorder=2)
        ax.plot(xs[0], ys[0], "o", ms=2.0, mfc="white", mec=MUTED,
                mew=0.6, alpha=0.5, zorder=2)
        ax.plot(xs[-1], ys[-1], "o", ms=2.6, color=MUTED, alpha=0.5, zorder=2)

    # Gold, with an arrowhead on each leg so the direction of travel is
    # unambiguous - the whole point of the figure is that it doubles back.
    gx = [g[x] for _, x in cols]
    gy = [g[m] for m, _ in cols]
    for i in range(2):
        ax.annotate("", xy=(gx[i + 1], gy[i + 1]), xytext=(gx[i], gy[i]),
                    arrowprops=dict(arrowstyle="-|>", lw=2.0, color=ACCENT,
                                    shrinkA=4, shrinkB=6), zorder=5)
    ax.plot(gx[0], gy[0], "o", ms=8, mfc="white", mec=ACCENT, mew=2.0, zorder=6)
    ax.plot(gx[1], gy[1], "o", ms=8, mfc=ACCENT, mec="white", mew=1.2,
            alpha=0.65, zorder=6)
    ax.plot(gx[2], gy[2], "o", ms=10, color=ACCENT, mec="white", mew=1.2, zorder=6)

    # ha is set per label so the surge text sits left of its point,
    # clear of the M = X annotation on the diagonal.
    offs = [(-16, -22), (-14, 2), (14, -12)]
    align = ["left", "right", "left"]
    for (px, py), lab, off, ha in zip(zip(gx, gy), PHASES, offs, align):
        ax.annotate(lab, (px, py), textcoords="offset points", xytext=off,
                    fontsize=7.5, color=ACCENT, ha=ha, va="center",
                    linespacing=1.25)
    ax.annotate("GOLD\nHS 7108 + 7115", (gx[1], gy[1]), textcoords="offset points",
                xytext=(16, 26), fontsize=9.5, fontweight="bold", color=ACCENT,
                linespacing=1.2)

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("US exports, $bn per month")
    ax.set_ylabel("US imports, $bn per month")
    ax.set_title("Gold went in, then came back out", loc="left",
                 fontsize=11, pad=26)
    ax.text(0, 1.035, "100 most-traded HS4 headings, three phases each. "
            "Above the diagonal a heading is import-dominated.",
            transform=ax.transAxes, fontsize=8, color="#555", va="bottom")

    # Regions, named rather than left for the reader to infer.
    ax.text(0.03, 0.955, "import-dominated", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55)
    ax.text(0.97, 0.035, "export-dominated", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55, ha="right")

    handles = [
        plt.Line2D([], [], marker="o", ls="none", mfc="white", mec=ACCENT,
                   mew=1.6, ms=7, label="baseline"),
        plt.Line2D([], [], marker="o", ls="none", color=ACCENT, alpha=0.65,
                   ms=7, label="surge"),
        plt.Line2D([], [], marker="o", ls="none", color=ACCENT, ms=8,
                   label="reversal"),
        plt.Line2D([], [], color=MUTED, lw=1.1, alpha=0.6,
                   label="other headings"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8, ncol=2,
              handletextpad=0.5, columnspacing=1.4)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"phase_path.{ext}", bbox_inches="tight")
    plt.close(fig)

    print(f"  gold  baseline ({gx[0]:.2f}, {gy[0]:.2f})  "
          f"surge ({gx[1]:.2f}, {gy[1]:.2f})  reversal ({gx[2]:.2f}, {gy[2]:.2f})")
    print(f"  amplitude {g.amp:.2f}, retrace {g.retrace:.2f}x, rank #{int(g['rank'])}")
    print(f"  wrote {FIG}/phase_path.pdf and .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
