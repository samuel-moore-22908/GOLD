"""
Re-time the New York leg onto the London auction, and check that it worked.

The premium as built compares a London price struck at 15:00 London with a New
York curve struck at 13:30 New York, so gold's return over the gap lands in it.
Because every contract settles at the same instant, that return is common to
the whole curve: it shifts the intercept and leaves the slope alone. One liquid
contract's return over the gap therefore corrects the entire cross-section.

    eps_t          = ln F_lead(settlement) - ln F_lead(London auction)
    premium_fixed  = premium - 100 * eps_t          (percentage points of spot)
    carry          unchanged, by construction

Run it with no minute data present and it prints the predictions the correction
should satisfy, so they are on the record before the data arrives.

    --selftest   run the whole pipeline on fabricated bars with a known shock,
                 which checks the code without buying anything

Reads   claude/premium-carry-series/premium_carry_daily.csv
        claude/timing-fix/timing_instants.csv
        data/databento/minute/*.csv                    (once bought)
        data/processed/comex_contract_daily.csv        (official settlements)
Writes  claude/timing-fix/premium_retimed_daily.csv
        claude/timing-fix/apply_timing_fix_output.txt

Run from the repo root:
    .venv/Scripts/python.exe claude/timing-fix/apply_timing_fix.py
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("claude/timing-fix")
MINUTE_GLOB = "data/databento/minute/*.csv"

# The auction is a process, not an instant: it opens at 15:00 London and settles
# over a few rounds. The price used is the mean close across this many one-minute
# bars from the open of the auction.
AUCTION_WINDOW_MIN = 5
# How far back to look for the last print at or before an instant, when the
# exact minute has none.
MAX_STALENESS_MIN = 10

# Stated before the data arrives. If the correction is doing what the model says,
# all five hold; if it is doing something else, at least one fails.
PREDICTIONS = [
    ("The premium stops predicting the next day's London return",
     "corr(premium, next-day London return) falls from 0.394 to |corr| < 0.10"),
    ("Daily noise falls",
     "sd of the daily premium falls from 0.499 pp by at least a fifth"),
    ("The calm/volatile noise gap closes",
     "sd on volatile days falls from 0.674 towards the 0.420 of calm days, "
     "the ratio moving from 1.60 to under 1.25"),
    ("The extreme days were the clock, not the market",
     "30 Jan 2026 moves from -5.55% to |premium| < 1.5%, and the 12 days "
     "beyond +/-2% fall to fewer than 5"),
    ("Monthly means barely move",
     "the Jan 2025 mean stays within 0.10 pp of 0.523, because a common shock "
     "averages out over a month -- if this one fails, the correction is wrong"),
]


def predictions_only() -> str:
    L = ["No minute data found under data/databento/minute/.",
         "",
         "Nothing to correct yet. pull_minute_bars.py --quote prices the pull;",
         "timing_instants.csv is the specification of exactly which minutes are",
         "needed. The predictions below are what the correction should deliver,",
         "recorded now so they cannot be adjusted after the fact.",
         ""]
    for i, (claim, test) in enumerate(PREDICTIONS, 1):
        L.append(f"{i}. {claim}")
        L.append(f"   test: {test}")
    L += ["",
          "Prediction 5 is the important one. The first four say the correction",
          "removes noise; the fifth says it removes noise rather than signal. A",
          "common timing shock has no reason to line up with calendar months, so",
          "monthly means should survive it almost untouched. If January 2025",
          "moves materially, the correction is picking up something other than",
          "the clock and should not be used."]
    return "\n".join(L)


def load_minutes() -> pd.DataFrame | None:
    files = sorted(glob.glob(MINUTE_GLOB))
    if not files:
        return None
    frames = []
    for f in files:
        df = pd.read_csv(f)
        ts = "ts_event" if "ts_event" in df.columns else df.columns[0]
        df["ts"] = pd.to_datetime(df[ts], utc=True)
        frames.append(df)
    m = pd.concat(frames, ignore_index=True)
    sym = "symbol" if "symbol" in m.columns else "requested_symbol"
    m["symbol"] = m[sym]
    return m[["ts", "symbol", "close"]].dropna().sort_values("ts")


def price_at(bars: pd.DataFrame, instant: pd.Timestamp, window: int) -> float:
    """Mean close over `window` minutes from `instant`; else the last print before it."""
    inside = bars[(bars.ts >= instant)
                  & (bars.ts < instant + pd.Timedelta(minutes=window))]
    if len(inside):
        return float(inside.close.mean())
    before = bars[(bars.ts <= instant)
                  & (bars.ts >= instant - pd.Timedelta(minutes=MAX_STALENESS_MIN))]
    return float(before.close.iloc[-1]) if len(before) else np.nan


def build(minutes: pd.DataFrame, window: int) -> pd.DataFrame:
    d = pd.read_csv("claude/premium-carry-series/premium_carry_daily.csv",
                    parse_dates=["date"])
    t = pd.read_csv(OUT / "timing_instants.csv",
                    parse_dates=["date", "auction_utc", "settle_utc"])
    c = pd.read_csv("data/processed/comex_contract_daily.csv", parse_dates=["date"])
    official = c[["date", "symbol", "settle"]].rename(columns={"settle": "lead_settle"})

    t = t.merge(official, left_on=["date", "lead_symbol"],
                right_on=["date", "symbol"], how="left")

    rows = []
    for _, r in t.iterrows():
        bars = minutes[minutes.symbol == r.lead_symbol]
        p_auction = price_at(bars, r.auction_utc, window)
        p_settle = price_at(bars, r.settle_utc, 1)
        rows.append({
            "date": r.date, "lead_symbol": r.lead_symbol,
            "p_auction": p_auction, "p_settle_minute": p_settle,
            "lead_settle": r.lead_settle,
            "eps_minute": np.log(p_settle / p_auction),
            "eps_settle": np.log(r.lead_settle / p_auction),
        })
    e = pd.DataFrame(rows)

    d = d.merge(e, on="date", how="left")
    d["retimed"] = d.eps_minute.notna()
    d["premium_pct_retimed"] = d.premium_pct - 100.0 * d.eps_minute
    d["premium_pct_retimed_settle"] = d.premium_pct - 100.0 * d.eps_settle
    d["premium_usd_retimed"] = d.lbma_pm_usd * np.expm1(d.premium_pct_retimed / 100.0)
    return d


def report(d: pd.DataFrame, window: int) -> str:
    L, P = [], lambda s="": L.append(s)
    ok = d[d.retimed]
    P("=" * 78)
    P(f"RE-TIMED PREMIUM  ({len(ok):,} of {len(d):,} days corrected, "
      f"auction window {window} min)")
    P("=" * 78)
    if ok.empty:
        return "\n".join(L + ["No day could be corrected; check the minute data."])

    s = ok[["premium_pct", "premium_pct_retimed", "lbma_pm_usd"]].copy()
    s["ret_next"] = 100.0 * np.log(s.lbma_pm_usd.shift(-1) / s.lbma_pm_usd)
    s = s.dropna()
    P(f"{'':<34}{'before':>10}{'after':>10}")
    P(f"{'standard deviation, pp of spot':<34}"
      f"{s.premium_pct.std():>10.3f}{s.premium_pct_retimed.std():>10.3f}")
    P(f"{'corr with next-day London return':<34}"
      f"{s.premium_pct.corr(s.ret_next):>10.3f}"
      f"{s.premium_pct_retimed.corr(s.ret_next):>10.3f}")
    q = s.ret_next.abs().quantile([0.25, 0.75])
    calm, vol = s[s.ret_next.abs() <= q.iloc[0]], s[s.ret_next.abs() >= q.iloc[1]]
    P(f"{'sd on calm days':<34}"
      f"{calm.premium_pct.std():>10.3f}{calm.premium_pct_retimed.std():>10.3f}")
    P(f"{'sd on volatile days':<34}"
      f"{vol.premium_pct.std():>10.3f}{vol.premium_pct_retimed.std():>10.3f}")
    P(f"{'days beyond +/-2 pp':<34}"
      f"{(s.premium_pct.abs()>2).sum():>10d}{(s.premium_pct_retimed.abs()>2).sum():>10d}")
    P("")
    P("Two ways of measuring the shock, as a check on each other:")
    P(f"   minute-to-minute vs settlement-based eps: "
      f"corr {ok.eps_minute.corr(ok.eps_settle):.4f}, "
      f"mean difference {1e4*(ok.eps_minute-ok.eps_settle).mean():.2f} bp")
    P("")
    P("Monthly means, before and after:")
    mm = ok.set_index("date")[["premium_pct", "premium_pct_retimed"]].resample("MS").mean()
    ep = mm.loc["2024-10":"2025-06"]
    P(f"   {'month':<10}{'before':>10}{'after':>10}{'change':>10}")
    for idx, r in ep.iterrows():
        P(f"   {idx:%Y-%m}   {r.premium_pct:>9.3f}{r.premium_pct_retimed:>10.3f}"
          f"{r.premium_pct_retimed - r.premium_pct:>10.3f}")
    P("")
    P("Carry is untouched: the correction is a common level shift, so it cannot")
    P("move the slope of the curve. Nothing in the carry series changes.")
    P("")
    P("Against the predictions recorded before the pull:")
    # A check the sample cannot speak to is reported as such. Scoring it FAIL
    # would read as evidence against the correction when it is only evidence
    # that the relevant months have not been bought yet.
    episode_present = "2025-01-01" in mm.index.strftime("%Y-%m-%d").tolist()
    had_extremes = (s.premium_pct.abs() > 2).sum() > 0
    checks = [
        (abs(s.premium_pct_retimed.corr(s.ret_next)) < 0.10, True,
         "1 next-day return"),
        (s.premium_pct_retimed.std() < 0.8 * s.premium_pct.std(), True,
         "2 noise falls"),
        (vol.premium_pct_retimed.std() / calm.premium_pct_retimed.std() < 1.25,
         True, "3 calm/volatile gap closes"),
        ((s.premium_pct_retimed.abs() > 2).sum() < 5, had_extremes,
         "4 extremes were the clock"),
        (episode_present
         and abs(mm.loc["2025-01", "premium_pct_retimed"] - 0.523) < 0.10,
         episode_present, "5 monthly means survive"),
    ]
    for passed, testable, name in checks:
        verdict = ("PASS" if passed else "FAIL") if testable else " -- "
        P(f"   [{verdict}] {name}"
          + ("" if testable else "   (no days in the sample to test it on)"))
    if len(ok) < len(d):
        P("")
        P(f"NOTE: only {len(ok):,} of {len(d):,} days carry minute data, so every")
        P("number above describes that subsample, not the full series.")
    return "\n".join(L)


def selftest() -> None:
    """Fabricate bars with a known shock and check the pipeline recovers it."""
    t = pd.read_csv(OUT / "timing_instants.csv",
                    parse_dates=["date", "auction_utc", "settle_utc"]).head(40)
    rng = np.random.default_rng(0)
    shocks = rng.normal(0, 0.004, len(t))
    rows = []
    for (_, r), eps in zip(t.iterrows(), shocks):
        base = 1500.0
        for k in range(AUCTION_WINDOW_MIN):
            rows.append({"ts": r.auction_utc + pd.Timedelta(minutes=k),
                         "symbol": r.lead_symbol, "close": base})
        rows.append({"ts": r.settle_utc, "symbol": r.lead_symbol,
                     "close": base * np.exp(eps)})
    minutes = pd.DataFrame(rows)
    built = build(minutes, AUCTION_WINDOW_MIN).dropna(subset=["eps_minute"])
    err = np.abs(built.eps_minute.to_numpy() - shocks[: len(built)]).max()
    moved = (built.premium_pct - built.premium_pct_retimed) / 100.0
    print(f"selftest: {len(built)} days, largest error in recovered shock "
          f"{err:.2e}")
    print(f"selftest: correction applied equals the shock to "
          f"{np.abs(moved.to_numpy() - built.eps_minute.to_numpy()).max():.2e}")
    assert err < 1e-12, "the shock is not being recovered"
    print("selftest: PASS")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--window", type=int, default=AUCTION_WINDOW_MIN)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        selftest()
        return

    minutes = load_minutes()
    if minutes is None:
        text = predictions_only()
    else:
        d = build(minutes, args.window)
        d.to_csv(OUT / "premium_retimed_daily.csv", index=False)
        text = report(d, args.window)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "apply_timing_fix_output.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
