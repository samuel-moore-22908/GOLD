# The timing fix

The premium compares a London price struck at 15:00 London with a New York
curve struck at 13:30 New York. Gold's return over the gap lands in the
premium and is worth about 0.4 percentage points of spot a day — the largest
single source of noise in the series, and the reason daily readings cannot
currently carry an argument.

This folder does the fix: it works out exactly which minutes have to be bought,
prices them before anything is spent, applies the correction, and checks it
against predictions written down in advance.

```
.venv/Scripts/python.exe claude/timing-fix/timing_instants.py            # the spec
.venv/Scripts/python.exe claude/timing-fix/pull_minute_bars.py --quote   # the price
.venv/Scripts/python.exe claude/timing-fix/pull_minute_bars.py --pull --confirm
.venv/Scripts/python.exe claude/timing-fix/apply_timing_fix.py           # the fix
```

**Status.** The specification and both scripts are built and the correction is
tested end to end on fabricated bars (`apply_timing_fix.py --selftest`, which
recovers a known shock to 1e-16). Nothing has been bought: no Databento key is
present on this machine, and costing calls need one even though they are free.
Running `apply_timing_fix.py` today prints the predictions rather than results.

---

## Why one contract is enough

Every contract on the curve settles at the same instant, so the return over the
gap multiplies all of that day's futures prices equally. In logs it is an
additive shift common to the cross-section: it moves the intercept and leaves
the slope untouched. That is the property the whole fix rests on, and it means

> one liquid contract's return between the two instants corrects the entire
> curve.

So the purchase is a few hundred minutes a day for one contract, not the whole
tape. And the carry series does not need correcting at all — it is the slope.

```
eps_t         = ln F_lead(settlement) - ln F_lead(London auction)
premium_fixed = premium - 100 * eps_t        (percentage points of spot)
```

The shock is measured two ways, as a check on each other: minute-to-minute
(both ends from traded bars) and settlement-based (the official settlement
against the auction-minute price). The first is cleaner, because it does not
mix a volume-weighted settlement procedure with a traded price; the second
needs one fewer minute. They should agree to a basis point or two.

---

## The clock is not a constant offset

`timing_instants.py` computes both instants for all 2,857 trading days from
`Europe/London` and `America/New_York` rather than assuming a fixed gap, and
that matters more than expected:

| Gap between the auction and the settlement | Days | Share |
|---|---:|---:|
| 3.5 hours | 2,654 | 92.9% |
| 2.5 hours | 203 | 7.1% |

The 2.5-hour days are the weeks when the two countries' clocks are out of step
— the US springs forward before the UK in March, the UK falls back before the
US in late October. They cluster 14–20 days a year, every year in the sample.
**A hard-coded 3.5-hour offset would silently mis-time 7% of the sample**,
including March 2020 and March 2025, both of which sit inside episodes the
paper cares about.

The script also flags 17 probable early-close sessions — the day after
Thanksgiving, Christmas Eve and the day before Independence Day — where the
settlement moves with the shortened session. Those days get a two-hour
look-back instead of five minutes, so the last print before the close is found
rather than missed.

`timing_instants.csv` is the output and the purchase specification: for each
date, the lead contract by open interest, a backup contract, both instants in
UTC, and the window to buy. In total **616,360 contract-minutes**, a median of
220 a day, across 50 distinct contracts.

---

## What to buy, and pricing it first

`pull_minute_bars.py --quote` prices three ways of getting the same correction
through `metadata.get_cost`, which is free:

1. **Everything** — `GC.FUT` parent symbology, `ohlcv-1m`, the whole sample.
   One job, the same shape as the two pulls already in `data/databento/`, and
   far more data than the correction needs.
2. **Lead contracts only**, whole days — 50 symbols over the sample.
3. **Lead contracts, only the minutes needed** — the windows in
   `timing_instants.csv`. Least data, most requests; the quote extrapolates
   from twelve sampled days and flags that per-request minimums, if any, set a
   floor.

`--pull` executes the third and refuses to run without `--confirm`. `--batch`
prints the web-UI parameters for the first, matching the existing workflow of
submitting a job and downloading the zip by hand.

The client is pinned in `requirements.txt` (`databento==0.86.0`); the API
signatures used here were checked against that installed version.

---

## Predictions, recorded before the data arrives

`apply_timing_fix.py` prints these today and tests them automatically once the
minute data is in place.

| # | Claim | Test |
|---|---|---|
| 1 | The premium stops predicting the next day's London return | corr falls from 0.394 to under 0.10 in absolute value |
| 2 | Daily noise falls | sd falls from 0.499 pp by at least a fifth |
| 3 | The calm/volatile noise gap closes | the sd ratio falls from 1.60 (0.674 vs 0.420) to under 1.25 |
| 4 | The extreme days were the clock | 30 Jan 2026 moves from −5.55% to inside ±1.5%, and the 12 days beyond ±2% fall below 5 |
| 5 | Monthly means barely move | the Jan 2025 mean stays within 0.10 pp of 0.523 |

**Prediction 5 is the one that can falsify the exercise.** The first four say
the correction removes noise. The fifth says it removes noise rather than
signal: a common intraday shock has no reason to line up with calendar months,
so monthly means should survive it almost untouched. If January 2025 moves
materially, the correction is picking up something other than the clock and
should not be used.

---

## Choices that are parameters, not facts

- **The auction window.** The LBMA auction opens at 15:00 London and settles
  over several rounds, so the New York price is taken as the mean close over
  the first five one-minute bars. `--window 1` reads it at the opening minute
  instead; the difference between the two is a sensitivity check worth
  reporting once the data exists.
- **Staleness.** If the exact minutes have no print, the last trade within ten
  minutes is used, and a day with nothing usable is flagged `retimed = False`
  rather than silently left uncorrected. Corrected and uncorrected days must
  never be mixed without the flag.
- **Which contract.** The lead contract is the one with the most open interest
  that day, which is the same rule the curve fit uses to decide what is liquid.
  The runner-up is carried in the specification as a fallback.

## What this does not fix

The correction removes the gap between the two legs. It does not make the two
prices the same kind of object: the London benchmark is an auction clearing
price for unallocated metal and the New York figure is a settlement for
warranted metal. The variant that removes that difference as well is the
two-curve measurement — ICE Gold Daily Futures settle 15:00–15:05 London, so
both legs would be exchange-cleared futures struck in the same window. See
`claude/spread-data-list/SPREAD_DATA_LIST.md`.
