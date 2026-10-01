"""
Step 4. How much metal moved because of the tariff threat, rather than for any
other reason.

The event study in step 3 shows that tariff news moved the price of location.
This step asks the quantity question, and it has to answer it with a
counterfactual, because the cost ledger needs excess tonnes, not gross tonnes.
Gross Swiss-US flow was large in 2020 as well, for reasons that had nothing to
do with tariffs.

DESIGN. Switzerland's gold exports are a panel: one series per destination,
monthly, in tonnes. The United States is the treated corridor; every other
destination with a continuous flow is a control. A two-way fixed-effects event
study,

    y_ct = a_c + d_t + sum_k beta_k * 1[c = US] * 1[t = t0 + k] + e_ct

with October 2024 as the omitted reference month, gives beta_k as the tonnes per
month by which the US corridor departed from what the destination's own average
level and the month's common shock would predict.

INFERENCE is by in-space placebo, in the spirit of Abadie's synthetic-control
inference. The whole estimation is re-run pretending each control corridor was
treated. If the US effect is not an outlier in that distribution, the design has
found nothing. With a donor pool of this size the smallest attainable p-value is
1/(donors+1), which is stated rather than dressed up.

THE ASSUMPTION THAT WILL BE CHALLENGED is no interference between corridors.
Swiss refining and secure-logistics capacity is finite over a few months, so
metal pointed at New York may be metal not pointed at Mumbai. If so, the control
corridors fall when the treated one rises, and the difference-in-differences
overstates the US-specific effect. The script tests this directly -- did total
Swiss exports rise, or only get redirected -- and reports a treated-unit-only
before-and-after estimate as the lower bound of the range. It also reports the
displacement itself, because gold that did not reach a consumption market during
the surge is a cost of the episode in its own right, not a nuisance.

Inputs:  output/che_gold_trade_all_partners_monthly.csv (from 02)
Output:  output/flow_did.json, output/flow_counterfactual.csv
"""
import json

import numpy as np
import pandas as pd

OUT = "claude/tariff-relocation-cost/output"
PANEL = OUT + "/che_gold_trade_all_partners_monthly.csv"

SAMPLE = ("2015-01-01", "2026-07-31")
REFERENCE = pd.Period("2024-10", "M")          # last clean pre-treatment month
SURGE = (pd.Period("2024-12", "M"), pd.Period("2025-03", "M"))
RETURN_LEG = (pd.Period("2025-04", "M"), pd.Period("2026-07", "M"))
# Donor admission. These are deliberately loose: the placebo p-value cannot go
# below 1/(donors+1), so a thin pool caps the inference before the data does. A
# corridor only has to be a real, recurring corridor rather than a large one.
MIN_ACTIVE_SHARE = 0.80                        # traded in 80% of pre-reference months
MIN_MEAN_TONNES = 0.20                         # and averaged at least 0.2 t/month


def load_panel(flow):
    d = pd.read_csv(PANEL, parse_dates=["date"])
    d = d[(d.flow == flow) & (d.date >= SAMPLE[0]) & (d.date <= SAMPLE[1])]
    wide = (d.groupby([d.date.dt.to_period("M"), "partner_iso2"])["net_mass_kg"]
            .sum().unstack().fillna(0.0) / 1000.0)
    return wide.sort_index()


def pick_donors(wide, treated="US"):
    pre = wide.loc[:REFERENCE]
    active = (pre > 0).mean()
    size = pre.mean()
    ok = active[(active >= MIN_ACTIVE_SHARE) & (size >= MIN_MEAN_TONNES)].index
    return [c for c in ok if c != treated]


def twfe_event_study(wide, treated, donors, k_range=(-24, 21)):
    """Return event-time coefficients and the implied counterfactual for the
    treated corridor, from a two-way fixed-effects regression in levels."""
    units = [treated] + donors
    panel = wide[units].stack()
    panel.index.names = ["month", "unit"]
    df = panel.rename("y").reset_index()
    df["k"] = (df["month"] - REFERENCE).apply(lambda x: x.n)
    df["treated"] = (df["unit"] == treated).astype(float)

    ks = [k for k in range(k_range[0], k_range[1] + 1)
          if k != 0 and (df.k == k).any()]
    cols = {"unit_" + u: (df.unit == u).astype(float) for u in units[1:]}
    cols.update({"time_" + str(m): (df.month == m).astype(float)
                 for m in sorted(df.month.unique())[1:]})
    cols.update({"evt_" + str(k): df.treated * (df.k == k) for k in ks})

    X = np.column_stack([np.ones(len(df))] + [c.to_numpy(dtype=float) for c in cols.values()])
    names = ["const"] + list(cols)
    beta, *_ = np.linalg.lstsq(X, df.y.to_numpy(dtype=float), rcond=None)
    coef = dict(zip(names, beta))

    resid = df.y.to_numpy(dtype=float) - X @ beta
    # Cluster-robust variance, clustering on unit. With this few clusters the
    # asymptotics are not to be trusted; it is reported alongside the placebo
    # distribution, which is what the inference actually rests on.
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros_like(XtX_inv)
    for u in units:
        m = (df.unit == u).to_numpy()
        Xu, ru = X[m], resid[m]
        s = Xu.T @ ru
        meat += np.outer(s, s)
    V = XtX_inv @ meat @ XtX_inv
    se = dict(zip(names, np.sqrt(np.clip(np.diag(V), 0, None))))

    events = {k: {"coef": float(coef["evt_" + str(k)]),
                  "se_cluster": float(se["evt_" + str(k)]),
                  "month": str(REFERENCE + k)} for k in ks}

    # Counterfactual for the treated corridor: fitted value with every event
    # dummy switched off.
    mask = df.treated.to_numpy() == 1
    Xc = X[mask].copy()
    for j, n in enumerate(names):
        if n.startswith("evt_"):
            Xc[:, j] = 0.0
    cf = pd.Series(Xc @ beta, index=df.loc[mask, "month"].to_numpy())
    actual = wide.loc[cf.index, treated]
    return events, pd.DataFrame({"actual_t": actual, "counterfactual_t": cf.reindex(actual.index)})


def att(events, window):
    ks = [k for k in events
          if window[0] <= pd.Period(events[k]["month"], "M") <= window[1]]
    vals = [events[k]["coef"] for k in ks]
    return {"months": len(vals), "mean_tonnes_per_month": float(np.mean(vals)),
            "total_tonnes": float(np.sum(vals)),
            "window": [str(window[0]), str(window[1])]}


def run_direction(wide, treated, label, windows):
    donors = pick_donors(wide, treated)
    events, cf = twfe_event_study(wide, treated, donors)
    out = {"label": label, "treated": treated, "n_donors": len(donors),
           "donors": donors, "event_coefficients": events, "att": {}}
    for name, w in windows.items():
        out["att"][name] = att(events, w)

    # in-space placebo
    placebo = {}
    for d in donors:
        pool = [x for x in donors if x != d]
        try:
            ev_d, _ = twfe_event_study(wide, d, pool)
        except np.linalg.LinAlgError:
            continue
        placebo[d] = {name: att(ev_d, w)["total_tonnes"] for name, w in windows.items()}
    out["placebo_by_donor"] = placebo
    out["placebo_rank"] = {}
    for name in windows:
        actual_val = out["att"][name]["total_tonnes"]
        vals = np.array([v[name] for v in placebo.values()])
        rank = int((np.abs(vals) >= abs(actual_val)).sum()) + 1
        out["placebo_rank"][name] = {
            "treated_total_tonnes": actual_val,
            "n_placebos": int(vals.size),
            "placebos_at_least_as_large_in_abs": rank - 1,
            "rank_of_treated": rank,
            "p_value": rank / (vals.size + 1),
            "smallest_attainable_p": 1 / (vals.size + 1),
            "placebo_abs_median_tonnes": float(np.median(np.abs(vals))),
            "placebo_abs_max_tonnes": float(np.max(np.abs(vals))),
        }

    # Pre-trend. The design is only credible if the treated corridor was not
    # already drifting away from the controls before the treatment date.
    pre_ks = sorted(k for k in events if -18 <= k <= -1)
    pre_vals = np.array([events[k]["coef"] for k in pre_ks])
    out["pre_trend"] = {
        "months_tested": len(pre_ks),
        "mean_abs_coef_tonnes": float(np.abs(pre_vals).mean()),
        "max_abs_coef_tonnes": float(np.abs(pre_vals).max()),
        "coefficients": {str(REFERENCE + k): float(events[k]["coef"]) for k in pre_ks},
        "ratio_surge_att_to_mean_abs_pre": None,  # filled by caller
    }

    # treated-only before/after, as the lower bound
    pre = wide.loc[:REFERENCE, treated]
    pre_mean = float(pre.loc["2015-01":].mean())
    for name, w in windows.items():
        act = wide.loc[w[0]:w[1], treated]
        out["att"][name]["treated_only_excess_tonnes"] = float(act.sum() - pre_mean * len(act))
        out["att"][name]["actual_total_tonnes"] = float(act.sum())
        out["att"][name]["pre_period_mean_tonnes_per_month"] = pre_mean
    out["pre_trend"]["ratio_surge_att_to_mean_abs_pre"] = (
        abs(out["att"]["surge"]["mean_tonnes_per_month"])
        / out["pre_trend"]["mean_abs_coef_tonnes"])
    return out, cf, donors


def main():
    exp = load_panel("export")   # Switzerland -> partner
    imp = load_panel("import")   # partner -> Switzerland

    results = {
        "sample": list(SAMPLE),
        "reference_month": str(REFERENCE),
        "donor_rule": ("traded in at least {:.0%} of pre-reference months and averaged "
                       "at least {} t/month".format(MIN_ACTIVE_SHARE, MIN_MEAN_TONNES)),
        "windows": {"surge": [str(SURGE[0]), str(SURGE[1])],
                    "return_leg": [str(RETURN_LEG[0]), str(RETURN_LEG[1])]},
    }

    west, cf_west, donors = run_direction(
        exp, "US", "Swiss gold exports to the United States",
        {"surge": SURGE, "return_leg": RETURN_LEG})
    results["westbound"] = west

    east, cf_east, _ = run_direction(
        imp, "US", "Swiss gold imports from the United States",
        {"surge": SURGE, "return_leg": RETURN_LEG})
    results["eastbound"] = east

    # ---- interference check: did the pie grow, or was it redirected?
    tot = exp.sum(axis=1)
    donor_tot = exp[donors].sum(axis=1)
    pre_tot = float(tot.loc["2015-01":REFERENCE].mean())
    pre_donor = float(donor_tot.loc["2015-01":REFERENCE].mean())
    surge_tot = float(tot.loc[SURGE[0]:SURGE[1]].mean())
    surge_donor = float(donor_tot.loc[SURGE[0]:SURGE[1]].mean())
    us_rise = float(exp.loc[SURGE[0]:SURGE[1], "US"].mean()
                    - exp.loc["2015-01":REFERENCE, "US"].mean())
    donor_fall = surge_donor - pre_donor
    results["interference"] = {
        "total_swiss_exports_pre_mean_t_per_month": pre_tot,
        "total_swiss_exports_surge_mean_t_per_month": surge_tot,
        "total_change_t_per_month": surge_tot - pre_tot,
        "us_corridor_change_t_per_month": us_rise,
        "donor_corridors_change_t_per_month": donor_fall,
        "share_of_us_rise_offset_by_donor_fall": (-donor_fall / us_rise) if us_rise else None,
        "reading": (
            "If the donor corridors fell by roughly as much as the US corridor "
            "rose, Swiss refining output was redirected rather than expanded, the "
            "no-interference assumption fails, and the difference-in-differences "
            "figure is an upper bound on the US-specific effect. The offset share "
            "is the diagnostic; the treated-only estimate is the matching lower "
            "bound."),
    }
    per_donor_change = (exp.loc[SURGE[0]:SURGE[1], donors].mean()
                        - exp.loc["2015-01":REFERENCE, donors].mean())
    results["interference"]["per_donor_change_t_per_month"] = {
        k: float(v) for k, v in per_donor_change.sort_values().items()}

    # ---- what the ledger needs
    surge_did = west["att"]["surge"]["total_tonnes"]
    surge_lo = west["att"]["surge"]["treated_only_excess_tonnes"]
    ret_did = east["att"]["return_leg"]["total_tonnes"]
    ret_lo = east["att"]["return_leg"]["treated_only_excess_tonnes"]
    results["excess_tonnage_for_ledger"] = {
        "westbound_surge_t": {"did": surge_did, "treated_only": surge_lo,
                              "range": sorted([surge_did, surge_lo])},
        "eastbound_return_t": {"did": ret_did, "treated_only": ret_lo,
                               "range": sorted([ret_did, ret_lo])},
        "round_trip_t": {"did": surge_did + ret_did,
                         "treated_only": surge_lo + ret_lo,
                         "range": sorted([surge_did + ret_did, surge_lo + ret_lo])},
        "note": ("The round trip counts both legs, because both legs consumed "
                 "freight, insurance and handling. Only the westbound leg required "
                 "recasting into COMEX-deliverable bars; the ledger charges "
                 "recasting once."),
    }

    cf_west.to_csv(OUT + "/flow_counterfactual.csv")
    with open(OUT + "/flow_did.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    print("DONOR POOL ({}): {}\n".format(len(donors), ", ".join(donors)))
    for name, blk in (("WESTBOUND (CHE -> US exports)", west),
                      ("EASTBOUND (CHE <- US imports)", east)):
        print(name)
        for w in ("surge", "return_leg"):
            a, p = blk["att"][w], blk["placebo_rank"][w]
            print("  {:<11} DiD {:>8.1f} t total ({:>6.1f} t/mo)   treated-only {:>8.1f} t"
                  .format(w, a["total_tonnes"], a["mean_tonnes_per_month"],
                          a["treated_only_excess_tonnes"]))
            print("  {:<11} placebo rank {}/{}, p = {:.3f} (min attainable {:.3f}); "
                  "median |placebo| {:.1f} t".format(
                      "", p["rank_of_treated"], p["n_placebos"] + 1, p["p_value"],
                      p["smallest_attainable_p"], p["placebo_abs_median_tonnes"]))
        pt = blk["pre_trend"]
        print("  pre-trend   mean |coef| over the {} months before the reference month "
              "= {:.1f} t/mo; surge effect is {:.0f}x that".format(
                  pt["months_tested"], pt["mean_abs_coef_tonnes"],
                  pt["ratio_surge_att_to_mean_abs_pre"]))
        print()

    i = results["interference"]
    print("INTERFERENCE CHECK")
    print("  total Swiss exports  {:.1f} -> {:.1f} t/month  (change {:+.1f})".format(
        i["total_swiss_exports_pre_mean_t_per_month"],
        i["total_swiss_exports_surge_mean_t_per_month"], i["total_change_t_per_month"]))
    print("  US corridor {:+.1f} t/mo, donor corridors {:+.1f} t/mo, offset {:.0%}".format(
        i["us_corridor_change_t_per_month"], i["donor_corridors_change_t_per_month"],
        i["share_of_us_rise_offset_by_donor_fall"]))
    print("  biggest donor moves:",
          {k: round(v, 1) for k, v in list(i["per_donor_change_t_per_month"].items())[:4]})

    print("\nEXCESS TONNAGE FOR THE LEDGER")
    print(json.dumps(results["excess_tonnage_for_ledger"], indent=2, default=float)[:900])


if __name__ == "__main__":
    main()
