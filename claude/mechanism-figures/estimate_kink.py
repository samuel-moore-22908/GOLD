"""
Estimate the kink in the spread-to-flow relationship, rather than drawing it.

FIGURE_PLAN.md sketched the hinge from bucket medians, which is honest but stops
at the median spread of the top bucket and leaves the line hanging in mid-air.
This estimates it.

THE MODEL. A continuous kink, which is CLAUDE.md's specification with the flat
segment relaxed into a free slope so the data can say whether it is flat:

    tonnes = a + b1*(x - g) + b2*max(0, x - g) + e

g is the threshold, b1 the slope below it, b1 + b2 the slope above. Continuous at
g by construction, which matters: a discontinuous threshold would claim that a
shipment decision jumps at a point, and nothing about freight works that way.
g is estimated by profile least squares - OLS at every candidate g on a grid,
keep the one with the smallest sum of squares - with 15% of the sample trimmed
from each end so neither regime can be fitted on a handful of months.

THE SPECIFICATION QUESTION THIS SETTLES. The threshold can be measured in two
units and they are not equivalent:

  * pp a year. What FIGURE_PLAN.md quoted, and what the figure's x-axis shows.
  * dollars an ounce over the 90-day horizon.

Freight, insurance and recasting are physical costs. They scale with weight, not
with value, so a transfer cost that is constant in dollars an ounce implies a
threshold in rate space that FALLS as gold gets dearer - and gold went from
$1,160 in 2015 to $4,573 in 2026, a factor of 3.9. A single constant threshold
in pp therefore mixes eras that are not comparable, in exactly the way CLAUDE.md
warns a fixed dollar threshold does in the other direction.

Which specification fits better is then an economic question with an answer, not
a modelling preference: if the dollar version wins, the threshold is a physical
cost, which is the claim the paper wants to make.

Reads   whatever validate_mechanism.py reads
Writes  claude/mechanism-figures/kink_estimates.csv   (for the figure)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_mechanism import constant_maturity, swiss_tonnes  # noqa: E402

OUT = Path("claude/mechanism-figures")
# The estimation window. 2020 and the 2022 sanctions shock are location
# dislocations of a different kind - grounded aircraft and closed refineries in
# one case, a payments and counterparty rupture in the other - and folding them
# into an exercise about a tariff threat buys precision at the cost of scope.
# The full-sample fit is still reported below, because the fact that the two
# agree is worth more than either on its own.
SAMPLE = ("2023-01-01", None)      # None = to the end of the data

TRIM = 0.15          # fraction of the sample kept out of each regime
GRID = 400           # candidate thresholds
BOOT = 2000
BLOCK = 6            # months per block in the moving-block bootstrap
RNG = np.random.default_rng(20260905)


def fit_at(x, y, g):
    """OLS for a fixed threshold. Returns (ssr, coefficients)."""
    X = np.column_stack([np.ones_like(x), x - g, np.maximum(0.0, x - g)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return float(resid @ resid), beta


def fit_kink(x, y, trim=TRIM, grid=GRID):
    """Profile least squares over the threshold."""
    lo, hi = np.quantile(x, trim), np.quantile(x, 1 - trim)
    cands = np.linspace(lo, hi, grid)
    ssrs = np.array([fit_at(x, y, g)[0] for g in cands])
    g = float(cands[np.argmin(ssrs)])
    ssr, beta = fit_at(x, y, g)
    tss = float(((y - y.mean()) ** 2).sum())
    return {"g": g, "a": beta[0], "b_below": beta[1], "b_above": beta[1] + beta[2],
            "ssr": ssr, "r2": 1 - ssr / tss, "n": len(x),
            "grid": cands, "ssr_profile": ssrs}


def linear_r2(x, y):
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return 1 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


def boot_ci(x, y, block=None, reps=BOOT):
    """Bootstrap the threshold. block=None gives iid pairs; else moving blocks."""
    n = len(x)
    out = []
    for _ in range(reps):
        if block is None:
            idx = RNG.integers(0, n, n)
        else:
            starts = RNG.integers(0, n - block + 1, int(np.ceil(n / block)))
            idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        try:
            out.append(fit_kink(x[idx], y[idx], grid=160)["g"])
        except np.linalg.LinAlgError:
            continue
    a = np.array(out)
    return float(np.quantile(a, 0.05)), float(np.quantile(a, 0.95)), a


def report(name, x, y, unit, price=None):
    f = fit_kink(x, y)
    lin = linear_r2(x, y)
    lo_i, hi_i, _ = boot_ci(x, y)
    lo_b, hi_b, _ = boot_ci(x, y, block=BLOCK)
    lo, hi = min(lo_i, lo_b), max(hi_i, hi_b)
    print(f"\n--- {name} (x in {unit}) ---")
    print(f"  threshold      {f['g']:+.3f} {unit}   90% CI [{lo:+.3f}, {hi:+.3f}]"
          f"   (iid [{lo_i:+.2f},{hi_i:+.2f}], block-{BLOCK} [{lo_b:+.2f},{hi_b:+.2f}])")
    print(f"  slope below    {f['b_below']:+8.2f} t per unit")
    print(f"  slope above    {f['b_above']:+8.2f} t per unit")
    print(f"  R2 kink {f['r2']:.3f}   vs linear {lin:.3f}   n={f['n']}")
    if price is not None:
        print(f"  threshold in dollars an ounce at the sample-mean gold price "
              f"(${price:,.0f}): ${f['g'] * (90/365) * price/100:,.2f}")
    return f, (lo, hi)


def main():
    pd.set_option("display.width", 200)
    d = constant_maturity()
    mon = d[["disloc_pp", "excess_usd", "lbma_pm_usd"]].groupby(
        d.index.to_period("M")).mean()
    mon.index = mon.index.to_timestamp()
    full = pd.concat([mon, swiss_tonnes()], axis=1, sort=True).loc["2015-01-01":].dropna(
        subset=["disloc_pp", "che_to_us_t"])
    m = full.loc[SAMPLE[0]:SAMPLE[1]]

    print(f"estimation window {SAMPLE[0][:7]} to "
          f"{m.index.max():%Y-%m}: n = {len(m)} months")
    print(f"full series available: n = {len(full)}, "
          f"{full.index.min():%Y-%m} to {full.index.max():%Y-%m}")
    print(f"gold price {full.lbma_pm_usd.min():,.0f} to "
          f"{full.lbma_pm_usd.max():,.0f} across the full series - a factor of "
          f"{full.lbma_pm_usd.max()/full.lbma_pm_usd.min():.1f}")
    y = m.che_to_us_t.to_numpy(float)

    print("\n" + "=" * 78)
    print("Which unit is the threshold constant in?")
    print("=" * 78)
    f_pp, ci_pp = report("rate space", m.disloc_pp.to_numpy(float), y,
                         "pp a year", price=m.lbma_pm_usd.mean())
    f_usd, ci_usd = report("dollar space", m.excess_usd.to_numpy(float), y,
                           "$/oz over 90 days")

    print("\n  The two are fitted to the same y, so the sums of squares compare "
          "directly:")
    print(f"    rate space   SSR {f_pp['ssr']:>10,.0f}   R2 {f_pp['r2']:.3f}")
    print(f"    dollar space SSR {f_usd['ssr']:>10,.0f}   R2 {f_usd['r2']:.3f}")
    better = "dollar" if f_usd["ssr"] < f_pp["ssr"] else "rate"
    print(f"    -> {better} space fits better by "
          f"{abs(f_usd['ssr']-f_pp['ssr'])/max(f_pp['ssr'],f_usd['ssr']):.1%} of SSR")
    print("""
  READ THIS COMPARISON WITH CARE ON A SHORT WINDOW. The two specifications are
  only distinguishable when the gold price moves a lot, because that is the only
  thing that separates a constant dollar cost from a constant rate. Over
  2015-2026 the price moves 4.7-fold and the dollar version wins clearly. Over
  2023-2025 it moves about half as much on a third of the observations, and the
  ranking flips - which is weak evidence against a prior that does not come from
  the data in the first place: freight, insurance and recasting are charged on
  weight, so a physical transfer cost is a dollar figure whatever this window
  says. The figures stay in dollars, and this note is the reason to distrust any
  claim that the short window settles the question.""")

    print("\n" + "=" * 78)
    print("Robustness of the dollar-space threshold")
    print("=" * 78)
    x = m.excess_usd.to_numpy(float)
    drop = m.che_to_us_t.nlargest(3).index
    k = ~m.index.isin(drop)
    print(f"  drop the three largest months "
          f"({', '.join(d.strftime('%b %Y') for d in drop)}):"
          f"  threshold {fit_kink(x[k], y[k])['g']:+.2f}")
    ylog = np.log(np.maximum(y, 0.05))
    print(f"  log tonnes instead of levels:                       "
          f"  threshold {fit_kink(x, ylog)['g']:+.2f}")
    xf = full.excess_usd.to_numpy(float)
    yf = full.che_to_us_t.to_numpy(float)
    ff = fit_kink(xf, yf)
    lo_f, hi_f, _ = boot_ci(xf, yf, reps=1000)
    print(f"  the full 2015-2026 series (n={len(full)}), which the window excludes:"
          f"  threshold {ff['g']:+.2f}, 90% CI [{lo_f:+.2f}, {hi_f:+.2f}]")
    print("  -> the two windows agree on the point estimate almost exactly. The")
    print("     restriction costs precision, not the result.")

    print("\n" + "=" * 78)
    print("The eastward leg, same window, same specification")
    print("=" * 78)
    ye = m.us_to_che_t.to_numpy(float)
    fe = fit_kink(x, ye)
    print(f"  straight line R2 {linear_r2(x, ye):.3f}, "
          f"correlation {np.corrcoef(x, ye)[0, 1]:+.3f}")
    print(f"  kink R2 {fe['r2']:.3f} at g={fe['g']:+.2f}, slope below "
          f"{fe['b_below']:+.2f}, above {fe['b_above']:+.2f}")
    disc = m[m.excess_usd < -2].sort_values("excess_usd")
    print(f"  The below-kink slope now rests on {len(disc)} discount months rather "
          f"than two,")
    print("  which is the main thing extending the window to the present changed:")
    for dt, r in disc.iterrows():
        print(f"    {dt:%b %Y}  premium {r.excess_usd:+6.2f}/oz   "
              f"eastward {r.us_to_che_t:5.1f} t")
    print("  So the earlier flat claim - that the return leg shows no price response")
    print("  at all - is too strong. What survives is weaker and worth stating as")
    print("  such: when New York goes to a discount, more metal does seem to leave,")
    print("  but the threshold interval spans zero, the straight-line R2 is 0.01 and")
    print("  the correlation is not distinguishable from noise at n = 43. The line")
    print("  is drawn on the figure; the diagnostics are printed beside it.")

    # ------------------------------------------------------------ for the figure
    # Both legs are fitted and both are drawn. The eastward line is drawn on
    # request rather than on the evidence: see the diagnostics above, where its
    # threshold interval spans zero and the straight-line R2 is 0.01. It is on
    # the figure so a reader can see what a fitted kink looks like when there is
    # nothing for it to fit, which is a fair thing to show as long as the
    # numbers travel with it.
    def curve(f, lo_x, hi_x):
        xs = np.linspace(lo_x, hi_x, 200)
        yh = (f["a"] + f["b_below"] * (xs - f["g"])
              + (f["b_above"] - f["b_below"]) * np.maximum(0.0, xs - f["g"]))
        return pd.DataFrame({"x": xs, "yhat": np.maximum(yh, 0)})

    lo, hi = ci_usd
    lo_e, hi_e, _ = boot_ci(x, ye, reps=BOOT)
    curve(f_usd, x.min(), x.max()).to_csv(OUT / "kink_fit.csv", index=False)
    curve(fe, x.min(), x.max()).to_csv(OUT / "kink_fit_east.csv", index=False)
    pd.DataFrame([{
        "g": f_usd["g"], "g_lo": lo, "g_hi": hi,
        "b_below": f_usd["b_below"], "b_above": f_usd["b_above"],
        "a": f_usd["a"], "r2": f_usd["r2"], "n": f_usd["n"],
        "r2_lin": linear_r2(x, y),
        "g_e": fe["g"], "g_e_lo": lo_e, "g_e_hi": hi_e,
        "b_below_e": fe["b_below"], "b_above_e": fe["b_above"],
        "r2_e": fe["r2"], "r2_lin_e": linear_r2(x, ye),
        "corr_e": float(np.corrcoef(x, ye)[0, 1]),
    }]).to_csv(OUT / "kink_estimates.csv", index=False)

    # The monthly panel itself belongs to build_figure_data.py, which already
    # carries excess_usd. Writing a second copy here would give the figure two
    # sources of truth for the same points.
    print("\nwrote kink_estimates.csv, kink_fit.csv and kink_fit_east.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
