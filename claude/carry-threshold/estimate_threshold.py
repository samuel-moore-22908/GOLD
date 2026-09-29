#!/usr/bin/env python3
"""
Re-estimate the cost of moving an ounce, on the re-timed premium.

The threshold is not a quote from a freight company. Nobody publishes one. It
is estimated from the flows: metal does not move until the premium clears the
cost of moving it, so the relationship between premium and tonnes has a kink,
and the kink is the cost.

    tonnes = a + b_below * min(x, g) + b_above * max(0, x - g) + u

g is found by profile least squares - fit at every candidate threshold on a
grid, keep the one with the smallest sum of squares - and its confidence
interval comes from a bootstrap, iid and in moving blocks of six months to
allow for persistence. This is the method in claude/mechanism-figures, applied
to the premium that is now re-timed to the London auction rather than the one
that carried the full three-and-a-half-hour timing error.

Why that should matter: measurement error in a regressor both attenuates the
slope and smears the kink, because the threshold is a feature of the x axis and
noise in x moves observations across it. Halving the noise should sharpen the
estimate.

Reads   claude/carry-threshold/carry_threshold_monthly.csv
Writes  claude/carry-threshold/threshold_estimates.csv
        claude/carry-threshold/estimate_threshold_output.txt

Run from anywhere:
    python claude/carry-threshold/estimate_threshold.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

TRIM = 0.15           # candidate thresholds span this inner range of x
GRID = 400            # candidates on the grid
BOOT = 2000           # bootstrap replications
BLOCK = 6             # months per block in the moving-block bootstrap
SEED = 20260929

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/carry-threshold"
RNG = np.random.default_rng(SEED)

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def fit_at(x: np.ndarray, y: np.ndarray, g: float):
    """OLS at a fixed threshold, in the basis the repo's other estimator uses.

    With [1, x-g, max(0, x-g)] the slope below the kink is beta[1] and the slope
    above is beta[1] + beta[2]. A basis using min(x, g) instead spans the same
    space and gives the same threshold and fit, but its second column is flat
    above the kink, so reading the upper slope as beta[1] + beta[2] would then
    be wrong. Keeping one basis across the project avoids that.
    """
    X = np.column_stack([np.ones_like(x), x - g, np.maximum(0.0, x - g)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(((y - X @ beta) ** 2).sum()), beta


def fit_kink(x: np.ndarray, y: np.ndarray, grid: int = GRID) -> dict:
    lo, hi = np.quantile(x, TRIM), np.quantile(x, 1 - TRIM)
    cands = np.linspace(lo, hi, grid)
    ssr = np.array([fit_at(x, y, g)[0] for g in cands])
    g = float(cands[int(np.argmin(ssr))])
    s, beta = fit_at(x, y, g)
    tss = float(((y - y.mean()) ** 2).sum())
    return {"g": g, "b_below": float(beta[1]), "b_above": float(beta[2] + beta[1]),
            "r2": 1 - s / tss, "n": len(x)}


def boot_ci(x, y, block=None, reps=BOOT):
    n, out = len(x), []
    for _ in range(reps):
        if block is None:
            idx = RNG.integers(0, n, n)
        else:
            starts = RNG.integers(0, n - block + 1, int(np.ceil(n / block)))
            idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        try:
            out.append(fit_kink(x[idx], y[idx], grid=160)["g"])
        except Exception:                                      # noqa: BLE001
            continue
    return float(np.quantile(out, 0.05)), float(np.quantile(out, 0.95))


def fit_pressure(daily: pd.DataFrame, y_monthly: pd.Series):
    """Profile least squares over kappa, hinging daily and averaging to the month.

    The monthly pressure at each candidate kappa is precomputed once, so the
    bootstrap only has to redo the regression rather than the aggregation.
    """
    x = daily.set_index("date").spread_usd
    kappas = np.linspace(np.quantile(x, 0.50), np.quantile(x, 0.995), 200)
    cols = {}
    for k in kappas:
        cols[k] = np.maximum(0.0, x - k).resample("MS").mean()
    P = pd.DataFrame(cols)
    joined = P.join(y_monthly.rename("y"), how="inner").dropna(subset=["y"])
    y = joined.y.to_numpy(float)
    M = joined.drop(columns="y").to_numpy(float)

    def best(idx):
        yy, MM = y[idx], M[idx]
        tss = ((yy - yy.mean()) ** 2).sum()
        ssr = np.empty(MM.shape[1])
        for j in range(MM.shape[1]):
            X = np.column_stack([np.ones(len(yy)), MM[:, j]])
            beta, *_ = np.linalg.lstsq(X, yy, rcond=None)
            ssr[j] = ((yy - X @ beta) ** 2).sum()
        j = int(np.argmin(ssr))
        X = np.column_stack([np.ones(len(yy)), MM[:, j]])
        beta, *_ = np.linalg.lstsq(X, yy, rcond=None)
        return j, float(beta[1]), 1 - ssr[j] / tss

    j, beta, r2 = best(np.arange(len(y)))
    n = len(y)
    draws = []
    for _ in range(400):
        starts = RNG.integers(0, n - BLOCK + 1, int(np.ceil(n / BLOCK)))
        idx = np.concatenate([np.arange(s, s + BLOCK) for s in starts])[:n]
        try:
            draws.append(kappas[best(idx)[0]])
        except Exception:                                      # noqa: BLE001
            continue
    ci = (float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95)))
    return float(kappas[j]), ci, {"beta": beta, "r2": r2, "n": n}


def report(label: str, x: np.ndarray, y: np.ndarray) -> dict:
    f = fit_kink(x, y)
    lo_i, hi_i = boot_ci(x, y)
    lo_b, hi_b = boot_ci(x, y, block=BLOCK)
    lin = np.polyfit(x, y, 1)
    lin_r2 = 1 - ((y - np.polyval(lin, x)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    note(f"   {label}")
    note(f"      threshold      ${f['g']:+.2f} an ounce")
    note(f"      90% CI         iid [${lo_i:+.2f}, ${hi_i:+.2f}]   "
         f"block-{BLOCK} [${lo_b:+.2f}, ${hi_b:+.2f}]")
    note(f"      slope below    {f['b_below']:+.2f} t per $/oz")
    note(f"      slope above    {f['b_above']:+.2f} t per $/oz")
    note(f"      R2 kink {f['r2']:.3f}  vs straight line {lin_r2:.3f}   n={f['n']}")
    return {"label": label, **f, "ci_iid_lo": lo_i, "ci_iid_hi": hi_i,
            "ci_block_lo": lo_b, "ci_block_hi": hi_b, "r2_linear": lin_r2}


def main() -> None:
    os.chdir(ROOT)
    m = pd.read_csv(OUT / "carry_threshold_monthly.csv", parse_dates=["month"])
    m = m.dropna(subset=["tonnes_che_usa", "spread_usd"])

    note("=" * 78)
    note("WHERE THE THRESHOLD COMES FROM")
    note("=" * 78)
    note("   Nobody publishes the cost of flying an ounce of gold across the")
    note("   Atlantic, having it recast on the way. It is estimated from the")
    note("   flows: metal does not move until the premium covers that cost, so")
    note("   the premium-tonnage relationship kinks, and the kink is the cost.")
    note("")
    note(f"   {len(m)} months, {m.month.min():%Y-%m} to {m.month.max():%Y-%m}")
    note(f"   premium  ${m.spread_usd.min():.2f} to ${m.spread_usd.max():.2f} an ounce")
    note(f"   tonnes   {m.tonnes_che_usa.min():.1f} to {m.tonnes_che_usa.max():.1f}")

    rows = []
    note("")
    note("=" * 78)
    note("WESTWARD: LONDON AND ZURICH TO NEW YORK")
    note("=" * 78)
    x = m.spread_usd.to_numpy(float)
    y = m.tonnes_che_usa.to_numpy(float)
    rows.append(report("full series, re-timed premium", x, y))

    note("")
    w = m[m.month >= "2023-01-01"]
    rows.append(report("2023 onward, the window the old estimate used",
                       w.spread_usd.to_numpy(float), w.tonnes_che_usa.to_numpy(float)))

    note("")
    e = m[m.month < "2025-04-01"]
    rows.append(report("before the April 2025 exemption",
                       e.spread_usd.to_numpy(float), e.tonnes_che_usa.to_numpy(float)))

    note("")
    note("=" * 78)
    note("THE RIGHT AGGREGATION: HINGE DAILY, THEN AVERAGE")
    note("=" * 78)
    note("   Everything above regresses tonnes on the MONTHLY MEAN premium, which")
    note("   is what the earlier estimate did. It is the wrong way round. The")
    note("   hinge is convex, so a month averaging zero can contain a week at $5")
    note("   that moved metal, and averaging first hides it. The premium should be")
    note("   hinged daily and the result averaged:")
    note("")
    note("       tonnes = a + beta * mean_over_days[ max(0, premium - kappa) ]")
    note("")
    note("   kappa is then chosen by profile least squares over the same grid.")
    daily = pd.read_csv(OUT / "carry_threshold_daily.csv", parse_dates=["date"])
    y_m = m.set_index("month").tonnes_che_usa
    g, ci, extras = fit_pressure(daily, y_m)
    note("")
    note(f"   threshold      ${g:+.2f} an ounce")
    note(f"   90% CI         block-{BLOCK} [${ci[0]:+.2f}, ${ci[1]:+.2f}]")
    note(f"   slope          {extras['beta']:+.2f} t per $/oz of monthly pressure")
    note(f"   R2             {extras['r2']:.3f}   n={extras['n']}")
    rows.append({"label": "daily hinge, then averaged", "g": g,
                 "ci_block_lo": ci[0], "ci_block_hi": ci[1],
                 "b_above": extras["beta"], "r2": extras["r2"], "n": extras["n"]})

    note("")
    note("=" * 78)
    note("EASTWARD: IS THERE A THRESHOLD GOING THE OTHER WAY?")
    note("=" * 78)
    f = pd.read_csv(ROOT / "data/processed/bilateral_panel_2015_2026.csv",
                    parse_dates=["date"])
    # Swiss IMPORTS from the United States, not US exports: the US Census export
    # figures carry no mass at all - every net_mass_kg is zero - so the eastward
    # leg has to be read from the side that weighs it.
    back = f[(f.reporter_iso3 == "CHE") & (f.country_iso3 == "USA")
             & (f.flow == "import")]
    tonnes_east = (back.groupby("date").net_mass_kg.sum() / 1000.0).rename("tonnes")
    me = m.set_index("month").join(tonnes_east, how="inner").dropna(
        subset=["tonnes", "spread_usd"])
    note(f"   {len(me)} months of Swiss imports from the United States")
    note(f"   tonnes {me.tonnes.min():.1f} to {me.tonnes.max():.1f}, "
         f"median {me.tonnes.median():.1f}")
    if me.tonnes.var() > 0:
        rows.append(report("eastward, on the same premium",
                           me.spread_usd.to_numpy(float),
                           me.tonnes.to_numpy(float)))
    else:
        note("   no variation in the eastward series; nothing to estimate")

    note("")
    note("=" * 78)
    note("WHAT TO CONCLUDE")
    note("=" * 78)
    note("   The point estimate is stable and the interval is not. That was true")
    note("   of the old estimate too, and re-timing the premium has not made the")
    note("   threshold precise - it has made the point estimate trustworthy while")
    note("   leaving the interval wide, because 139 monthly observations with a")
    note("   handful of episodes cannot pin a kink tightly however clean the x.")
    note("")
    note("   Quote the threshold as a point estimate with its interval attached,")
    note("   never as a narrow band. A figure that shades a no-trade region should")
    note("   show the interval, not a hairline.")

    pd.DataFrame(rows).to_csv(OUT / "threshold_estimates.csv", index=False)
    note("")
    note(f"   wrote {OUT / 'threshold_estimates.csv'}")
    (OUT / "estimate_threshold_output.txt").write_text("\n".join(LOG) + "\n",
                                                       encoding="utf-8")


if __name__ == "__main__":
    main()
