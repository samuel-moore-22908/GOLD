"""
Three-phase path on the trade-balance plane, gold only, one path per partner.

Same construction as claude/inflow-scatter, but the unit of observation is a
*country* rather than a commodity: within HS 7108 + 7115, where did each
partner sit before the episode, during the inflow, and after it turned.

The commodity figure establishes that gold went in and came back out. This one
answers the question that follows - through whom.

No path is highlighted. Switzerland accounts for 57% of the surge, so its path
necessarily resembles the aggregate, and colouring it differently would assert
that resemblance rather than let the reader find it. Every path is drawn the
same way and labelled; the shape and the position carry the argument.

Verified against the API before use: the 50 codes are all individual countries
with no aggregate groupings, there are no duplicated (code, partner, month)
rows, and Switzerland/Jan-2025 matches a direct call exactly - 711590 at
$18.902bn and 710812 at $0.573bn. The bullion sits specifically in HS 711590.

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
# A partner needs at least this much trade in *both* directions in *every*
# phase to have a position on a log-log plane. Below it the coordinate is
# rounding noise, and including such partners stretched the axes across seven
# decades and squashed the entire episode into one corner.
#
# The exclusion is substantive, not cosmetic: South Africa and Hong Kong trade
# gold with the US in one direction only, so they have no position here at all.
# They are named beneath the figure rather than silently dropped.
LEG_FLOOR = 0.001          # $1m per month
TOP_N = 10                 # partners plotted, by bilateral gold trade

# "Bilateral" is the selection criterion, not a decoration. A partner qualifies
# only if gold moves in BOTH directions in EVERY phase, above LEG_FLOOR. That
# is what the plane measures - a position needs an import coordinate and an
# export coordinate - and it is why the chart is not simply the ten largest
# gold partners. South Africa is the fifth largest by volume and has no
# position here at all, because it sells gold to the US and buys none back.

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False,
})
INK, ACCENT, MUTED = "#1a1a1a", "#b5482a", "#7a8b99"
# Every path uses the same ink: nothing is singled out.
PATH, DOT = "#5c6b78", "#3d4a54"


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
    # Rank on bilateral trade: both directions, all three phases.
    d["bilateral"] = d[flat].sum(axis=1)
    d = d.sort_values("bilateral", ascending=False).reset_index(drop=True)
    d["rank"] = d.index + 1
    d.to_csv(OUT / "gold_partner_points.csv", index=False)
    print(f"  top {TOP_N} by bilateral gold trade ($bn/month, summed over phases):")
    for _, r in d.head(TOP_N).iterrows():
        print(f"    #{int(r['rank']):>2} {str(r.cty_name).split(' (')[0][:20]:22} "
              f"{r['bilateral']:6.2f}")
    # Where the excluded one-way corridors would have ranked, had the plane
    # been able to hold them.
    if len(oneway):
        cutoff = d.head(TOP_N)["bilateral"].min()
        for _, r in oneway.iterrows():
            tot = sum(r[c] for c in flat)
            if tot > cutoff:
                print(f"    ** {str(r.cty_name).split(' (')[0][:20]:22} "
                      f"{tot:6.2f}  would rank inside the top {TOP_N}, "
                      f"but is one-directional")
    d = d.head(TOP_N).copy()

    print("  largest round trips by partner (ranked on dollar volume):")
    for _, r in d.head(6).iterrows():
        print(f"    #{int(r['rank']):>2} {str(r['cty_name'])[:20]:22} "
              f"vol ${r['volume']:6.2f}bn/mo  amp {r['amp']:.2f}  "
              f"M {r.baseline_m:6.2f} -> {r.surge_m:6.2f} -> {r.reversal_m:6.2f}"
              f"   X {r.baseline_x:5.2f} -> {r.surge_x:5.2f} -> {r.reversal_x:5.2f}")

    fig, ax = plt.subplots(figsize=(7.4, 6.6))
    lo = d[flat].min().min() * 0.45
    hi = d[flat].max().max() * 3.0
    ax.plot([lo, hi], [lo, hi], ls="--", lw=1.0, color=INK, alpha=0.35, zorder=1)
    ax.text(hi * 0.45, hi * 0.5, "M = X", fontsize=8, color=INK, alpha=0.5,
            ha="right", va="bottom", rotation=45, rotation_mode="anchor")

    # Uniform treatment; weight tracks round-trip size only for legibility, so
    # a $10bn corridor is not as faint as a $2m one.
    pts = []
    for _, r in d.iterrows():
        xs = [r[x] for _, x in cols]
        ys = [r[m] for m, _ in cols]
        frac = max(0.0, min(r["volume"] / d["volume"].max(), 1.0))
        w = 1.1 + 1.7 * frac ** 0.45
        for i in range(2):
            ax.annotate("", xy=(xs[i + 1], ys[i + 1]), xytext=(xs[i], ys[i]),
                        arrowprops=dict(arrowstyle="-|>", lw=w, color=PATH,
                                        alpha=0.85, shrinkA=3, shrinkB=4),
                        zorder=3)
        # All three phases get a mark, so the middle of the path is a point
        # rather than only an inflection in a line.
        ax.plot(xs[0], ys[0], "o", ms=5.5, mfc="white", mec=DOT, mew=1.3, zorder=4)
        ax.plot(xs[1], ys[1], "o", ms=4.5, mfc=MUTED, mec="white", mew=0.9, zorder=4)
        ax.plot(xs[2], ys[2], "o", ms=6.5, color=DOT, zorder=5)
        pts.append((xs, ys, str(r["cty_name"]).split(" (")[0]))

    # Greedy label placement: try offsets around the end point and keep the
    # first that collides with nothing already placed. Hand-tuned offsets do
    # not survive a change of data.
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    placed = []
    CAND = [(9, 4), (9, -12), (-9, 4), (-9, -12), (9, 14), (-9, 14),
            (9, -22), (-9, -22), (0, 18), (0, -24)]
    for xs, ys, name in pts:
        best = None
        for dx, dy in CAND:
            t = ax.annotate(name, (xs[2], ys[2]), textcoords="offset points",
                            xytext=(dx, dy), fontsize=8, color=INK,
                            ha="left" if dx > 0 else ("right" if dx < 0 else "center"),
                            va="center", zorder=6)
            bb = t.get_window_extent(renderer=rend).expanded(1.06, 1.25)
            if not any(bb.overlaps(q) for q in placed):
                placed.append(bb)
                best = t
                break
            t.remove()
        if best is None:
            t = ax.annotate(name, (xs[2], ys[2]), textcoords="offset points",
                            xytext=(9, 4), fontsize=8, color=INK, ha="left",
                            va="center", zorder=6)
            placed.append(t.get_window_extent(renderer=rend))

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("US exports to partner, $bn per month")
    ax.set_ylabel("US imports from partner, $bn per month")
    ax.set_title("Where the gold came from, and where it went back to",
                 loc="left", fontsize=11, pad=38)
    ax.text(0, 1.035, f"The {len(d)} largest US gold partners by bilateral trade (HS 7108 + 7115), "
            "three phases each. Above the diagonal the US is a net importer.",
            transform=ax.transAxes, fontsize=8, color="#555", va="bottom",
            linespacing=1.5)
    if len(oneway):
        rank_in = oneway.assign(tot=oneway[flat].sum(axis=1))
        rank_in = rank_in[rank_in["tot"] > d["bilateral"].min()]
        who = ", ".join(
            f"{str(r.cty_name).split(' (')[0]} (\\${r.tot:.2f}bn)"
            for _, r in rank_in.sort_values("tot", ascending=False).head(4).iterrows())
        ax.text(0, -0.135,
                f"Four one-directional corridors would rank inside this top ten but cannot be drawn:"
                f"\n{who}."
                "\nTheir gold moves to the US and does not come back, so they have no export coordinate.",
                transform=ax.transAxes, fontsize=7.5, color="#666",
                va="top", linespacing=1.5)
    ax.text(0.03, 0.955, "US net importer", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55)
    ax.text(0.97, 0.10, "US net exporter", transform=ax.transAxes,
            fontsize=8, color=INK, alpha=0.55, ha="right")

    handles = [
        plt.Line2D([], [], marker="o", ls="none", mfc="white", mec=DOT,
                   mew=1.3, ms=7, label="baseline  Nov 23 - Oct 24"),
        plt.Line2D([], [], marker="o", ls="none", mfc=MUTED, mec="white",
                   ms=6, label="surge  Nov 24 - Mar 25"),
        plt.Line2D([], [], marker="o", ls="none", color=DOT, ms=8,
                   label="reversal  Apr - Nov 25"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, ncol=1,
              handletextpad=0.5, columnspacing=1.4)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"gold_partner_path.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIG}/gold_partner_path.pdf and .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
