"""
Does liquidity predict how noisy a settlement price is? Apparently not.

Every document in this project justifies weighting the daily curve fit by
liquidity on inverse-variance grounds: thin contracts are said to carry noisier
settlements, so they should count for less. That is a testable claim about the
residuals, and this tests it, against both liquidity measures the panel carries.

    OPEN INTEREST is a stock: contracts outstanding at the end of the day.
    VOLUME is a flow: contracts traded during it.

They are related but not the same. A day of heavy trading between existing
holders moves volume and leaves open interest unchanged; a day when new
positions are opened moves both.

The trap this script exists to avoid: contracts with no trades are mostly
deferred contracts, which sit at the far end of the horizon range, where
leverage is high and ordinary least squares pulls the fitted line towards them.
Their raw residuals are therefore small for a reason that has nothing to do
with data quality. Studentizing removes that, and the apparent finding with it.

Reads   data/processed/comex_contract_daily.csv
Writes  claude/premium-carry-series/weighting_diagnostics_output.txt

Run from the repo root:
    .venv/Scripts/python.exe claude/premium-carry-series/weighting_diagnostics.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("claude/premium-carry-series")
MIN_TAU, MAX_TAU, MIN_OI = 15, 400, 1000


def panel() -> pd.DataFrame:
    c = pd.read_csv("data/processed/comex_contract_daily.csv", parse_dates=["date"])
    c = c[c.days_to_first_notice.between(MIN_TAU, MAX_TAU)]
    c = c[(c.open_interest.fillna(0) >= MIN_OI) & c.settle.notna()]
    c["volume"] = c.volume.fillna(0)
    return c


def residuals(c: pd.DataFrame) -> pd.DataFrame:
    """Unweighted daily fit, with leverage and studentized residuals.

    Unweighted on purpose: the residuals are the evidence about which weighting
    is right, so they must not be produced by one of the weightings on trial.
    """
    rows = []
    for _, g in c.groupby("date"):
        if len(g) < 4:
            continue
        x = g.days_to_first_notice.to_numpy(float)
        y = np.log(g.settle.to_numpy(float))
        X = np.column_stack([np.ones_like(x), x])
        h = np.clip(np.diag(X @ np.linalg.pinv(X.T @ X) @ X.T), 0, 0.999)
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ b
        s = np.sqrt(max((e ** 2).sum() / max(len(x) - 2, 1), 1e-18))
        rows.append(g.assign(resid_bp=1e4 * e, leverage=h,
                             studentized=e / (s * np.sqrt(np.clip(1 - h, 1e-6, None)))))
    r = pd.concat(rows)
    r["traded"] = r.volume > 0
    r["abs_t"] = r.studentized.abs()
    return r


def main() -> None:
    c = panel()
    r = residuals(c)
    L, P = [], lambda s="": None
    out: list[str] = []
    P = out.append

    P("=" * 78)
    P("WHAT THE TWO LIQUIDITY MEASURES LOOK LIKE")
    P("=" * 78)
    P(f"contract-days in the fit : {len(c):,}")
    P(f"open interest, median    : {c.open_interest.median():,.0f} contracts")
    P(f"volume, median           : {c.volume.median():,.0f} contracts")
    P(f"no trades at all         : {(c.volume == 0).sum():,} "
      f"({100*(c.volume == 0).mean():.1f}%)")
    P(f"fewer than 100 traded    : {(c.volume < 100).sum():,} "
      f"({100*(c.volume < 100).mean():.1f}%)")
    P(f"corr(log OI, log volume) : "
      f"{np.corrcoef(np.log(c.open_interest), np.log1p(c.volume))[0,1]:.3f}")
    P("")
    P("A settlement for a contract that did not trade is not a traded price. The")
    P("exchange derives it from the rest of the curve, so it is not an")
    P("independent observation of the curve being fitted.")

    P("")
    P("=" * 78)
    P("RAW RESIDUALS SUGGEST THINNER CONTRACTS FIT BETTER -- WHICH IS AN ARTEFACT")
    P("=" * 78)
    for name, col in (("open interest", "open_interest"), ("volume", "volume")):
        q = pd.qcut(r[col].rank(method="first"), 5, labels=False)
        g = r.groupby(q).agg(median_abs_bp=("resid_bp", lambda v: v.abs().median()),
                             sd_bp=("resid_bp", "std"), n=("resid_bp", "size"))
        P(f"\nby {name} quintile (basis points of price):")
        P(g.round(2).to_string())
    z, nz = r[~r.traded], r[r.traded]
    P(f"\nnever traded : n={len(z):,}  median |residual| {z.resid_bp.abs().median():.2f} bp")
    P(f"traded       : n={len(nz):,}  median |residual| {nz.resid_bp.abs().median():.2f} bp")
    P("")
    P("The untraded contracts look tidier. They are not. They are deferred")
    P("contracts sitting at the far end of the horizon range, where leverage is")
    P("high and the fitted line is pulled towards them:")
    P(r.groupby("traded").agg(n=("leverage", "size"),
                              mean_leverage=("leverage", "mean"),
                              median_tau=("days_to_first_notice", "median"))
      .round(3).to_string())

    P("")
    P("=" * 78)
    P("STUDENTIZED, AND WITHIN HORIZON BUCKETS: NEITHER MEASURE PREDICTS NOISE")
    P("=" * 78)
    r["tau_bucket"] = pd.cut(r.days_to_first_notice, [15, 60, 120, 200, 400],
                             labels=["15-60", "60-120", "120-200", "200-400"])
    tab = r.pivot_table(index="tau_bucket", columns="traded", values="abs_t",
                        aggfunc="median", observed=True)
    tab.columns = ["not traded", "traded"]
    cnt = r.pivot_table(index="tau_bucket", columns="traded", values="abs_t",
                        aggfunc="size", observed=True)
    cnt.columns = ["n not traded", "n traded"]
    P("median |studentized residual|:")
    P(pd.concat([tab, cnt], axis=1).round(3).to_string())
    P("")
    for lab, sub in (("not traded", r[~r.traded]), ("traded", r[r.traded])):
        P(f"   {lab:<12} n={len(sub):>6,}  median |t| {sub.abs_t.median():.3f}"
          f"   sd {sub.studentized.std():.3f}")
    P("")
    for name, col in (("open interest", "open_interest"), ("volume", "volume")):
        q = pd.qcut(r[col].rank(method="first"), 5, labels=False)
        med = r.groupby(q).abs_t.median()
        P(f"median |studentized| across {name} quintiles: "
          + ", ".join(f"{v:.3f}" for v in med))

    P("")
    P("=" * 78)
    P("WHAT THIS MEANS FOR THE WEIGHTS")
    P("=" * 78)
    P("The inverse-variance case for weighting by liquidity is not supported in")
    P("this panel: residual dispersion is flat across open-interest quintiles,")
    P("flat across volume quintiles, and the same for contracts that traded and")
    P("contracts that did not, once leverage is accounted for.")
    P("")
    P("That does not make weighting wrong, but it changes what it is for. Open")
    P("interest tilts the fit towards near-dated contracts, which is where the")
    P("intercept is extrapolated to, so it reduces the variance of the")
    P("extrapolation. That is an argument about leverage and influence, not")
    P("about precision, and it is the one the paper should make.")
    P("")
    P("Volume carries the one thing open interest cannot: whether a settlement")
    P("is a traded price at all. Untraded settlements are not noisier, but they")
    P("are not independent either, so they flatter the fit statistics. Reporting")
    P("the intercept's standard error on traded contracts only is the honest")
    P("robustness check, and volume is what makes it possible.")

    text = "\n".join(out)
    (OUT / "weighting_diagnostics_output.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
