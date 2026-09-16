"""
Evidence for the model section of SPREAD_EXPLAINED.html: the horizon choice,
the clock-mismatch correction, and what the curve's slope says about storage
and the New York lease rate.

Everything is computed from files already in data/processed/. Nothing is
pulled. Output is saved in spread_model_checks_output.txt.

The daily fit is the same one validate_mechanism.constant_maturity() uses -
weighted log-linear across contracts - but this script keeps the fitted
intercept and slope instead of only the 90-day reading, and adds a quadratic
fit to measure curvature.

Run from the repo root:
    .venv/Scripts/python.exe claude/spread-explainer/spread_model_checks.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanism-figures"))
from validate_mechanism import MAX_DAYS, MIN_DAYS, MIN_OI  # noqa: E402

P = Path("data/processed")
GAP_HOURS = 3.5          # 15:00 London auction to 13:30 New York settlement
SHARE = GAP_HOURS / 24
STORAGE = 0.0025


def rule(s):
    print(f"\n{'=' * 78}\n{s}\n{'=' * 78}")


def ols(y, X):
    """Coefficients, heteroskedasticity-robust standard errors, R^2."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    inv = np.linalg.inv(X.T @ X)
    V = inv @ (X.T @ (X * resid[:, None] ** 2)) @ inv
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return beta, np.sqrt(np.diag(V)), r2


def fit_daily():
    """Per-day weighted log-linear and log-quadratic fits of the COMEX curve."""
    c = pd.read_csv(P / "comex_contract_daily.csv", parse_dates=["date"])
    e = pd.read_csv(P / "efp_dislocation_v2.csv", parse_dates=["date"]).set_index("date")
    c = c[c.days_to_first_notice.between(MIN_DAYS, MAX_DAYS)
          & (c.open_interest.fillna(0) >= MIN_OI) & c.settle.notna()]
    rows = []
    for dt, g in c.groupby("date"):
        if len(g) < 3:                      # a quadratic needs three points
            continue
        x = g.days_to_first_notice.to_numpy(float)
        y = np.log(g.settle.to_numpy(float))
        w = np.sqrt(g.open_interest.to_numpy(float))
        b, a = np.polyfit(x, y, 1, w=w)
        q2, q1, q0 = np.polyfit(x, y, 2, w=w)
        wsq = w ** 2                        # np.polyfit weights enter squared
        xbar = np.average(x, weights=wsq)
        rows.append((dt, a, b, q0, q1, q2, x.min(), x.max(), xbar,
                     wsq.sum(), (wsq * (x - xbar) ** 2).sum(), len(g)))
    f = pd.DataFrame(rows, columns=["date", "a", "b", "q0", "q1", "q2", "tmin", "tmax",
                                    "tbar", "sw", "sxx", "n"]).set_index("date")
    f = f.join(e[["lbma_pm_usd", "short_rate", "carry_rate"]], how="inner")
    f["level_pct"] = (f.a - np.log(f.lbma_pm_usd)) * 100      # P/S, per cent of spot
    f["level_usd"] = np.exp(f.a) - f.lbma_pm_usd              # P, $/oz
    f["omega_pp"] = (365 * f.b - f.short_rate) * 100          # storage - lease (+ any hazard)
    for T in (30, 60, 90, 180):
        f[f"d{T}"] = ((np.exp(f.a + f.b * T) / f.lbma_pm_usd - 1) * 365 / T - f.carry_rate) * 100
    return f


def main():
    pd.set_option("display.width", 200)
    f = fit_daily()
    print(f"{len(f)} days, {f.index.min():%Y-%m-%d} to {f.index.max():%Y-%m-%d}, "
          f"median {f.n.median():.0f} contracts a day")

    rule("1  Is the horizon inside the data? (support)")
    print("shortest contract in the fit, days:",
          f.tmin.describe()[["min", "25%", "50%", "75%", "max"]].round(0).to_dict())
    print("longest contract in the fit, days:",
          f.tmax.describe()[["min", "50%", "max"]].round(0).to_dict())
    for T in (30, 60, 77, 90, 120):
        print(f"  T={T:>3}: read below the shortest contract on {(f.tmin > T).mean():6.1%} of days")

    rule("2  Where is the fitted value most precise? (variance)")
    grid = np.arange(20, 271, 5)
    V = np.array([(1 / f.sw + (T - f.tbar) ** 2 / f.sxx).mean() for T in grid])
    print(f"weighted centre of mass of the fit: mean {f.tbar.mean():.0f} days, "
          f"median {f.tbar.median():.0f}, middle half {f.tbar.quantile(.25):.0f}-{f.tbar.quantile(.75):.0f}")
    print(f"variance-minimising horizon on this grid: {grid[V.argmin()]} days")
    for T in (30, 60, 90, 180, 270):
        print(f"  T={T:>3}: fit variance {V[list(grid).index(T)] / V.min():.2f}x the minimum")

    rule("3  How much does a straight line cost? (specification bias)")
    print(f"mean curvature q2: {f.q2.mean() * 1e6:+.3f}e-6 per day^2"
          f"   (calm 2015-19 {f.loc['2015':'2019'].q2.mean() * 1e6:+.3f}e-6,"
          f" Nov 2024-Apr 2025 {f.loc['2024-11':'2025-04'].q2.mean() * 1e6:+.3f}e-6)")
    for lab, sl in (("2015-2019", slice("2015", "2019")), ("Nov 2024-Apr 2025", slice("2024-11", "2025-04"))):
        q = f.loc[sl].q2
        print(f"  {lab}: mean/se = {q.mean() / (q.std() / np.sqrt(len(q))):+.1f} (n={len(q)})")
    for T in (30, 90, 180):
        lin = np.exp(f.a + f.b * T)
        quad = np.exp(f.q0 + f.q1 * T + f.q2 * T ** 2)
        d_pp = (quad - lin) / f.lbma_pm_usd * 365 / T * 100
        print(f"  T={T:>3}: straight line vs curve differs by ${(quad - lin).abs().mean():5.2f}/oz "
              f"on average = {d_pp.abs().mean():.2f} pp at that horizon")

    rule("4  The clock mismatch: is the level noise the 3.5-hour window?")
    S = f.lbma_pm_usd
    ret = np.log(S).diff() * 100                      # 15:00 London to 15:00 London, per cent
    fwd = ret.shift(-1)                               # the window inside day t sits inside this
    for lab, sl in (("2015-2026", slice(None)), ("2019 only", slice("2019", "2019"))):
        sd = ret.loc[sl].std()
        pred = sd * np.sqrt(SHARE)
        print(f"{lab}: daily sd of the London fix {sd:.2f}%"
              f" -> implied sd over 3.5h {pred:.2f}% = ${pred / 100 * S.loc[sl].mean():.2f}/oz")
        print(f"{' ' * len(lab)}  measured sd of the fitted level: {f.level_pct.loc[sl].std():.2f}%"
              f" = ${f.level_usd.loc[sl].std():.2f}/oz")
    print(f"drift: mean London-to-London return {ret.mean():.3f}%/day;"
          f" a uniform slice of the day gives {ret.mean() * SHARE:.4f}%"
          f" = ${ret.mean() * SHARE / 100 * S.iloc[-1]:.2f}/oz at the latest price."
          f" LOWER BOUND - the US morning is not an average slice.")

    d = pd.DataFrame({"level": f.level_pct, "omega": f.omega_pp,
                      "R": fwd, "Rlag": fwd.shift(1)}).dropna()
    one = np.ones(len(d))
    b1, se1, r21 = ols(d.level.to_numpy(), np.column_stack([one, d.R]))
    print(f"\nlevel on the same-day forward return : slope {b1[1]:+.3f} (se {se1[1]:.3f}), R2 {r21:.3f}"
          f"   <- predicted {SHARE:.3f} if the 3.5h window drives it")
    b2, se2, _ = ols(d.level.to_numpy(), np.column_stack([one, d.R, d.Rlag]))
    print(f"  with the previous day's return added : slope {b2[1]:+.3f} (se {se2[1]:.3f}),"
          f" placebo lag {b2[2]:+.3f} (se {se2[2]:.3f})   <- lag should be ~0")
    b3, se3, r23 = ols(d.omega.to_numpy(), np.column_stack([one, d.R]))
    print(f"  slope wedge on the same return      : {b3[1]:+.4f} (se {se3[1]:.4f}), R2 {r23:.3f}"
          f"   <- ~0 confirms the error is common across contracts, so it lands in the level only")

    rule("5  What the slope says about storage and the New York lease rate")
    print("omega = 365b - r = storage_NY - lease_NY (+ any horizon-dependent policy hazard)")
    for lab, sl in (("2015-2019 calm", slice("2015", "2019")), ("2019", slice("2019", "2019")),
                    ("Nov 2024-Apr 2025", slice("2024-11", "2025-04")),
                    ("Aug-Oct 2025", slice("2025-08", "2025-10")), ("2026", slice("2026", "2026"))):
        w = f.loc[sl]
        print(f"  {lab:<18} omega {w.omega_pp.mean():+.2f} pp    "
              f"level {w.level_pct.mean():+.3f}% of spot (${w.level_usd.mean():+.2f}/oz)    n={len(w)}")
    calm = f.loc["2015":"2019"].omega_pp.mean()
    print(f"\nIf lease_NY were 0 in calm years, the calm omega implies storage of {calm:.2f}%/yr,"
          f" against the assumed {STORAGE:.2%}.")
    print(f"If instead storage really is {STORAGE:.2%}, the same omega implies lease_NY ="
          f" {STORAGE * 100 - calm:+.2f}%/yr, which is negative - so one of the two is mis-set.")

    rule("6  Measurement error at monthly frequency (attenuation)")
    m = f.resample("ME").agg(level=("level_pct", "mean"), omega=("omega_pp", "mean"),
                             n=("level_pct", "size"))
    m = m[m.n > 5]
    sigma_day = ret.std() * np.sqrt(SHARE)
    sigma_month = sigma_day / np.sqrt(m.n.mean())
    rel = 1 - sigma_month ** 2 / m.level.var()
    print(f"timing noise in one session: {sigma_day:.3f}% of spot; in a monthly mean of"
          f" {m.n.mean():.0f} sessions: {sigma_month:.3f}%")
    print(f"sd of the monthly level series: {m.level.std():.3f}%"
          f" -> reliability {rel:.3f}, so a slope regressed on it is attenuated by {rel:.3f}"
          f" (divide by that to correct: {1 / rel:.2f}x)")

    rule("7  Monthly level and slope through the episode")
    print(m.loc["2024-09":"2025-10", ["level", "omega", "n"]].round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
