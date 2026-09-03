"""
Three-phase path on the trade-balance plane, gold only, one path per partner.

Same construction as claude/inflow-scatter, but the unit of observation is a
*country* rather than a commodity: within HS 7108 + 7115, where did each
partner sit before the episode, during the inflow, and after it turned.

The commodity figure establishes that gold went in and came back out. This one
answers the question that follows - through whom - and the answer is legible
without arithmetic: Switzerland traces a hook of its own while most partners
sit still.

Reads   transfer/raw/gold_panel_top50.parquet   (HS6, bilateral, monthly)
        transfer/raw/gold_partners_top50.csv    (partner names, ch71 ranking)
Writes  claude/gold-partner-path/figures/gold_partner_path.{pdf,png}
        claude/gold-partner-path/gold_partner_points.csv

Note transfer/raw is gitignored, so the inputs are local-only and this script
will not run on a fresh clone until that pull is rerun.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PANEL = Path("transfer/raw/gold_panel_top50.parquet")
NAMES = Path("transfer/raw/gold_partners_top50.csv")
OUT = Path("claude/gold-partner-path")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# Same split as the commodity figure, and the same reason: the phases are
# 12/5/8 months, so everything is a monthly-average rate.
PHASES = {"baseline": ("2023-11", "2024-10"),
          "surge":    ("2024-11", "2025-03"),
          "reversal": ("2025-04", "2025-11")}
MONTHS = {"baseline": 12, "surge": 5, "reversal": 8}
HIGHLIGHT = "Switzerland"

# A partner needs at least this much trade in *both* directions in *every*
# phase to have a position on a log-log plane. Below it the coordinate is
# rounding noise, and including such partners stretched the axes across seven
# decades and squashed the entire episode into one corner.
#
# The exclusion is substantive, not cosmetic: South Africa and Hong Kong trade
# gold with the US in one direction only, so they have no position here at all.
# They are named beneath the figure rather than silently dropped.
LEG_FLOOR = 0.001          # $1m per month

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False,
})
INK, ACCENT, MUTED = "#1a1a1a", "#b5482a", "#7a8b99"


def load():
    p = pd.read_parquet(PANEL)
    # One code column and one value column: the API names them differently per
    # flow, and the pull kept both sets side by side.
    p["code"] = p["I_COMMODITY"].fillna(p["E_COMMODITY"]).astype(str)
    p["val"] = p["GEN_VAL_MO"].fillna(p["ALL_VAL_MO"])
    p = p[p["code"].str.startswith(("7108", "7115"))].copy()

    # CTY_CODE arrives as a zero-padded string; the name file stores it as an
    # integer, so joining them raw silently produces all-missing names.
    nm = pd.read_csv(NAMES)
    nm["k"] = nm["cty_code"].astype(str).str.zfill(4)
    p["k"] = p["CTY_CODE"].astype(str).str.zfill(4)

    def phase(t):
        for name, (lo, hi) in PHASES.items():
            if lo <= t <= hi:
                return name
        return None

    p["phase"] = p["time"].map(phase)
    p = p.dropna(subset=["phase"])

    w = (p.pivot_table(index="k", columns=["phase", "flow"], values="val",
                       aggfunc="sum")
           .fillna(0.0))
    for ph in PHASES:
        for fl in ("imports", "exports"):
            if (ph, fl) in w.columns:
                w[(ph, fl)] = w[(ph, fl)] / MONTHS[ph] / 1e9
            else:
                w[(ph, fl)] = 0.0
    w.columns = [f"{f[0]}_{'m' if f[1] == 'imports' else 'x'}" for f in w.columns]
    w = w.join(nm.set_index("k")[["cty_name", "rank_ch71"]])
    return w.reset_index()


def main():
    d = load()
    cols = [(f"{p}_m", f"{p}_x") for p in PHASES]
    flat = [c for pair in cols for c in pair]

    n_all = len(d)
    # Both axes are logged, so a partner needs positive trade in both
    # directions in all three phases. Dropping is honest here: a country that
    # exported nothing to the US in a phase has no position on this plane,
    # and flooring it at an arbitrary epsilon would invent one.
    keep = (d[flat] >= LEG_FLOOR).all(axis=1)
    # Anyone excluded who nonetheless moved real metal during the surge is
    # worth naming: they are one-directional corridors, not small ones.
    cut = d.loc[~keep].copy()
    cut["swing"] = cut["surge_m"] - cut["baseline_m"]
    oneway = cut[cut["swing"] >= 0.05].sort_values("swing", ascending=False)
    d = d[keep].copy()
    print(f"  {n_all} partners -> {len(d)} plottable at a "
          f"${LEG_FLOOR*1000:.0f}m/month per-leg floor")
    print("  excluded but material (one-directional corridors):")
    for _, r in oneway.iterrows():
        print(f"    {str(r['cty_name'])[:24]:26} imports {r.baseline_m:5.2f} -> "
              f"{r.surge_m:5.2f} -> {r.reversal_m:5.2f}   exports "
              f"{r.baseline_x:.3f} -> {r.surge_x:.3f} -> {r.reversal_x:.3f}")

    lg = lambda a, b: np.hypot(np.log10(d[a[0]] / d[b[0]]),
                               np.log10(d[a[1]] / d[b[1]]))
    d["out"] = lg(cols[1], cols[0])
    d["back"] = lg(cols[2], cols[1])
    d["net"] = lg(cols[2], cols[0])
    d["amp"] = np.minimum(d["out"], d["back"])
    # Log amplitude is scale-free in *level*, which is fine across commodities
    # already filtered to the top 100 but wrong across partners: Sweden going
    # $0m -> $30m -> $0m outscores Switzerland going $0.5bn -> $11bn -> $1.3bn.
    # The claim is about how much metal moved, so rank in dollars - how much
    # extra arrived during the surge, and how much of that left again.
    d["swing_in"] = d["surge_m"] - d["baseline_m"]
    d["swing_out"] = d["surge_m"] - d["reversal_m"]
    d["volume"] = np.minimum(d["swing_in"], d["swing_out"])
    d["retrace"] = d["path"] = d["out"] + d["back"]
    d["retrace"] = np.where(d["net"] > 1e-6, d["path"] / d["net"], np.nan)
    d = d.sort_values("volume", ascending=False).reset_index(drop=True)
    d["rank"] = d.index + 1
    d.to_csv(OUT / "gold_partner_points.csv", index=False)

    print("  largest round trips by partner (ranked on dollar volume):")
    for _, r in d.head(6).iterrows():
        print(f"    #{int(r['rank']):>2} {str(r['cty_name'])[:20]:22} "
              f"vol ${r['volume']:6.2f}bn/mo  amp {r['amp']:.2f}  "
              f"M {r.baseline_m:6.2f} -> {r.surge_m:6.2f} -> {r.reversal_m:6.2f}"
              f"   X {r.baseline_x:5.2f} -> {r.surge_x:5.2f} -> {r.reversal_x:5.2f}")

    hi_row = d[d.cty_name == HIGHLIGHT]
    rest = d[d.cty_name != HIGHLIGHT]

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    lo = d[flat].min().min() * 0.55
    hi = d[flat].max().max() * 1.9
    ax.plot([lo, hi], [lo, hi], ls="--", lw=1.1, color=INK, alpha=0.45, zorder=1)
    ax.text(hi * 0.5, hi * 0.55, "M = X", fontsize=8, color=INK, alpha=0.6,
            ha="right", va="bottom", rotation=45, rotation_mode="anchor")

    labelled = 0
    for _, r in rest.iterrows():
        xs = [r[x] for _, x in cols]
        ys = [r[m] for m, _ in cols]
        big = r["volume"] >= 0.05
        ax.plot(xs, ys, "-", lw=1.1 if big else 0.7, color=MUTED,
                alpha=0.65 if big else 0.32, zorder=3 if big else 2)
        ax.plot(xs[0], ys[0], "o", ms=3.0, mfc="white", mec=MUTED, mew=0.7,
                alpha=0.6, zorder=3)
        ax.plot(xs[-1], ys[-1], "o", ms=3.6, color=MUTED, alpha=0.6, zorder=3)
        # Name the ones that actually moved; the rest would be a thicket.
        if big:
            # Alternate the offset: neighbouring partners land close together
            # and a fixed offset stacks their labels on top of each other.
            nudge = (7, 5) if (labelled % 2 == 0) else (7, -11)
            ax.annotate(str(r["cty_name"])[:18], (xs[-1], ys[-1]),
                        textcoords="offset points", xytext=nudge,
                        fontsize=7, color="#5c6b78")
            labelled += 1

    if len(hi_row):
        r = hi_row.iloc[0]
        gx = [r[x] for _, x in cols]
        gy = [r[m] for m, _ in cols]
        for i in range(2):
            ax.annotate("", xy=(gx[i + 1], gy[i + 1]), xytext=(gx[i], gy[i]),
                        arrowprops=dict(arrowstyle="-|>", lw=2.0, color=ACCENT,
                                        shrinkA=4, shrinkB=6), zorder=6)
        ax.plot(gx[0], gy[0], "o", ms=8, mfc="white", mec=ACCENT, mew=2.0, zorder=7)
        ax.plot(gx[1], gy[1], "o", ms=8, color=ACCENT, mec="white", mew=1.2,
                alpha=0.65, zorder=7)
        ax.plot(gx[2], gy[2], "o", ms=10, color=ACCENT, mec="white", mew=1.2,
                zorder=7)
        for (px, py), lab, off, ha in zip(
                zip(gx, gy),
                ["baseline\nNov 23–Oct 24", "surge\nNov 24–Mar 25",
                 "reversal\nApr–Nov 25"],
                [(-14, -30), (-12, 6), (12, -12)], ["right", "right", "left"]):
            ax.annotate(lab, (px, py), textcoords="offset points", xytext=off,
                        fontsize=7.5, color=ACCENT, ha=ha, va="center",
                        linespacing=1.25)
        ax.annotate("SWITZERLAND", (gx[1], gy[1]), textcoords="offset points",
                    xytext=(-20, -34), fontsize=10, fontweight="bold",
                    color=ACCENT, ha="right")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("US exports to partner, $bn per month")
    ax.set_ylabel("US imports from partner, $bn per month")
    ax.set_title("The round trip ran through Switzerland", loc="left",
                 fontsize=11, pad=26)
    ax.text(0, 1.035, f"US gold trade (HS 7108 + 7115) with {len(d)} partners, "
            "three phases each. Above the diagonal the US is a net importer.",
            transform=ax.transAxes, fontsize=8, color="#555", va="bottom")
    if len(oneway):
        who = ", ".join(str(x)[:14] for x in oneway["cty_name"].head(4))
        ax.text(0, -0.125,
                "One-directional corridors have no position on a log-log plane"
                f"\nand are omitted: {who}."
                "\nTheir gold moves to the US and does not come back.",
                transform=ax.transAxes, fontsize=7.5, color="#666",
                va="top", linespacing=1.5)
    ax.text(0.03, 0.955, "US net importer", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55)
    ax.text(0.97, 0.10, "US net exporter", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55, ha="right")

    handles = [
        plt.Line2D([], [], marker="o", ls="none", mfc="white", mec=ACCENT,
                   mew=1.6, ms=7, label="baseline"),
        plt.Line2D([], [], marker="o", ls="none", color=ACCENT, alpha=0.65,
                   ms=7, label="surge"),
        plt.Line2D([], [], marker="o", ls="none", color=ACCENT, ms=8,
                   label="reversal"),
        plt.Line2D([], [], color=MUTED, lw=1.1, alpha=0.6, label="other partners"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, ncol=2,
              handletextpad=0.5, columnspacing=1.4)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"gold_partner_path.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIG}/gold_partner_path.pdf and .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
