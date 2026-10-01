"""
Step 3. Causal event study on the price of location.

The outcome is the excess basis: the COMEX-minus-London spread in dollars per
ounce, net of the carry that the delivery calendar mechanically implies. It is
what an arbitrageur is paid for having metal in New York rather than in London,
and it is the object the tariff threat should move if the tariff threat is what
drove the relocation.

Identification is narrative. Each event below is a gold-specific, document-dated
change in whether US import duty could attach to a COMEX-deliverable bar, and
each carries an unambiguous predicted sign fixed before looking at the series.
Inference is by randomization: the null is the empirical distribution of the
same statistic computed at every non-event date in 2015-2026. Nothing is assumed
about the shape of that distribution, which matters because the basis is
fat-tailed.

ANCHORING. Each event is anchored at the last COMEX settlement that could not
yet contain the news, and the response is measured forward from there. COMEX
gold settles at 13:30 ET. So:

  5 Nov 2024   election returns arrived overnight        -> anchor 5 Nov
  2 Apr 2025   EO 14257 announced ~16:00 ET, after settle -> anchor 2 Apr
  8 Aug 2025   CBP N351466 reported during Friday's session, futures hit a
               record intraday                            -> anchor 7 Aug
  11 Aug 2025  presidential statement, Monday morning     -> anchor 8 Aug
  5 Sep 2025   EO 14346 signed Friday, effective 8 Sep    -> anchor 5 Sep

MEASUREMENT NOISE. The COMEX leg settles at 13:30 ET and the London leg is the
15:00 London PM auction, about three and a half hours earlier. The excess basis
therefore carries a non-synchronous-pricing error whose daily standard deviation
(~$16/oz) is close to gold's own daily volatility. That error is in the outcome,
not the treatment, so it widens the randomization null and makes these tests
conservative rather than optimistic. The headline specification averages three
observations either side of the anchor to damp it.

Two placebos run alongside. The LBMA PM price itself is a placebo outcome: if
these were general gold-price news rather than location news, spot should move
by as many of its own standard deviations as the basis moves by its own. And
every non-event date in the sample is a placebo date, which is what the
randomization p-values are built from.

Input:  data/processed/efp_dislocation_v2.csv
Output: output/event_study.json, output/event_study_windows.csv
"""
import json

import numpy as np
import pandas as pd

OUT = "claude/tariff-relocation-cost/output"

MIN_DTFN = 20      # drop near-expiry days: futures converge to spot mechanically
MAX_GAP_DAYS = 7   # drop windows straddling the stretch between active contracts
BUFFER_DAYS = 10   # observations around each event excluded from the null
WINDOW = 3         # observations averaged either side of the anchor

EVENTS = [
    {"key": "election_2024", "anchor": "2024-11-05", "expected": +1,
     "label": "US presidential election",
     "document": "(not a document; returns arrived after the 5 Nov settle)"},
    {"key": "eo14257_annex2", "anchor": "2025-04-02", "expected": -1,
     "label": "EO 14257 Annex II published; unwrought gold 7108.12.10 excluded",
     "document": "EO 14257, signed 2 Apr 2025, FR 2025-06063"},
    {"key": "cbp_n351466_reported", "anchor": "2025-08-07", "expected": +1,
     "label": "CBP N351466 reaches the market; cast bars are 7108.13.55 and dutiable",
     "document": "CBP CROSS N351466, dated 31 Jul 2025, reported 8 Aug 2025"},
    {"key": "gold_will_not_be_tariffed", "anchor": "2025-08-08", "expected": -1,
     "label": "Administration states gold will not be tariffed",
     "document": "Presidential statement, 11 Aug 2025 (no Federal Register instrument)"},
    {"key": "eo14346_signed", "anchor": "2025-09-05", "expected": -1,
     "label": "EO 14346 replaces Annex II; 7108.13.55 excluded, effective 8 Sep",
     "document": "EO 14346, signed 5 Sep 2025, FR 2025-17507"},
]

OUTCOMES = {
    "excess_basis_usd": "Excess basis, USD/oz (COMEX settle - LBMA PM - implied carry)",
    "spot_log_pts": "LBMA PM gold price, 100 x log (placebo outcome)",
}


def load_basis():
    d = (pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])
         .sort_values("date").reset_index(drop=True))
    d = d[d.days_to_first_notice >= MIN_DTFN].reset_index(drop=True)
    d["gap_days"] = d["date"].diff().dt.days
    # Spot in log points so moves are comparable across an era in which gold
    # went from about $1,200 to about $4,600.
    d["spot_log_pts"] = 100.0 * np.log(d["lbma_pm_usd"])
    return d


def clean_window(d, i, w):
    """True if observations i-w+1 .. i+w are contiguous enough to compare."""
    if i - w + 1 < 0 or i + w >= len(d):
        return False
    gaps = d["gap_days"].iloc[i - w + 2: i + w + 1]
    return bool((gaps <= MAX_GAP_DAYS).all())


def shift_stat(d, col, i, w):
    """Mean over the w observations after i, minus the mean over the w
    observations ending at i."""
    post = d[col].iloc[i + 1: i + 1 + w].mean()
    pre = d[col].iloc[i - w + 1: i + 1].mean()
    return post - pre


def build_null(d, col, w, excluded):
    vals = []
    for i in range(len(d)):
        if excluded.iloc[i] or not clean_window(d, i, w):
            continue
        vals.append(shift_stat(d, col, i, w))
    return np.array(vals, dtype=float)


def ri(null, value, expected):
    signed = expected * value
    return {
        "change": float(value),
        "n_null": int(null.size),
        "null_sd": float(null.std(ddof=1)),
        "z_vs_null": float(value / null.std(ddof=1)),
        "p_one_sided_ri": float((expected * null >= signed).mean()),
        "p_two_sided_ri": float((np.abs(null) >= abs(value)).mean()),
    }


def main():
    d = load_basis()

    idx = {}
    for ev in EVENTS:
        hits = d.index[d["date"] <= pd.Timestamp(ev["anchor"])]
        idx[ev["key"]] = int(hits[-1])
        if str(d.date.iloc[idx[ev["key"]]].date()) != ev["anchor"]:
            print("NOTE: {} anchor {} fell on a non-trading day; using {}".format(
                ev["key"], ev["anchor"], d.date.iloc[idx[ev["key"]]].date()))

    excluded = pd.Series(False, index=d.index)
    for i in idx.values():
        excluded.iloc[max(0, i - BUFFER_DAYS): i + BUFFER_DAYS + 1] = True

    results = {"settings": {
        "min_days_to_first_notice": MIN_DTFN,
        "max_gap_days_within_window": MAX_GAP_DAYS,
        "buffer_days_excluded_from_null": BUFFER_DAYS,
        "window_observations_each_side": WINDOW,
        "sample": [str(d.date.min().date()), str(d.date.max().date())],
        "n_obs": int(len(d)),
        "anchoring": ("each event is anchored at the last COMEX settlement that "
                      "could not contain the news; the response is measured forward"),
    }, "outcomes": {}}
    rows = []

    for col, desc in OUTCOMES.items():
        per = {"description": desc, "events": {}}
        nulls = {w: build_null(d, col, w, excluded) for w in (1, WINDOW)}
        for ev in EVENTS:
            i = idx[ev["key"]]
            rec = {"label": ev["label"], "document": ev["document"],
                   "anchor_date": str(d.date.iloc[i].date()),
                   "reaction_date": str(d.date.iloc[i + 1].date()),
                   "expected_sign": ev["expected"], "specs": {}}
            for w in (1, WINDOW):
                if not clean_window(d, i, w):
                    rec["specs"]["w{}".format(w)] = {"change": None,
                                                     "note": "window straddles a roll gap"}
                    continue
                stat = shift_stat(d, col, i, w)
                rec["specs"]["w{}".format(w)] = ri(nulls[w], stat, ev["expected"])
                rows.append({"outcome": col, "event": ev["key"], "window_obs": w,
                             "anchor_date": d.date.iloc[i].date(), "change": stat,
                             **{k: v for k, v in ri(nulls[w], stat, ev["expected"]).items()
                                if k != "change"}})
            per["events"][ev["key"]] = rec
        results["outcomes"][col] = per

    # Joint test on non-overlapping one-day moves, signs fixed in advance.
    null1 = build_null(d, "excess_basis_usd", 1, excluded)
    signs = np.array([ev["expected"] for ev in EVENTS], dtype=float)
    actual = np.array([shift_stat(d, "excess_basis_usd", idx[ev["key"]], 1) for ev in EVENTS])
    stat = float((signs * actual).sum())
    rng = np.random.default_rng(20260826)
    placebo = (rng.choice(null1, size=(200_000, len(EVENTS)), replace=True) * signs).sum(axis=1)
    results["joint_test"] = {
        "spec": "sum of sign-adjusted one-day moves in the excess basis",
        "statistic_usd_per_oz": stat,
        "per_event_usd_per_oz": {ev["key"]: float(a) for ev, a in zip(EVENTS, actual)},
        "p_value_ri": float((placebo >= stat).mean()),
        "draws": 200_000,
        "note": ("One-day windows are used here so the two August events, which "
                 "are two business days apart, cannot double-count the same move."),
    }

    # The August pair on its own: tariff risk switched on and off in two sessions.
    i_on, i_off = idx["cbp_n351466_reported"], idx["gold_will_not_be_tariffed"]
    results["august_2025_switch"] = {
        "on_news_date": str(d.date.iloc[i_on + 1].date()),
        "excess_basis_before_usd": float(d.excess_basis_usd.iloc[i_on]),
        "excess_basis_after_usd": float(d.excess_basis_usd.iloc[i_on + 1]),
        "move_on_usd": float(d.excess_basis_usd.iloc[i_on + 1] - d.excess_basis_usd.iloc[i_on]),
        "off_news_date": str(d.date.iloc[i_off + 1].date()),
        "move_off_usd": float(d.excess_basis_usd.iloc[i_off + 1] - d.excess_basis_usd.iloc[i_off]),
        "raw_basis_peak_usd": float(d.basis_usd.iloc[i_on + 1]),
        "spot_move_on_pct": float(np.exp((d.spot_log_pts.iloc[i_on + 1]
                                          - d.spot_log_pts.iloc[i_on]) / 100) * 100 - 100),
        "spot_move_off_pct": float(np.exp((d.spot_log_pts.iloc[i_off + 1]
                                           - d.spot_log_pts.iloc[i_off]) / 100) * 100 - 100),
        "round_trip_days": 1,
    }

    # Regime means: two tariff-risk-on windows against calm and post-resolution.
    regimes = {
        "risk_on_1_election_to_annex2": ("2024-11-06", "2025-04-02"),
        "risk_on_2_cbp_to_eo14346": ("2025-08-08", "2025-09-08"),
        "calm_2015_2019": ("2015-01-02", "2019-12-31"),
        "post_eo14346": ("2025-09-09", "2026-08-20"),
    }
    reg = {}
    for name, (a, b) in regimes.items():
        w = d[(d.date >= a) & (d.date <= b)]
        reg[name] = {
            "start": a, "end": b, "n_days": int(len(w)),
            "mean_excess_basis_usd": float(w.excess_basis_usd.mean()),
            "median_excess_basis_usd": float(w.excess_basis_usd.median()),
            "max_excess_basis_usd": float(w.excess_basis_usd.max()),
            "sd_excess_basis_usd": float(w.excess_basis_usd.std(ddof=1)),
            "mean_dislocation_annualized": float(w.dislocation.mean()),
            "share_days_excess_above_10usd": float((w.excess_basis_usd > 10).mean()),
        }
    results["regimes"] = reg

    with open(OUT + "/event_study.json", "w") as f:
        json.dump(results, f, indent=2)
    pd.DataFrame(rows).to_csv(OUT + "/event_study_windows.csv", index=False)

    def stars(p):
        return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

    print("\nEVENT STUDY -- excess basis (USD/oz). Signs predicted in advance.\n")
    print("{:<26} {:>10} {:>18} {:>18}".format("event", "anchor", "1-day", "3-day mean shift"))
    print("-" * 76)
    eb = results["outcomes"]["excess_basis_usd"]["events"]
    sp = results["outcomes"]["spot_log_pts"]["events"]
    for ev in EVENTS:
        r = eb[ev["key"]]
        cells = []
        for w in (1, WINDOW):
            s = r["specs"]["w{}".format(w)]
            cells.append("  --" if s.get("change") is None else
                         "{:>8.1f}{:<3} z={:>4.1f}".format(s["change"], stars(s["p_one_sided_ri"]),
                                                           s["z_vs_null"]))
        print("{:<26} {:>10} {:>18} {:>18}".format(ev["key"][:26], r["anchor_date"], *cells))
    print("\nplacebo outcome -- spot price, same windows (z against its own null):")
    for ev in EVENTS:
        s = sp[ev["key"]]["specs"]["w{}".format(WINDOW)]
        if s.get("change") is not None:
            print("  {:<26} {:>7.2f} log pts   z={:>5.2f}   p2={:.3f}".format(
                ev["key"][:26], s["change"], s["z_vs_null"], s["p_two_sided_ri"]))
    print("\none-sided randomization p-values: * .10  ** .05  *** .01"
          "  (null n = {})".format(len(null1)))
    print("\njoint test  stat = ${:.1f}/oz   p = {:.4f}".format(
        results["joint_test"]["statistic_usd_per_oz"], results["joint_test"]["p_value_ri"]))
    print("\nAugust 2025 switch:")
    print(json.dumps(results["august_2025_switch"], indent=2))
    print("\nregimes:")
    print(pd.DataFrame(reg).T.round(3).to_string())


if __name__ == "__main__":
    main()
