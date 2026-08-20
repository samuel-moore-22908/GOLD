"""
Part 2: where did the COMEX metal actually come from, and where did it go?
This is the part that turned out to be the interesting bit.
"""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OZ = 32150.7
raw = pd.read_csv("gold_raw_data.csv", parse_dates=["date"])
ctx = pd.read_csv("gold_context_data.csv")
S = lambda n: raw[raw.series == n].set_index("date")["value"].sort_index()

print("=" * 78)
print("7. SOURCING RECONCILIATION - THE BIG RESIDUAL")
print("=" * 78)

comex = S("comex_stock")
ch_us = S("ch_exports_to_us")

# Window 1: election through end-Jan 2025 (FT reported both sides)
ft_build = 393.0                       # t into COMEX, election -> 2025-01-29
lbma_draw = 30.0 + 151.0               # Dec + Jan London vault drawdown
ch_us_w1 = ch_us.loc["2024-11":"2025-01"].sum()

print(f"\nWindow A: US election -> 29 Jan 2025")
print(f"  COMEX build (FT):                    {ft_build:7.1f} t")
print(f"  LBMA London vault drawdown:          {lbma_draw:7.1f} t   "
      f"({lbma_draw/ft_build*100:.0f}% of build)")
print(f"  Swiss exports to US (Nov+Dec+Jan):   {ch_us_w1:7.1f} t   "
      f"({ch_us_w1/ft_build*100:.0f}% of build)")
print(f"  -> London alone explains only {lbma_draw/ft_build*100:.0f}% of the New York build.")

# Window 2: election -> peak
build_full = (comex.loc["2025-04-04"] - comex.loc["2024-11-01"]) * 1e6 / OZ
ch_us_full = ch_us.loc["2024-11":"2025-04"].sum()
print(f"\nWindow B: US election -> COMEX peak (4 Apr 2025)")
print(f"  COMEX build:                         {build_full:7.1f} t")
print(f"  Swiss exports to US (Nov-Apr):       {ch_us_full:7.1f} t   "
      f"({ch_us_full/build_full*100:.0f}% of build)")
print(f"  Unsourced residual:                  {build_full-ch_us_full:7.1f} t   "
      f"({(build_full-ch_us_full)/build_full*100:.0f}%)")

print("""
  Candidate sources for the residual:
    - direct UK->US shipments of already-conforming bars
    - other refiners (Perth, Canada, UAE) shipping kilobars
    - US domestic mine + refinery output diverted to vault
    - existing non-COMEX US private vault stock re-warranted
  The last one records NO cross-border trade at all, which matters:
  it means trade data UNDERSTATES the relocation in one direction while
  OVERSTATING it in another. Not a simple inflation factor.
""")

print("=" * 78)
print("8. WHERE IT WENT ON THE WAY OUT")
print("=" * 78)
drain = (comex.loc["2025-04-04"] - comex.loc["2026-07-02"]) * 1e6 / OZ
us_ch_obs = S("ch_imports_from_us").sum()
print(f"\n  COMEX drain Apr 2025 -> Jul 2026:    {drain:7.1f} t")
print(f"  Observed US->CH return (Feb-Apr 25):  {us_ch_obs:7.1f} t  [partial series]")
print(f"  Unobserved / other destinations:      {drain-us_ch_obs:7.1f} t")
print("""
  In early 2026 gold was the single largest US export item for three
  consecutive months (Feb 2026: $17.9bn). At a ~$4,800/oz working price
  that implies roughly the tonnage below.
""")
for px in [4400, 4800, 5200]:
    t = 17.88e9 / px / OZ * 1e0
    t = (17.88e9 / px) / OZ
    print(f"    at ${px}/oz  ->  Feb 2026 US gold exports = {t:6.1f} t")

print("""
  Sanity check: that is one month of US gold EXPORTS running at roughly
  the same order as a normal month of total Swiss gold exports globally.
  The US - historically a marginal player in physical gold trade - became
  a major net exporter purely by unwinding a vault position.
""")

print("=" * 78)
print("9. LEAD-LAG: SPREAD FIRST, METAL SECOND")
print("=" * 78)
efp = S("efp_spread")
print("\n  EFP / COMEX-London spread observations:")
for d, v in efp.items():
    print(f"    {d:%Y-%m-%d}  ${v:.0f}/oz")
print(f"""
  Spread first opened >$50 in mid-Dec 2024. Swiss shipments:
    Nov 2024   {ch_us.loc['2024-11-01']:6.1f} t   (spread not yet open)
    Dec 2024   {ch_us.loc['2024-12-01']:6.1f} t   (spread opens)
    Jan 2025   {ch_us.loc['2025-01-01']:6.1f} t   (spread peaks ~$64)
    Feb 2025   {ch_us.loc['2025-02-01']:6.1f} t   (spread compressing)
    Mar 2025   {ch_us.loc['2025-03-01']:6.1f} t
    Apr 2025   {ch_us.loc['2025-04-01']:6.1f} t   (exemption; spread gone)

  Physical flow lags the spread by roughly one month - the recast-and-fly
  cycle. That lag is exploitable: the spread is a LEADING indicator of the
  phantom component of next month's trade print. That is the most useful
  practical result here.
""")

print("=" * 78)
print("10. VOLATILITY AS A CLASSIFIER (underpowered but suggestive)")
print("=" * 78)
rows = []
for name, lbl in [("ch_exports_to_us", "United States"),
                  ("ch_exports_to_uk", "United Kingdom"),
                  ("ch_exports_to_india", "India"),
                  ("ch_exports_to_turkey", "Turkey")]:
    s = S(name).loc["2024-11":]
    if len(s) >= 3:
        rows.append({"destination": lbl, "n_obs": len(s), "mean_t": s.mean(),
                     "sd_t": s.std(), "cv": s.std() / s.mean(),
                     "max_min_ratio": s.max() / max(s.min(), 0.05)})
cls = pd.DataFrame(rows).sort_values("cv", ascending=False)
print()
print(cls.to_string(index=False, float_format=lambda x: f"{x:8.2f}"))
print("""
  CV above ~1.5 flags a financial/relocation corridor; consumption
  corridors sit well below 1. With n=3-12 this is illustrative only, but
  on the full Swiss-Impex panel (2012-present, ~40 destinations) it would
  be a clean unsupervised first cut before any event study.
""")

# ---------------- charts ----------------
fig, axes = plt.subplots(2, 1, figsize=(11, 8.5), sharex=False)

ax = axes[0]
e = ch_us.loc["2024-11":"2025-12"]
ax.bar([d.strftime("%b\n%y") for d in e.index], e.values, color="#B8860B", width=0.62)
ax.set_ylabel("tonnes")
ax.set_title("Swiss gold exports to the US — a policy artefact, not a demand signal",
             loc="left", fontsize=12, fontweight="bold")
for ev, lbl in [("Dec\n24", "EFP opens"), ("Apr\n25", "tariff\nexemption"),
                ("Aug\n25", "CBP bar\nruling")]:
    if ev in [d.strftime("%b\n%y") for d in e.index]:
        i = [d.strftime("%b\n%y") for d in e.index].index(ev)
        ax.annotate(lbl, xy=(i, e.values[i]), xytext=(i, max(e.values) * 0.72),
                    ha="center", fontsize=8, color="#444",
                    arrowprops=dict(arrowstyle="->", color="#999", lw=0.8))
ax.grid(axis="y", alpha=0.25)
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
c = comex.copy()
ax.plot(c.index, c.values * 1e6 / OZ, marker="o", color="#1f4e79", lw=2)
ax.set_ylabel("tonnes in COMEX vaults")
ax.set_title("COMEX gold inventory: build and unwind",
             loc="left", fontsize=12, fontweight="bold")
ax.axhline(115, color="#c0392b", ls="--", lw=1)
ax.annotate("US annual physical coin & bar demand (115 t)",
            xy=(c.index[2], 150), fontsize=8, color="#c0392b")
ax.grid(alpha=0.25)
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.savefig("gold_flows.png", dpi=150)
print("\nChart written: gold_flows.png")

cls.to_csv("corridor_classifier.csv", index=False)
print("Classifier table written: corridor_classifier.csv")
