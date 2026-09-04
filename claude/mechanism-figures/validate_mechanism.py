"""
Check that the three proposed mechanism figures are actually buildable, and
print every number FIGURE_PLAN.md quotes.

This is a feasibility pass, not the figures themselves. Those get built in Stata
like the rest of the paper's exhibits; the point here is to establish, before any
of that work is done, that the series behave the way the plan says they do.

Three things it settles.

1. THE EXISTING EFP SERIES CANNOT CARRY FIGURE 2 AS SPECIFIED. Both candidate
   measures in data/processed/efp_dislocation_v2.csv are contaminated by the
   delivery calendar. The raw dollar basis carries the roll sawtooth
   RESEARCH_DOSSIER.md already warns about. The annualised front-month rate has
   the mirror-image problem: implied_rate divides by days_to_first_notice, so it
   explodes as delivery approaches. On 12 Nov 2025 a $76.85 basis with 16 days
   left prints as a 42% annualised rate. That is a calendar artefact, not a
   dislocation, and it is the largest value in the whole series.

   The fix is a constant-maturity spread: fit the liquid part of the futures
   curve each day and read it at a fixed 90-day horizon. Neither artefact can
   survive it, because the horizon never changes.

2. THE HINGE IS REAL AND IT IS NOT AN ARTEFACT OF THE TARIFF EPISODE. Bucketing
   139 months on the constant-maturity dislocation, Swiss shipments to the US sit
   flat at 2-3 t/month from -1pp all the way to +0.5pp and then step to a 64 t
   median above +1.5pp. The months in that top bucket are COVID (2020), the
   sanctions shock (Mar 2022) and the tariff scare (2025) - three unrelated
   causes, one response.

3. THE RETURN LEG IS NOT PRICED. US shipments to Switzerland do not respond to
   the dislocation in either direction (r = -0.09), nor to a six-month inventory
   overhang (r = -0.04). This CONTRADICTS the "sign is directional" claim in
   CLAUDE.md, which predicts eastbound flow when New York is cheap. It is not
   what the data says, and the asymmetry is a result rather than a nuisance.

Reads   data/processed/comex_contract_daily.csv
        data/processed/efp_dislocation_v2.csv
        data/processed/bilateral_panel_2015_2026.csv
        data/processed/us_hs4_universe_monthly.csv
Writes  claude/mechanism-figures/mechanism_monthly.csv   (the Fig 3/4 panel)
        claude/mechanism-figures/dislocation_daily.csv   (the Fig 2 series)
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("claude/mechanism-figures")

# The horizon to read the curve at. Long enough to sit clear of the delivery
# scramble, short enough that the fit is over contracts people actually trade.
HORIZON = 90
# Contracts entering the fit. Below 15 days the front month is in its delivery
# window and stops behaving like a forward; above 400 days open interest is a
# rounding error. The 1,000-lot floor drops the deferred contracts that carry a
# handful of lots and a stale settle.
MIN_DAYS, MAX_DAYS, MIN_OI = 15, 400, 1000
# The window the "arbitrage-pinned" band on Figure 2 is measured over: after the
# 2024 rate cuts started and before the election, so it is neither the zero-rate
# era nor the episode.
CALM = ("2024-06-01", "2024-11-30")


def constant_maturity():
    """Daily COMEX-London dislocation at a fixed 90-day horizon, in excess of carry."""
    c = pd.read_csv("data/processed/comex_contract_daily.csv", parse_dates=["date"])
    e = pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])

    c = c[c.days_to_first_notice.between(MIN_DAYS, MAX_DAYS)]
    c = c[(c.open_interest.fillna(0) >= MIN_OI) & c.settle.notna()]

    rows = []
    for dt, g in c.groupby("date"):
        if len(g) < 2:
            continue
        # Log-linear in days, weighted by sqrt(open interest). The curve is a
        # financing curve, so it is close to log-linear by construction; the
        # weighting stops a thin deferred contract tilting the fit.
        x = g.days_to_first_notice.to_numpy(float)
        y = np.log(g.settle.to_numpy(float))
        w = np.sqrt(g.open_interest.to_numpy(float))
        slope, intercept = np.polyfit(x, y, 1, w=w)
        rows.append((dt, float(np.exp(intercept + slope * HORIZON)), len(g)))

    f = pd.DataFrame(rows, columns=["date", "f90", "n_contracts"])
    f = f.merge(e[["date", "lbma_pm_usd", "short_rate", "carry_rate",
                   "storage_rate_assumed"]], on="date")
    f = f.dropna(subset=["lbma_pm_usd"])

    # Annualised, then net of carry, so the near-zero-rate era and the 4-5% era
    # are on the same scale.
    f["implied_rate"] = (f.f90 / f.lbma_pm_usd - 1) * 365 / HORIZON
    f["disloc"] = f.implied_rate - f.carry_rate
    f["disloc_pp"] = f.disloc * 100
    # The same thing in $/oz over the 90 days, which is the unit a shipping
    # decision is actually taken in.
    f["excess_usd"] = (f.disloc * HORIZON / 365) * f.lbma_pm_usd
    # 10 sessions. COMEX settles at 13:30 New York, the LBMA PM fix is struck
    # around 10:00 there, so a 1% intraday move puts ~4pp of pure timing noise
    # into a single day's annualised figure. Smoothing is not decoration here.
    f["disloc_pp_10d"] = f.disloc_pp.rolling(10, min_periods=6).mean()
    return f.set_index("date").sort_index()


def swiss_tonnes():
    """Swiss customs gold trade with the US, tonnes per month, both directions."""
    b = pd.read_csv("data/processed/bilateral_panel_2015_2026.csv", parse_dates=["date"])
    ch = b[(b.reporter_iso3 == "CHE") & (b.country_iso3 == "USA")]
    t = ch.groupby(["date", "flow"])["net_mass_kg"].sum().unstack().div(1000)
    return t.rename(columns={"export": "che_to_us_t", "import": "us_to_che_t"})


def rule(s):
    print(f"\n{'=' * 78}\n{s}\n{'=' * 78}")


def main():
    pd.set_option("display.width", 200)
    daily = constant_maturity()

    rule("1  Why the front month cannot be used: the calendar artefacts")
    e = pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])
    ep = e[e.date.between("2024-10-01", "2025-12-31")]
    worst = ep.nlargest(5, "dislocation")[
        ["date", "active_contract", "basis_usd", "days_to_first_notice",
         "implied_rate", "dislocation"]]
    print("Largest front-month 'dislocations' in the episode window.\n"
          "Every one is within 16 days of first notice - that is the divisor,\n"
          "not the market:")
    print(worst.to_string(index=False))
    print(f"\nRoll sawtooth in the raw basis: days_to_first_notice ranges "
          f"{ep.days_to_first_notice.min():.0f}-{ep.days_to_first_notice.max():.0f} "
          f"days over the same window.")

    rule("2  Figure 2: the constant-maturity dislocation")
    calm = daily.loc[CALM[0]:CALM[1], "disloc_pp_10d"]
    print(f"Calm window {CALM[0]} to {CALM[1]}: "
          f"mean {calm.mean():+.2f} pp, sd {calm.std():.2f} pp  "
          f"(the 'arbitrage-pinned' band on the figure is +/- 1 sd)")
    mo = daily.disloc_pp_10d.groupby(daily.index.strftime("%Y-%m")).agg(["mean", "max"])
    print("\nSmoothed series by month, pp annualised:")
    print(mo.loc["2024-09":"2025-12"].round(2).to_string())
    jan = daily.disloc_pp_10d.loc["2025-01"]
    peak = jan.idxmax()
    print(f"\nPeak of the tariff episode: {peak.date()} at {jan.max():.2f} pp "
          f"(${daily.loc[peak, 'excess_usd']:.0f}/oz over 90 days)")
    print(f"For scale, the largest smoothed value anywhere in 2015-2026 is "
          f"{daily.disloc_pp_10d.max():.2f} pp on "
          f"{daily.disloc_pp_10d.idxmax():%d %b %Y} - the COVID dislocation.")
    gaps = daily.index.to_series().diff().dt.days
    print(f"Gaps over 5 calendar days in the daily series: {int((gaps > 5).sum())} "
          f"- draw them as gaps, do not interpolate.")

    rule("3  Figures 3 and 4: the monthly panel")
    mon = daily.disloc_pp.groupby(daily.index.to_period("M")).mean()
    mon.index = mon.index.to_timestamp()
    m = pd.concat([mon.rename("disloc_pp"), swiss_tonnes()], axis=1, sort=True)
    m = m.dropna().loc["2015-01-01":]
    print(f"n = {len(m)} months, {m.index.min():%Y-%m} to {m.index.max():%Y-%m}")

    print("\nFigure 3 - the hinge. Swiss shipments TO the US by dislocation bucket:")
    edges = [-99, -0.5, 0, 0.5, 1.0, 1.5, 99]
    names = ["< -0.5", "-0.5 to 0", "0 to 0.5", "0.5 to 1", "1 to 1.5", "> 1.5"]
    m["bucket"] = pd.cut(m.disloc_pp, edges, labels=names)
    print(m.groupby("bucket", observed=True).agg(
        n=("che_to_us_t", "size"), median_t=("che_to_us_t", "median"),
        mean_t=("che_to_us_t", "mean"), max_t=("che_to_us_t", "max")).round(1).to_string())
    print(f"\ncorrelation, contemporaneous: {m.disloc_pp.corr(m.che_to_us_t):+.3f}"
          f"   at one month's lag: {m.disloc_pp.corr(m.che_to_us_t.shift(-1)):+.3f}"
          f"   Spearman: {m.disloc_pp.corr(m.che_to_us_t, method='spearman'):+.3f}")
    print("Contemporaneous beats lagged: Zurich to New York is a flight, and the\n"
          "shipment is recorded when it leaves. Spearman is far below Pearson\n"
          "because the relationship is a hinge, not a slope - which is the point.")

    top = m.nlargest(10, "che_to_us_t")[["che_to_us_t", "disloc_pp"]]
    print("\nThe ten largest westbound months in eleven years:")
    print(top.round(1).to_string())
    print(f"Positive dislocation in {int((top.disloc_pp > 0).sum())} of 10.")

    print("\nFigure 4 - the return leg. Same buckets, US shipments TO Switzerland:")
    print(m.groupby("bucket", observed=True).agg(
        n=("us_to_che_t", "size"), median_t=("us_to_che_t", "median"),
        mean_t=("us_to_che_t", "mean")).round(1).to_string())
    print(f"\ncorrelation with the dislocation: {m.disloc_pp.corr(m.us_to_che_t):+.3f}"
          f"   at one month's lag: {m.disloc_pp.corr(m.us_to_che_t.shift(-1)):+.3f}")

    # Does the return instead track an inventory overhang? It does not.
    base = (m.loc["2015":"2019", "che_to_us_t"].mean()
            - m.loc["2015":"2019", "us_to_che_t"].mean())
    m["overhang"] = ((m.che_to_us_t - m.us_to_che_t) - base).rolling(6, min_periods=6).sum()
    ov = m.dropna(subset=["overhang"])
    print(f"...and with a six-month inventory overhang: "
          f"{ov.overhang.shift(1).corr(ov.us_to_che_t):+.3f}")
    print("\nNeither. CLAUDE.md's 'sign is directional' prediction does not hold:\n"
          "the outbound leg is arbitrage and is priced, the return is an unwind\n"
          "that happens once the premium is gone, not once it inverts.")
    print("\nThe six largest eastbound months in eleven years:")
    print(m.nlargest(6, "us_to_che_t")[["us_to_che_t", "disloc_pp"]].round(1).to_string())

    rule("4  What is NOT buildable from what is in hand")
    s = pd.read_csv("data/processed/comex_gold_stocks_daily.csv", parse_dates=["date"])
    ep_s = s[s.date.between("2025-01-01", "2026-01-31")]
    print(f"COMEX warehouse stocks: {len(ep_s)} snapshots between Jan 2025 and Jan 2026 "
          f"({', '.join(d.strftime('%d %b %y') for d in ep_s.date)}).")
    print(f"That is {len(ep_s)} points, not a series. The Wayback file cannot carry a\n"
          "vault build-and-drain figure; it needs the direct CME pull, which is item 1\n"
          "of CLAUDE.md's build order and is not actually done.")
    u = pd.read_csv("data/processed/us_hs4_universe_monthly.csv", dtype={"hs4": str})
    print(f"\nUS HS4 universe quantities: {(u.qty > 0).sum()} of {len(u)} rows carry one; "
          f"units present: {sorted(u.unit.unique())}.")
    print("The pull requested GEN_QY1_MO/QTY_1_MO but Census returned nothing at the\n"
          "country-aggregated HS4 level, so a value-density figure - the cleanest answer\n"
          "to 'why gold and not cars' - needs an HS6 or HS10 re-pull first.")

    OUT.mkdir(parents=True, exist_ok=True)
    m.drop(columns="bucket").to_csv(OUT / "mechanism_monthly.csv")
    daily[["f90", "lbma_pm_usd", "carry_rate", "disloc_pp", "disloc_pp_10d",
           "excess_usd", "n_contracts"]].to_csv(OUT / "dislocation_daily.csv")
    print(f"\nwrote {OUT / 'mechanism_monthly.csv'} and {OUT / 'dislocation_daily.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
