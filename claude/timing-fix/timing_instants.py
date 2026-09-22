"""
The two instants, for every trading day in the sample.

The premium compares a London price struck at 15:00 London with a New York
price struck at 13:30 New York. To re-time the New York leg onto the London
auction, you first have to know exactly when each of those moments is, in a
single clock, on each date -- which is not a fixed offset, because the UK and
the US change their clocks on different dates.

This writes the purchase specification for the minute data: the precise UTC
windows to buy, and the contract to buy them for, day by day.

Reads   claude/premium-carry-series/premium_carry_daily.csv   (the trading days)
        data/processed/comex_contract_daily.csv               (the lead contract)
Writes  claude/timing-fix/timing_instants.csv

Run from the repo root:
    .venv/Scripts/python.exe claude/timing-fix/timing_instants.py
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

OUT = Path("claude/timing-fix")
LONDON, NEW_YORK = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")

# The LBMA Gold Price PM auction starts at 15:00 London and runs in rounds for
# a few minutes. The settlement price for COMEX gold is calculated over the
# 13:29:30-13:30:00 New York window.
AUCTION_HOUR, AUCTION_MINUTE = 15, 0
SETTLE_HOUR, SETTLE_MINUTE = 13, 30
# Minutes of slack either side, so a minute with no print is not a missing day.
PAD_BEFORE, PAD_AFTER = 5, 5
# Early closes need a wider look-back, because the session has already ended by
# the usual settlement minute and the last print may be an hour earlier.
EARLY_CLOSE_LOOKBACK = 120


def early_close_dates(years: range) -> set[pd.Timestamp]:
    """US holiday sessions when COMEX closes early, by rule rather than by list.

    The day after Thanksgiving, Christmas Eve and the day before Independence
    Day all trade a shortened session, and the settlement moves with the close.
    Generated rather than hard-coded so the set extends with the sample.
    """
    out: set[pd.Timestamp] = set()
    for y in years:
        thanksgiving = pd.date_range(f"{y}-11-01", f"{y}-11-30", freq="W-THU")[3]
        out.add(thanksgiving + pd.Timedelta(days=1))
        for d in (pd.Timestamp(f"{y}-12-24"), pd.Timestamp(f"{y}-07-03")):
            if d.weekday() < 5:
                out.add(d)
    return out


def main() -> None:
    days = pd.read_csv("claude/premium-carry-series/premium_carry_daily.csv",
                       parse_dates=["date"], usecols=["date"])
    contracts = pd.read_csv("data/processed/comex_contract_daily.csv",
                            parse_dates=["date"])
    contracts = contracts[(contracts.open_interest.fillna(0) >= 1000)
                          & contracts.settle.notna()]

    # The contract to buy minute bars for: the one the market is actually using
    # that day. Its runner-up is carried too, as the fallback for a day when the
    # lead contract has no print in the window.
    ranked = contracts.sort_values(["date", "open_interest"], ascending=[True, False])
    lead = ranked.groupby("date").head(2).copy()
    lead["rank"] = lead.groupby("date").cumcount()
    wide = lead.pivot(index="date", columns="rank", values="symbol")
    wide.columns = ["lead_symbol", "backup_symbol"][: wide.shape[1]]

    d = days.merge(wide, left_on="date", right_index=True, how="left")
    early = early_close_dates(range(d.date.dt.year.min(), d.date.dt.year.max() + 1))

    rows = []
    for _, r in d.iterrows():
        day = r.date.date()
        auction = (pd.Timestamp(day, tz=LONDON)
                   + pd.Timedelta(hours=AUCTION_HOUR, minutes=AUCTION_MINUTE))
        settle = (pd.Timestamp(day, tz=NEW_YORK)
                  + pd.Timedelta(hours=SETTLE_HOUR, minutes=SETTLE_MINUTE))
        is_early = pd.Timestamp(day) in early
        rows.append({
            "date": r.date,
            "lead_symbol": r.get("lead_symbol"),
            "backup_symbol": r.get("backup_symbol"),
            "auction_utc": auction.tz_convert("UTC"),
            "settle_utc": settle.tz_convert("UTC"),
            "gap_hours": (settle - auction).total_seconds() / 3600.0,
            # The window to buy: from just before the auction to just after the
            # settlement, one contiguous block per day.
            "window_start_utc": (auction - pd.Timedelta(minutes=PAD_BEFORE)).tz_convert("UTC"),
            "window_end_utc": (settle + pd.Timedelta(minutes=PAD_AFTER)).tz_convert("UTC"),
            "lookback_minutes": EARLY_CLOSE_LOOKBACK if is_early else PAD_BEFORE,
            "possible_early_close": is_early,
        })

    t = pd.DataFrame(rows)
    t["window_minutes"] = ((t.window_end_utc - t.window_start_utc)
                           .dt.total_seconds() / 60).astype(int)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "timing_instants.csv", index=False)

    print(f"{len(t):,} trading days, {t.date.min():%Y-%m-%d} to {t.date.max():%Y-%m-%d}")
    print()
    print("Gap between the London auction and the COMEX settlement:")
    for gap, n in t.gap_hours.value_counts().sort_index(ascending=False).items():
        print(f"   {gap:.1f} hours on {n:,} days ({100*n/len(t):.1f}%)")
    print()
    print("The 2.5-hour days are the weeks when the UK and US clocks are out of")
    print("step -- the US springs forward first in March, the UK falls back first")
    print("in October. A fixed offset would be wrong on all of them:")
    odd = t[t.gap_hours != 3.5]
    per_year = odd.groupby(odd.date.dt.year).size()
    print("   " + ", ".join(f"{y}: {n}" for y, n in per_year.items()))
    print()
    print(f"Possible early closes flagged: {t.possible_early_close.sum()} days")
    print(f"Minutes to buy: {t.window_minutes.sum():,} contract-minutes in total, "
          f"median {t.window_minutes.median():.0f} a day")
    print(f"Distinct lead contracts across the sample: {t.lead_symbol.nunique()}")
    print()
    print(f"wrote {OUT/'timing_instants.csv'}")


if __name__ == "__main__":
    main()
