"""
Part 3: fix the visual honesty problems, revise the classifier claim
(my own data contradicted the threshold I guessed), produce headline table.
"""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OZ = 32150.7
raw = pd.read_csv("gold_raw_data.csv", parse_dates=["date"])
S = lambda n: raw[raw.series == n].set_index("date")["value"].sort_index()

ch_us = S("ch_exports_to_us")
comex = S("comex_stock")

# Full monthly index so gaps show as gaps, not as absent months
idx = pd.date_range("2024-11-01", "2026-03-01", freq="MS")
ch_us_full = ch_us.reindex(idx)

print("=" * 78)
print("11. HEADLINE DECOMPOSITION")
print("=" * 78)

build = (comex.loc["2025-04-04"] - comex.loc["2024-11-01"]) * 1e6 / OZ
drain = (comex.loc["2025-04-04"] - comex.loc["2026-07-02"]) * 1e6 / OZ
us_absorb_5mo = 115 * 5 / 12
gross_ch_us = ch_us.loc["2024-11":"2025-12"].sum()

tbl = pd.DataFrame([
    ["Gross Swiss->US gold exports, Nov24-Dec25", gross_ch_us, "t", "reported+derived"],
    ["COMEX inventory build, Nov24-Apr25", build, "t", "derived from CME"],
    ["COMEX inventory drain, Apr25-Jul26", drain, "t", "derived from CME"],
    ["Net retained in COMEX vs pre-episode", build - drain, "t", "derived"],
    ["Plausible US absorption over build window", us_absorb_5mo, "t", "Norman 115t/yr"],
    ["-> RELOCATION share of the build", (1 - us_absorb_5mo / build) * 100, "%", "derived"],
    ["-> ABSORPTION share of the build", us_absorb_5mo / build * 100, "%", "derived"],
    ["Recorded trade if build round-tripped x4 legs", build * 4, "t", "derived"],
    ["2025 world total gold supply (for scale)", 5002, "t", "WGC"],
    ["Phantom trade as multiple of world supply", build * 4 / 5002, "x", "derived"],
], columns=["metric", "value", "unit", "basis"])
print()
print(tbl.to_string(index=False, float_format=lambda x: f"{x:10.1f}"))

print("""
Read: of the ~871 t that moved into COMEX vaults between the US election
and April 2025, roughly 95% was relocation of existing above-ground metal
between financial venues. It changed the METAL'S ADDRESS, not its owner
and not the world's consumption of gold. Yet every leg of it printed in
somebody's merchandise trade statistics.
""")

print("=" * 78)
print("12. REVISING THE CLASSIFIER CLAIM (I guessed wrong first time)")
print("=" * 78)
print("""
I asserted CV > 1.5 flags a relocation corridor. My own data says
otherwise: the US corridor scored CV = 1.31, BELOW the threshold I
invented, because a handful of near-zero months drag the mean down and
compress the ratio. CV is the wrong statistic.

The max/min ratio separates cleanly:
    United States    964x    <- relocation corridor
    United Kingdom    53x    <- mixed (transit + relocation)
    India            4.2x    <- consumption corridor

Better still for the paper: a corridor's correlation with the EFP spread
versus its correlation with local price in local currency. Consumption
corridors respond to the latter; relocation corridors to the former.
That needs the full daily spread series, which I could not pull here.
""")

# ---------------- honest chart ----------------
fig, axes = plt.subplots(2, 1, figsize=(11, 8))

ax = axes[0]
vals = ch_us_full.values
cols = ["#B8860B" if not np.isnan(v) else "none" for v in vals]
ax.bar(range(len(idx)), np.nan_to_num(vals), color=cols, width=0.65)
for i, v in enumerate(vals):
    if np.isnan(v):
        ax.text(i, 8, "no\ndata", ha="center", va="bottom", fontsize=6.5, color="#aaa")
ax.set_xticks(range(len(idx)))
ax.set_xticklabels([d.strftime("%b\n%y") for d in idx], fontsize=7.5)
ax.set_ylabel("tonnes")
ax.set_title("Swiss gold exports to the US — a policy artefact, not a demand signal",
             loc="left", fontsize=12, fontweight="bold")
for lbl, i in [("EFP opens", 1), ("tariff\nexemption", 5), ("CBP bar ruling", 9)]:
    ax.annotate(lbl, xy=(i, np.nan_to_num(vals)[i]), xytext=(i, 165),
                ha="center", fontsize=7.5, color="#555",
                arrowprops=dict(arrowstyle="->", color="#aaa", lw=0.8))
ax.grid(axis="y", alpha=0.25)
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
obs = comex * 1e6 / OZ
solid = obs.loc[:"2025-04-17"]
ax.plot(solid.index, solid.values, marker="o", color="#1f4e79", lw=2, label="observed")
ax.plot([obs.index[-2], obs.index[-1]], [obs.values[-2], obs.values[-1]],
        ls=":", color="#1f4e79", lw=1.5, marker="o", label="no observations between")
ax.axhline(115, color="#c0392b", ls="--", lw=1)
ax.annotate("US annual physical coin & bar demand (115 t)", xy=(obs.index[1], 165),
            fontsize=8, color="#c0392b")
ax.set_ylabel("tonnes in COMEX vaults")
ax.set_title("COMEX gold inventory: build and unwind", loc="left",
             fontsize=12, fontweight="bold")
ax.legend(frameon=False, fontsize=8, loc="upper right")
ax.grid(alpha=0.25)
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.savefig("gold_flows.png", dpi=150)
tbl.to_csv("headline_decomposition.csv", index=False)
print("\nRewrote gold_flows.png (gaps now visible, interpolation marked dotted)")
print("Wrote headline_decomposition.csv")
