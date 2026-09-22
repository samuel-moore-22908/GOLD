"""
Build the two series the paper reports from the reduced-form curve fit:

    1. the NEW YORK PREMIUM, p_hat = a_t - ln S_t, a level, in per cent of spot
    2. the CARRY,             365 * b_t, a rate, in per cent a year

where a_t and b_t are the intercept and slope of the daily weighted regression
of log COMEX settlement prices on days to first notice, across the contracts
listed that day. See claude/spread-reduced-form/REDUCED_FORM_MODEL.pdf for why
the objects are defined this way.

The carry series is the sanity check: it is an estimate of what it costs to
hold gold in New York for a year, and it has no interest-rate data in it at
all, so if the fit is doing what it claims, carry should track the dollar
short rate one for one. That comparison is the main diagnostic printed below.

Reads   data/processed/comex_contract_daily.csv   (Databento GLBX.MDP3, local)
        prices.lbma.org.uk  gold_pm.json          (cached under raw_cache/)
        fred.stlouisfed.org SOFR, DFF, DTB3       (cached under raw_cache/)

Writes  premium_carry_daily.csv
        premium_carry_monthly.csv
        build_premium_carry_output.txt   (whatever this prints)

Run from the repo root:
    .venv/Scripts/python.exe claude/premium-carry-series/build_premium_carry.py
"""
from __future__ import annotations

import io
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("claude/premium-carry-series")
CACHE = OUT / "raw_cache"

# --- Specification, all of it in one place -----------------------------------
#
# Contracts entering the daily fit. Inside 15 days a contract is in its delivery
# window and stops behaving like a forward; past 400 days open interest is a
# rounding error; the 1,000-lot floor drops deferred contracts whose settlement
# is marked rather than traded.
MIN_TAU, MAX_TAU, MIN_OI = 15, 400, 1000
MIN_CONTRACTS = 3          # 2 points fit a line exactly and leave no residual

# Weighting. WEIGHT_POWER is the exponent on open interest in the WLS objective,
# i.e. the fit minimises sum_i OI_i**WEIGHT_POWER * (residual_i)**2.
#   0.5 -> the sqrt(OI) weighting every document in this project specifies
#   1.0 -> what np.polyfit(..., w=np.sqrt(OI)) actually does, and therefore what
#          claude/mechanism-figures/validate_mechanism.py has been doing
#   0.0 -> unweighted
WEIGHT_POWER = 0.5
ALT_WEIGHT_POWERS = (0.0, 1.0)

# Day count. Rates are annualised on 365; SOFR and fed funds are quoted ACT/360,
# so they are scaled before any comparison with the fitted carry.
DAYS_PER_YEAR = 365.0
ACT360_TO_365 = 365.0 / 360.0

# Politeness when fetching public series: one request at a time, spaced out.
REQUEST_SPACING_S = 1.5


# --- Inputs ------------------------------------------------------------------

def _get(url: str, cache_name: str) -> bytes:
    """Fetch a public series once, then serve it from disk on later runs."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / cache_name
    if path.exists():
        return path.read_bytes()
    time.sleep(REQUEST_SPACING_S)
    req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except Exception:
        # FRED's CSV endpoint intermittently stalls under urllib on this
        # machine while curl fetches it without trouble, so fall back rather
        # than fail the build.
        body = subprocess.run(
            ["curl", "-sS", "-m", "90", "-A", "GOLD-research/1.0", url],
            check=True, capture_output=True).stdout
    if not body:
        raise RuntimeError(f"empty response from {url}")
    path.write_bytes(body)
    return body


def lbma_pm() -> pd.DataFrame:
    """London benchmark, PM auction, USD per troy ounce."""
    raw = json.loads(_get("https://prices.lbma.org.uk/json/gold_pm.json",
                          "lbma_gold_pm.json"))
    df = pd.DataFrame({"date": [r["d"] for r in raw],
                       "lbma_pm_usd": [r["v"][0] if r.get("v") else None for r in raw]})
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["lbma_pm_usd"]).sort_values("date")


def fred(series_id: str) -> pd.DataFrame:
    """Any FRED series, via the keyless CSV endpoint."""
    raw = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
               f"fred_{series_id}.csv")
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", series_id]
    df["date"] = pd.to_datetime(df["date"])
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    return df.dropna()


def contracts() -> pd.DataFrame:
    c = pd.read_csv("data/processed/comex_contract_daily.csv", parse_dates=["date"])
    c = c[c.days_to_first_notice.between(MIN_TAU, MAX_TAU)]
    c = c[(c.open_interest.fillna(0) >= MIN_OI) & c.settle.notna()]
    return c


# --- The daily projection ----------------------------------------------------

def fit_line(tau: np.ndarray, logf: np.ndarray, v: np.ndarray) -> dict:
    """WLS of log F on tau. `v` weights the squared residual.

    Returns the intercept and slope, their standard errors, and fit statistics.
    """
    X = np.column_stack([np.ones_like(tau), tau])
    s = np.sqrt(v)
    beta, *_ = np.linalg.lstsq(X * s[:, None], logf * s, rcond=None)
    resid = logf - X @ beta
    dof = len(tau) - 2
    sigma2 = float(v @ resid**2 / dof) if dof > 0 else np.nan
    try:
        xtvx_inv = np.linalg.inv(X.T @ (X * v[:, None]))
        se = np.sqrt(np.diag(sigma2 * xtvx_inv))
    except np.linalg.LinAlgError:
        se = np.array([np.nan, np.nan])
    wmean = float(v @ logf / v.sum())
    ss_tot = float(v @ (logf - wmean) ** 2)
    ss_res = float(v @ resid**2)
    return {
        "a": float(beta[0]), "b": float(beta[1]),
        "se_a": float(se[0]), "se_b": float(se[1]),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan,
        "rmse_logpts": float(np.sqrt(np.mean(resid**2))),
    }


def daily_fits(c: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dt, g in c.groupby("date"):
        if len(g) < MIN_CONTRACTS:
            continue
        tau = g.days_to_first_notice.to_numpy(float)
        logf = np.log(g.settle.to_numpy(float))
        oi = g.open_interest.to_numpy(float)

        row = {"date": dt, "n_contracts": len(g),
               "tau_min": tau.min(), "tau_max": tau.max(), "oi_total": oi.sum()}
        row.update(fit_line(tau, logf, oi**WEIGHT_POWER))

        # Robustness: the same projection under the other weighting conventions,
        # and with a quadratic term, kept as columns so the baseline can be
        # compared with them without a second pass over the data.
        for p in ALT_WEIGHT_POWERS:
            alt = fit_line(tau, logf, oi**p)
            row[f"a_w{p}"] = alt["a"]
            row[f"b_w{p}"] = alt["b"]
        if len(g) >= 4:
            X = np.column_stack([np.ones_like(tau), tau, tau**2])
            s = np.sqrt(oi**WEIGHT_POWER)
            q, *_ = np.linalg.lstsq(X * s[:, None], logf * s, rcond=None)
            row["a_quad"], row["b_quad"], row["c_quad"] = map(float, q)
        rows.append(row)
    return pd.DataFrame(rows)


# --- Assembly ----------------------------------------------------------------

def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    fits = daily_fits(contracts())
    px = lbma_pm()
    sofr, dff, tbill = fred("SOFR"), fred("DFF"), fred("DTB3")

    d = fits.merge(px, on="date", how="inner")          # both markets open
    d = d.merge(sofr, on="date", how="left").merge(dff, on="date", how="left")
    d = d.merge(tbill, on="date", how="left")
    d = d.sort_values("date").reset_index(drop=True)

    # Overnight dollar rate: SOFR from April 2018, effective fed funds before it.
    # Both are ACT/360, so both are put on a 365 basis before use.
    d["short_rate_pct"] = d["SOFR"].fillna(d["DFF"]).ffill() * ACT360_TO_365
    d["tbill_3m_pct"] = d["DTB3"].ffill() * ACT360_TO_365

    # ---- the two reported series ----
    # Premium: a level. exp(a) is the curve extrapolated to zero horizon, i.e.
    # the price today of New York-deliverable metal.
    d["premium_log"] = d["a"] - np.log(d["lbma_pm_usd"])
    d["premium_pct"] = 100.0 * d["premium_log"]
    d["premium_usd"] = d["lbma_pm_usd"] * np.expm1(d["premium_log"])
    d["premium_se_pct"] = 100.0 * d["se_a"]

    # Carry: a rate. The slope is per calendar day, continuously compounded.
    d["carry_pct"] = 100.0 * DAYS_PER_YEAR * d["b"]
    d["carry_se_pct"] = 100.0 * DAYS_PER_YEAR * d["se_b"]
    d["carry_simple_pct"] = 100.0 * np.expm1(DAYS_PER_YEAR * d["b"])
    d["excess_carry_pp"] = d["carry_pct"] - d["short_rate_pct"]

    # Robustness columns, in the units of the reported series.
    for p in ALT_WEIGHT_POWERS:
        d[f"premium_pct_w{p}"] = 100.0 * (d[f"a_w{p}"] - np.log(d["lbma_pm_usd"]))
        d[f"carry_pct_w{p}"] = 100.0 * DAYS_PER_YEAR * d[f"b_w{p}"]
    d["premium_pct_quad"] = 100.0 * (d["a_quad"] - np.log(d["lbma_pm_usd"]))
    d["carry_pct_quad"] = 100.0 * DAYS_PER_YEAR * d["b_quad"]

    # A quality flag rather than a silent drop. The projection assumes the curve
    # is one log-linear object; on a handful of days it is not, and those days
    # should be visible as such rather than deleted or trusted.
    d["fit_ok"] = d["r2"] >= 0.90

    # Gaps are gaps: the number of calendar days since the previous observation,
    # so plotting code can break the line instead of drawing across a hole.
    d["gap_days"] = d["date"].diff().dt.days.fillna(0).astype(int)

    keep = ["date", "n_contracts", "tau_min", "tau_max", "oi_total",
            "a", "b", "se_a", "se_b", "r2", "rmse_logpts",
            "lbma_pm_usd", "short_rate_pct", "tbill_3m_pct",
            "premium_log", "premium_pct", "premium_usd", "premium_se_pct",
            "carry_pct", "carry_se_pct", "carry_simple_pct", "excess_carry_pp",
            "premium_pct_w0.0", "carry_pct_w0.0",
            "premium_pct_w1.0", "carry_pct_w1.0",
            "premium_pct_quad", "carry_pct_quad", "fit_ok", "gap_days"]
    daily = d[keep]

    m = d.set_index("date")
    monthly = pd.DataFrame({
        "n_days": m["premium_pct"].resample("MS").count(),
        "premium_pct": m["premium_pct"].resample("MS").mean(),
        "premium_pct_sd": m["premium_pct"].resample("MS").std(),
        "premium_usd": m["premium_usd"].resample("MS").mean(),
        "carry_pct": m["carry_pct"].resample("MS").mean(),
        "short_rate_pct": m["short_rate_pct"].resample("MS").mean(),
        "excess_carry_pp": m["excess_carry_pp"].resample("MS").mean(),
        "lbma_pm_usd": m["lbma_pm_usd"].resample("MS").mean(),
    }).reset_index().rename(columns={"date": "month"})
    monthly = monthly[monthly["n_days"] > 0]
    return daily, monthly


# --- Diagnostics -------------------------------------------------------------

def ols(y: np.ndarray, x: np.ndarray) -> tuple[float, float, float]:
    """Slope, intercept, R^2 of a simple regression, dropping missing rows."""
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()
    return float(beta[1]), float(beta[0]), float(r2)


def report(daily: pd.DataFrame, monthly: pd.DataFrame) -> str:
    L: list[str] = []
    P = L.append
    P("=" * 78)
    P("THE TWO SERIES")
    P("=" * 78)
    P(f"days fitted            : {len(daily):,}  "
      f"({daily.date.min():%Y-%m-%d} to {daily.date.max():%Y-%m-%d})")
    P(f"contracts per day      : median {daily.n_contracts.median():.0f}, "
      f"range {daily.n_contracts.min():.0f}-{daily.n_contracts.max():.0f}")
    P(f"weighting              : OI ** {WEIGHT_POWER} on the squared residual")
    P(f"curve fit R^2          : median {daily.r2.median():.4f}, "
      f"10th pct {daily.r2.quantile(0.10):.4f}")
    P(f"residual RMSE          : median {1e4*daily.rmse_logpts.median():.2f} "
      f"basis points of price")
    bad = daily[~daily.fit_ok]
    P(f"days with R^2 < 0.90   : {len(bad)} ({100*len(bad)/len(daily):.1f}%), of which "
      f"{len(bad[bad.date.dt.year == 2020])} fall in 2020")
    if len(bad):
        months = bad.date.dt.to_period("M").value_counts().head(4)
        P("                         worst months: "
          + ", ".join(f"{k} ({v})" for k, v in months.items()))
    P("")
    for col, unit in (("premium_pct", "% of spot"), ("premium_usd", "$/oz"),
                      ("carry_pct", "% a year"), ("excess_carry_pp", "pp a year")):
        s = daily[col]
        P(f"{col:<18} {unit:<10} mean {s.mean():8.3f}   sd {s.std():7.3f}   "
          f"min {s.min():8.3f}   max {s.max():8.3f}")
    P("")
    P(f"premium standard error : median {daily.premium_se_pct.median():.3f} pp "
      f"of spot (within-day, from the fit alone)")
    P(f"carry standard error   : median {daily.carry_se_pct.median():.3f} pp a year")

    P("")
    P("=" * 78)
    P("SANITY CHECK: DOES THE FITTED CARRY TRACK THE DOLLAR SHORT RATE?")
    P("=" * 78)
    P("No interest rate enters the fit, so agreement here is informative.")
    P("A slope near 1 means a point of SOFR shows up as a point of carry.")
    P("")
    P(f"{'sample':<22}{'n':>6}{'corr':>8}{'slope':>8}{'const':>8}{'R2':>7}"
      f"{'mean carry':>12}{'mean rate':>11}")
    eras = [("full sample", "2015-01-01", "2026-12-31"),
            ("zero rates 2015-19", "2015-01-01", "2019-12-31"),
            ("covid 2020-21", "2020-01-01", "2021-12-31"),
            ("hiking 2022-23", "2022-01-01", "2023-12-31"),
            ("cuts 2024-26", "2024-01-01", "2026-12-31")]
    for name, lo, hi in eras:
        w = daily[(daily.date >= lo) & (daily.date <= hi)]
        if w.empty:
            continue
        y, x = w.carry_pct.to_numpy(), w.short_rate_pct.to_numpy()
        slope, const, r2 = ols(y, x)
        P(f"{name:<22}{len(w):>6}{np.corrcoef(y, x)[0,1]:>8.3f}{slope:>8.3f}"
          f"{const:>8.3f}{r2:>7.3f}{y.mean():>12.3f}{x.mean():>11.3f}")

    mm = monthly.dropna(subset=["carry_pct", "short_rate_pct"])
    slope, const, r2 = ols(mm.carry_pct.to_numpy(), mm.short_rate_pct.to_numpy())
    P(f"{'monthly means':<22}{len(mm):>6}"
      f"{mm.carry_pct.corr(mm.short_rate_pct):>8.3f}{slope:>8.3f}{const:>8.3f}{r2:>7.3f}"
      f"{mm.carry_pct.mean():>12.3f}{mm.short_rate_pct.mean():>11.3f}")
    tb = daily.dropna(subset=["tbill_3m_pct"])
    P(f"{'vs 3m T-bill':<22}{len(tb):>6}{tb.carry_pct.corr(tb.tbill_3m_pct):>8.3f}"
      f"{ols(tb.carry_pct.to_numpy(), tb.tbill_3m_pct.to_numpy())[0]:>8.3f}")
    P("")
    P("In changes rather than levels. An overnight rate is a step function that")
    P("moves on eight scheduled dates a year, so a day-on-day comparison against")
    P("it is mostly noise against nothing; the three-month bill, which moves with")
    P("expectations, is the informative counterpart at daily frequency.")
    P(f"{'':<22}{'n':>6}{'corr':>8}{'slope':>8}")
    for label, rate, freq in (("d carry vs d SOFR", "short_rate_pct", "D"),
                              ("d carry vs d T-bill", "tbill_3m_pct", "D"),
                              ("m carry vs m SOFR", "short_rate_pct", "M"),
                              ("m carry vs m T-bill", "tbill_3m_pct", "M")):
        s = daily.set_index("date")[["carry_pct", rate]].dropna()
        if freq == "M":
            s = s.resample("MS").mean()
        s = s.diff().dropna()
        P(f"{label:<22}{len(s):>6}{s.carry_pct.corr(s[rate]):>8.3f}"
          f"{ols(s.carry_pct.to_numpy(), s[rate].to_numpy())[0]:>8.3f}")

    P("")
    P("=" * 78)
    P("DOES THE PREMIUM SERIES LOOK LIKE ANYTHING? (a check, not a result)")
    P("=" * 78)
    P("Largest premium days, and the most negative:")
    for _, r in daily.nlargest(5, "premium_pct").iterrows():
        P(f"   {r.date:%Y-%m-%d}  {r.premium_pct:+7.3f}%  = ${r.premium_usd:+8.2f}/oz"
          f"   ({int(r.n_contracts)} contracts, R2 {r.r2:.4f})")
    for _, r in daily.nsmallest(5, "premium_pct").iterrows():
        P(f"   {r.date:%Y-%m-%d}  {r.premium_pct:+7.3f}%  = ${r.premium_usd:+8.2f}/oz"
          f"   ({int(r.n_contracts)} contracts, R2 {r.r2:.4f})")
    P("")
    P("How much of the premium is the clock, not the market? The London leg is")
    P("struck at 15:00 London and the New York leg about three and a half hours")
    P("later, so a move in between lands in the premium. The next day's London")
    P("auction has already absorbed that move, which makes the next-day London")
    P("return a proxy for it: if the premium is partly the clock, the two should")
    P("be positively related, and they should be most related on volatile days.")
    s = daily[["date", "premium_pct", "lbma_pm_usd"]].copy()
    s["ret_next_pct"] = 100.0 * np.log(s.lbma_pm_usd.shift(-1) / s.lbma_pm_usd)
    s["abs_ret"] = s.ret_next_pct.abs()
    s = s.dropna()
    slope, const, r2 = ols(s.premium_pct.to_numpy(), s.ret_next_pct.to_numpy())
    P(f"   corr(premium_t, next-day London return) = {s.premium_pct.corr(s.ret_next_pct):.3f}"
      f"   slope {slope:.3f}   R2 {r2:.3f}")
    P(f"   {'':<26}{'n':>6}{'sd of premium':>16}{'corr':>8}")
    q = s.abs_ret.quantile([0.25, 0.75])
    for label, sub in (("calm days (|ret| < p25)", s[s.abs_ret <= q.iloc[0]]),
                       ("middle half", s[(s.abs_ret > q.iloc[0]) & (s.abs_ret < q.iloc[1])]),
                       ("volatile days (> p75)", s[s.abs_ret >= q.iloc[1]])):
        P(f"   {label:<26}{len(sub):>6}{sub.premium_pct.std():>16.3f}"
          f"{sub.premium_pct.corr(sub.ret_next_pct):>8.3f}")
    P(f"   Implied noise floor: on calm days the premium's standard deviation is")
    P(f"   {s[s.abs_ret <= q.iloc[0]].premium_pct.std():.3f} pp of spot, against "
      f"{s[s.abs_ret >= q.iloc[1]].premium_pct.std():.3f} pp on volatile ones.")
    P("")
    P("Monthly means through the tariff episode:")
    ep = monthly[(monthly.month >= "2024-10-01") & (monthly.month <= "2025-06-30")]
    P(f"   {'month':<10}{'premium %':>11}{'$/oz':>9}{'carry %':>10}"
      f"{'SOFR %':>9}{'excess pp':>11}{'days':>6}")
    for _, r in ep.iterrows():
        P(f"   {r.month:%Y-%m}   {r.premium_pct:>10.3f}{r.premium_usd:>9.2f}"
          f"{r.carry_pct:>10.3f}{r.short_rate_pct:>9.3f}{r.excess_carry_pp:>11.3f}"
          f"{int(r.n_days):>6}")

    P("")
    P("=" * 78)
    P("ROBUSTNESS: HOW MUCH DO THE SPECIFICATION CHOICES MATTER?")
    P("=" * 78)
    P(f"{'variant':<28}{'corr w/ baseline':>18}{'mean diff':>12}{'max |diff|':>12}")
    for label, col, base in (
            ("premium, unweighted", "premium_pct_w0.0", "premium_pct"),
            ("premium, OI weights", "premium_pct_w1.0", "premium_pct"),
            ("premium, quadratic fit", "premium_pct_quad", "premium_pct"),
            ("carry, unweighted", "carry_pct_w0.0", "carry_pct"),
            ("carry, OI weights", "carry_pct_w1.0", "carry_pct"),
            ("carry, quadratic fit", "carry_pct_quad", "carry_pct")):
        s = daily[[col, base]].dropna()
        diff = s[col] - s[base]
        P(f"{label:<28}{s[col].corr(s[base]):>18.4f}{diff.mean():>12.4f}"
          f"{diff.abs().max():>12.4f}")

    P("")
    P("=" * 78)
    P("COVERAGE AND GAPS")
    P("=" * 78)
    big = daily[daily.gap_days > 7]
    P(f"gaps longer than 7 days: {len(big)}")
    for _, r in big.head(12).iterrows():
        P(f"   {r.date:%Y-%m-%d}  after a {int(r.gap_days)}-day gap")
    P("")
    P("Charts must break the line at these points rather than drawing across.")
    return "\n".join(L)


def main() -> None:
    daily, monthly = build()
    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "premium_carry_daily.csv", index=False)
    monthly.to_csv(OUT / "premium_carry_monthly.csv", index=False)
    text = report(daily, monthly)
    (OUT / "build_premium_carry_output.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
