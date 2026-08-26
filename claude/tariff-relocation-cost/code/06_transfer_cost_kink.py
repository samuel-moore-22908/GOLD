"""
Step 6. Estimate the all-in cost of moving an ounce across the Atlantic from
market behaviour rather than from quoted freight rates.

Arbitrage between London and New York only pays above the full cost of doing
it: secure freight, insurance, recasting 400 oz London Good Delivery bars into
COMEX-deliverable kilobars or 100 oz bars, financing the metal in transit, and
the premium a desk demands for operational risk. Below that cost nothing moves.
That gives two ways to read the cost off the data, and this script runs both,
because they turn out to disagree in an informative way.

(1) THE BAND OF INACTION. If arbitrage is costly, the excess basis wanders
freely inside a band of width c and is pushed back only once it leaves. That is
a threshold autoregression, the standard estimator for spatial commodity
arbitrage:

    d x_t = phi_in  * x_{t-1}                              if |x_{t-1}| <= c
          = phi_out * sign(x) * (|x_{t-1}| - c)            if |x_{t-1}| >  c

with c profiled over a grid. Inside the band we expect phi_in near zero; outside
we expect phi_out clearly negative. c is then the round-trip cost in dollars per
ounce.

Measurement noise matters here and pushes the estimate the wrong way. The COMEX
leg settles at 13:30 ET and the London leg is the 15:00 London PM auction, so
the excess basis carries a non-synchronous-pricing error with a daily standard
deviation near $16/oz. Classical measurement error in the lagged level creates
spurious mean reversion, which shrinks the estimated band toward zero. The
script therefore estimates the band at daily, 5-day-average and weekly
frequency: averaging damps the timing error without touching the band, so the
estimate should rise with the averaging window and stabilise. Whatever it
converges to is an estimate; the daily figure is a lower bound.

(2) THE FLOW HINGE. flow_t = alpha + beta * mean_d in t [max(0, excess_d - c)].
This is the specification the project's earlier drafts used. It is reported here
because its profile is nearly flat -- raising c shrinks the regressor almost
proportionally, and the slope absorbs the rescaling, so the sum of squares
barely moves and the minimum lands on the boundary. That is a weak-identification
result, not evidence that the cost is zero, and saying so is the point of
keeping it in.

Inputs:  data/processed/efp_dislocation_v2.csv
         data/processed/che_gold_trade_hs4_monthly.csv
Output:  output/transfer_cost.json
"""
import json

import numpy as np
import pandas as pd

OUT = "claude/tariff-relocation-cost/output"
MIN_DTFN = 20
OZ_PER_TONNE = 32150.7
SAMPLE = ("2015-01-01", "2026-07-31")
BOOT = 1000
BLOCK = 20  # observations per bootstrap block


def load():
    b = pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])
    b = b[(b.days_to_first_notice >= MIN_DTFN)
          & (b.date >= SAMPLE[0]) & (b.date <= SAMPLE[1])].copy()
    b["month"] = b["date"].dt.to_period("M")

    t = pd.read_csv("data/processed/che_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    t = t[(t.country_iso3 == "USA") & (t.date >= SAMPLE[0]) & (t.date <= SAMPLE[1])]
    flow = (t.groupby([t.date.dt.to_period("M"), "flow"])["net_mass_kg"].sum()
            .unstack().fillna(0.0) / 1000.0)
    flow.columns = ["che_to_us_t" if c == "export" else "us_to_che_t" for c in flow.columns]
    return b, flow


def ols(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return beta, float(resid @ resid)


# ------------------------------------------------------------------ (1) TAR band

def tar_design(x_lag, c):
    inside = np.abs(x_lag) <= c
    z_in = np.where(inside, x_lag, 0.0)
    z_out = np.where(inside, 0.0, np.sign(x_lag) * (np.abs(x_lag) - c))
    return np.column_stack([np.ones(len(x_lag)), z_in, z_out])


def profile_tar(x, grid):
    dx, x_lag = np.diff(x), x[:-1]
    best, curve = None, []
    for c in grid:
        beta, ssr = ols(dx, tar_design(x_lag, c))
        curve.append({"c": float(c), "ssr": ssr,
                      "phi_in": float(beta[1]), "phi_out": float(beta[2])})
        if best is None or ssr < best["ssr"]:
            best = {"c": float(c), "ssr": ssr, "const": float(beta[0]),
                    "phi_in": float(beta[1]), "phi_out": float(beta[2]),
                    "n": int(len(dx))}
    tss = float(((dx - dx.mean()) ** 2).sum())
    best["r2"] = 1 - best["ssr"] / tss
    _, ssr_linear = ols(dx, np.column_stack([np.ones(len(x_lag)), x_lag]))
    best["r2_linear_ar1"] = 1 - ssr_linear / tss
    best["share_days_inside_band"] = float((np.abs(x_lag) <= best["c"]).mean())
    return best, curve


def bootstrap_tar(x, grid, rng, n=BOOT, block=BLOCK):
    dx, x_lag = np.diff(x), x[:-1]
    designs = {float(c): tar_design(x_lag, c) for c in grid}
    m = len(dx)
    n_blocks = int(np.ceil(m / block))
    draws = []
    for _ in range(n):
        starts = rng.integers(0, m - block + 1, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:m]
        best_c, best_ssr = None, np.inf
        yb = dx[idx]
        for c, X in designs.items():
            _, ssr = ols(yb, X[idx])
            if ssr < best_ssr:
                best_ssr, best_c = ssr, c
        draws.append(best_c)
    return np.array(draws, dtype=float)


# ------------------------------------------------------------------ (2) flow hinge

def hinge_monthly(b, c, direction):
    sign = 1.0 if direction == "west" else -1.0
    return np.maximum(0.0, sign * b["excess_basis_usd"] - c).groupby(b["month"]).mean()


def profile_hinge(b, flow, direction, grid):
    y = (flow["che_to_us_t"] if direction == "west" else flow["us_to_che_t"]).to_numpy()
    idx = flow.index
    best, curve = None, []
    for c in grid:
        x = hinge_monthly(b, c, direction).reindex(idx).fillna(0.0).to_numpy()
        if x.std() == 0:
            continue
        beta, ssr = ols(y, np.column_stack([np.ones(len(x)), x]))
        tss = float(((y - y.mean()) ** 2).sum())
        curve.append({"c": float(c), "ssr": ssr, "beta": float(beta[1]),
                      "r2": 1 - ssr / tss})
        if best is None or ssr < best["ssr"]:
            best = {"c": float(c), "ssr": ssr, "alpha": float(beta[0]),
                    "beta": float(beta[1]), "r2": 1 - ssr / tss}
    return best, curve


def main():
    b, flow = load()
    rng = np.random.default_rng(20260826)
    results = {
        "sample": list(SAMPLE),
        "n_daily_obs": int(len(b)),
        "n_months": int(len(flow)),
        "units": "USD per troy ounce unless stated",
    }

    # ---- (1) band of inaction at three sampling frequencies
    grid = np.round(np.arange(0.0, 60.01, 0.25), 2)
    s = b.set_index("date")["excess_basis_usd"]
    series = {
        "daily": s,
        "mean_5day": s.rolling(5).mean().dropna().iloc[::5],
        "weekly_last": s.resample("W-FRI").last().dropna(),
    }
    band = {}
    for name, ser in series.items():
        x = ser.to_numpy(dtype=float)
        best, curve = profile_tar(x, grid)
        draws = bootstrap_tar(x, grid, rng)
        lo, hi = np.percentile(draws, [5, 95])
        band[name] = {
            "n_obs": int(len(x)),
            "half_width_usd_per_oz": best["c"],
            "ci90_usd_per_oz": [float(lo), float(hi)],
            "phi_inside_band": best["phi_in"],
            "phi_outside_band": best["phi_out"],
            "share_obs_inside_band": best["share_days_inside_band"],
            "r2": best["r2"],
            "r2_linear_ar1": best["r2_linear_ar1"],
            "profile_curve": curve[::8],
        }
    results["band_of_inaction"] = band
    results["band_note"] = (
        "The half-width is the one-way cost: the basis has to clear c before "
        "westbound arbitrage pays and fall below -c before eastbound arbitrage "
        "pays. The estimate rises with the averaging window, which is what "
        "attenuation from non-synchronous pricing predicts; the daily figure is "
        "therefore a lower bound and the weekly one the preferred estimate.")

    # The band estimator does not identify anything here, and the diagnostics say
    # so plainly rather than leaving a number to be quoted.
    ci_widths = {k: v["ci90_usd_per_oz"][1] - v["ci90_usd_per_oz"][0] for k, v in band.items()}
    phi_out = {k: v["phi_outside_band"] for k, v in band.items()}
    results["band_verdict"] = {
        "identified": False,
        "point_estimates_usd_per_oz": {k: v["half_width_usd_per_oz"] for k, v in band.items()},
        "ci90_widths_usd_per_oz": ci_widths,
        "phi_outside_band": phi_out,
        "share_inside_band": {k: v["share_obs_inside_band"] for k, v in band.items()},
        "diagnosis": (
            "The three frequencies give $0.00, $26.00 and $0.75 with confidence "
            "intervals spanning most of the grid, and the outside-band reversion "
            "coefficient sits near -1 at every frequency. A coefficient of -1 means "
            "the series fully reverts in one period: it is white noise around zero, "
            "not a price wandering inside a band and being pushed back at its edges. "
            "The 5-day fit puts 99 percent of observations INSIDE the band and has "
            "the inside regime doing the reverting, which is the model backwards. "
            "The reading is that the excess basis built from a 13:30 ET COMEX "
            "settlement against a 15:00 London PM auction is dominated by "
            "non-synchronous pricing error at daily-to-weekly frequency, and that "
            "error swamps the band. This does not affect the event study, where the "
            "moves being tested are two to four standard deviations of that same "
            "noise and inference is randomization-based against it; it does mean the "
            "transfer cost cannot be read off this series. Identifying it properly "
            "needs a real dealer EFP quote series or intraday-matched prices."),
        "consequence": ("The cost ledger uses the bottom-up build below as an assumed "
                        "range with explicit sensitivity, not a data-derived point "
                        "estimate."),
    }
    c_hat = band["weekly_last"]["half_width_usd_per_oz"]

    # ---- (2) flow hinge, reported for the record
    hinge = {}
    for direction, label in (("west", "Switzerland -> United States"),
                             ("east", "United States -> Switzerland")):
        best, curve = profile_hinge(b, flow, direction, np.round(np.arange(0, 40.01, 0.5), 2))
        linear, _ = profile_hinge(b, flow, direction, np.array([0.0]))
        r2s = [p["r2"] for p in curve]
        hinge[direction] = {
            "corridor": label,
            "argmin_c_usd_per_oz": best["c"],
            "beta_tonnes_per_month_per_usd_per_oz": best["beta"],
            "alpha_tonnes_per_month": best["alpha"],
            "r2_at_argmin": best["r2"],
            "r2_at_c_zero": linear["r2"],
            "r2_range_across_grid": [min(r2s), max(r2s)],
            "identification": (
                "weak: the R-squared varies by {:.4f} across the whole grid, so the "
                "profile is close to flat and the argmin is not informative about c"
            ).format(max(r2s) - min(r2s)),
            "profile_curve": curve[::4],
        }
    results["flow_hinge"] = hinge

    # ---- (3) bottom-up build of the one-way relocation cost
    #
    # Real resources are separated from pure financing. Recasting, freight,
    # insurance and handling consume labour, energy, capital and airframe hours:
    # they are deadweight, and the world is poorer by that amount whether or not
    # the metal ever needed to move. Financing is different. The owner was paying
    # to carry the metal in a London vault anyway, so shipping it does not add a
    # full short rate; what it adds is the value of the metal's foregone use
    # while it is in the air and being re-assayed, which is the gold lease rate,
    # not SOFR. Charging the full short rate to transit, as the first draft of
    # this script did, roughly triples the estimate and attributes to the
    # tariff episode a cost that would have been borne regardless.
    spot = float(b.loc[b.date >= "2024-10-01", "lbma_pm_usd"].mean())
    transit_days = [10, 20]
    lease_rate = [0.005, 0.030]  # gold lease rates, calm to squeezed
    build = {
        "reference_spot_usd_per_oz": spot,
        "real_resource_components_usd_per_oz": {
            "recasting_400oz_to_kilobar_or_100oz": [0.50, 2.00],
            "secure_air_freight_transatlantic": [0.30, 1.00],
            "insurance_in_transit": [0.10, 0.50],
            "handling_assay_vault_in_and_out": [0.20, 0.80],
        },
        "financing_component_usd_per_oz": {
            "foregone_lease_income_in_transit": [
                round(spot * lease_rate[0] * transit_days[0] / 365, 3),
                round(spot * lease_rate[1] * transit_days[1] / 365, 3)],
        },
        "assumptions": {
            "transit_days": transit_days,
            "gold_lease_rate_range": lease_rate,
            "note": (
                "The recasting, freight, insurance and handling ranges are "
                "order-of-magnitude assumptions, not quoted prices: no public "
                "series for bullion logistics or refining fees exists, and the "
                "band estimator above could not supply one. They are stated as "
                "ranges and the ledger carries the sensitivity through to the "
                "headline. Only the financing line is derived, from the mean spot "
                "price over the episode and an assumed lease-rate range."),
        },
    }
    rr = build["real_resource_components_usd_per_oz"]
    fin = build["financing_component_usd_per_oz"]
    lo = sum(v[0] for v in rr.values())
    hi = sum(v[1] for v in rr.values())
    flo = sum(v[0] for v in fin.values())
    fhi = sum(v[1] for v in fin.values())
    build["real_resource_total_usd_per_oz"] = [round(lo, 2), round(hi, 2)]
    build["all_in_total_usd_per_oz"] = [round(lo + flo, 2), round(hi + fhi, 2)]
    build["real_resource_total_usd_per_tonne"] = [round(lo * OZ_PER_TONNE),
                                                  round(hi * OZ_PER_TONNE)]
    build["all_in_total_usd_per_tonne"] = [round((lo + flo) * OZ_PER_TONNE),
                                           round((hi + fhi) * OZ_PER_TONNE)]
    results["bottom_up_build"] = build

    with open(OUT + "/transfer_cost.json", "w") as f:
        json.dump(results, f, indent=2)

    print("BAND OF INACTION IN THE EXCESS BASIS\n")
    print("{:<12} {:>6} {:>10} {:>18} {:>9} {:>9} {:>8}".format(
        "frequency", "n", "c ($/oz)", "90% CI", "phi_in", "phi_out", "inside"))
    for name, r in band.items():
        print("{:<12} {:>6} {:>10.2f} {:>8.2f} - {:<7.2f} {:>9.3f} {:>9.3f} {:>7.0%}".format(
            name, r["n_obs"], r["half_width_usd_per_oz"], *r["ci90_usd_per_oz"],
            r["phi_inside_band"], r["phi_outside_band"], r["share_obs_inside_band"]))
    print("\nVERDICT: not identified. Point estimates {}, CI widths {}.".format(
        results["band_verdict"]["point_estimates_usd_per_oz"],
        {k: round(v, 1) for k, v in results["band_verdict"]["ci90_widths_usd_per_oz"].items()}))
    print("phi_outside_band near -1 at every frequency => white noise, not a band.")

    print("\nFLOW HINGE (reported for the record)")
    for d, r in hinge.items():
        print("  {:<30} argmin c = ${:.1f}, R2 range across grid = {:.4f}".format(
            r["corridor"], r["argmin_c_usd_per_oz"],
            r["r2_range_across_grid"][1] - r["r2_range_across_grid"][0]))

    print("\nBOTTOM-UP BUILD, one way")
    print("  real resources only : ${:.2f} - ${:.2f}/oz  (${:,.0f} - ${:,.0f} per tonne)".format(
        *build["real_resource_total_usd_per_oz"], *build["real_resource_total_usd_per_tonne"]))
    print("  all in incl. finance: ${:.2f} - ${:.2f}/oz  (${:,.0f} - ${:,.0f} per tonne)".format(
        *build["all_in_total_usd_per_oz"], *build["all_in_total_usd_per_tonne"]))


if __name__ == "__main__":
    main()
