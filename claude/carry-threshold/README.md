# When the spread clears carry, and whether metal moves

The cash-and-carry test, run properly. Buy London metal, finance and store it
to the delivery date, deliver against a COMEX contract: it pays only if the
spread exceeds carry, and metal only moves if what is left also covers the cost
of shipping it.

```
python claude/carry-threshold/build_carry_threshold.py   # the test
python claude/carry-threshold/estimate_threshold.py      # where kappa comes from
```

The carry rate is not assumed. It is the slope of the daily log futures curve —
the market's own price of holding gold in New York — read at the active
contract's horizon, so the carry cost spans exactly the interval the quoted
spread spans.

```
carry cost   K(tau) = S * (exp(carry_rate * tau/365) - 1)
excess       X      = b(tau) - K(tau)
metal moves  when    X > kappa
```

## Carry is most of the quoted spread

| | |
|---|---|
| horizon | median 46 days |
| carry cost | mean **$8.75**/oz, max $65.48 |
| quoted spread | mean $8.50/oz |

Panel A shows why the raw number is useless as a signal: the carry line is
itself a sawtooth resetting every delivery cycle, with the quoted spread
oscillating around it. Almost everything in `F − S` is the calendar.

## The all-in hurdle: carry plus shipping

Carry is not the whole cost of the trade. The metal also has to be flown and
recast, so the spread has to clear

```
carry(tau)  +  kappa        the westward trigger
```

**Shipping is a level, not a rate.** It is paid once, so it is added once
rather than entering the slope. A cost inside the slope would make the hurdle
grow with the horizon, and freight does not care whether the contract expires
in ten days or a hundred. That is why the test compares the *excess* — the
spread already net of carry — against a constant, rather than adding anything
to the fitted carry rate.

What the decomposition has done over eleven years:

| year | gold | carry | ship | hurdle | shipping share |
|---|---:|---:|---:|---:|---:|
| 2015 | $1,160 | $0.71 | $0.78 | $1.49 | **57.3%** |
| 2019 | $1,392 | $4.40 | $0.78 | $5.18 | 19.3% |
| 2022 | $1,800 | $9.01 | $0.78 | $9.79 | 13.7% |
| 2025 | $3,434 | $21.28 | $0.78 | $22.06 | 5.1% |
| 2026 | $4,571 | $24.96 | $0.78 | $25.74 | **4.8%** |

### The composite, and where its error bar comes from

```
hurdle = S·(exp(b·tau) - 1) + kappa
se     = sqrt( se(carry)^2 + se(kappa)^2 )
```

The two pieces are estimated independently — carry from the day's curve fit,
shipping from a bootstrap over months of customs data — so their variances add.
`se(kappa)` is $0.88, backed out of the block-bootstrap interval; `se(carry)`
has a median of $0.08.

| year | hurdle | 90% band | carry, % of level | carry, % of variance |
|---|---:|---|---:|---:|
| 2015 | $1.49 | [0.04, 2.93] | 42.7% | **0.5%** |
| 2020 | $5.43 | [3.83, 7.04] | 77.7% | 14.7% |
| 2025 | $22.06 | [20.42, 23.71] | 94.9% | 17.7% |
| 2026 | $25.74 | [24.17, 27.30] | 95.2% | **12.8%** |

**That asymmetry is the useful part.** By 2026 the hurdle is 95% carry while
its error bar is 87% shipping: the large component is the precisely measured
one and the small component is the guess. Sharpening the hurdle therefore means
getting a freight quote, not a better curve fit.

### At a fixed horizon, so it is comparable with itself

The hurdle at the active contract's `tau` is the right thing to set against
that contract's quoted spread, but `tau` cycles with the delivery calendar, so
that series cannot be compared with itself over time. At a constant ninety
days:

| year | $/oz | % of spot | $ per tonne |
|---|---:|---:|---:|
| 2015 | $2.08 | 0.180% | 67,002 |
| 2020 | $8.59 | 0.481% | 276,158 |
| 2025 | $40.25 | 1.183% | 1,293,946 |
| 2026 | $50.28 | 1.102% | 1,616,588 |

Relocating a tonne cost $67,000 in 2015 and $1.6 million in 2026, and as a
share of the metal's value it rose from 0.18% to 1.10% — a sixfold increase.

That cuts against the intuition that a rising gold price makes a fixed physical
cost matter less. It does — but the physical cost is the small part. The hurdle
is mostly carry, carry is a rate, and rates went from zero to five per cent.
**The barrier to relocation grew because money got expensive, not because
freight did.**

Shipping was the majority of the barrier in 2015 and is a twentieth of it now:
carry went from 43% of the hurdle to 95%. Rates and the gold price both rose
while freight stayed flat in dollars, so **what stops metal moving is now
almost entirely a financing cost** — one that moves with monetary policy rather
than with logistics. A paper about relocation flows should say that, because it
means the barrier to relocation is set by the Federal Reserve and the gold
price, not by Brink's.

## The decomposition checks out — and the check is the finding

| Excess compared with | corr | sd of difference |
|---|---:|---:|
| the premium **before** re-timing (same settlement) | **0.998** | $0.78 |
| the premium **re-timed** to the London auction | 0.276 | $12.14 |

The first line is the identity: subtracting carry from one contract's spread
reproduces the curve's intercept to 78 cents an ounce.

The second is not a failure of it. The quoted spread is struck at the New York
settlement and London spot three and a half hours earlier, so the excess
carries the whole timing error. A premium with standard deviation $3.95 against
an error of $12.14 implies a correlation of 0.309, and 0.276 is observed.
Averaging recovers it — 0.737 monthly, 0.822 quarterly.

**So the textbook test cannot be run on the quoted spread at daily frequency.**
The measurement error is $12 an ounce against a shipping cost around $1.

## Where kappa comes from

Nobody publishes the cost of flying an ounce of gold across the Atlantic and
having it recast on the way. It is **estimated from the flows**: metal does not
move until the premium covers that cost, so the premium–tonnage relationship
kinks, and the kink is the cost. `estimate_threshold.py` finds it by profile
least squares — fit at every candidate threshold on a grid, keep the smallest
sum of squares — with iid and moving-block bootstrap intervals.

The specification the model section calls for hinges **daily** and then
averages to the month, because `max(0, ·)` is convex and averaging first hides
a week at $5 inside a month averaging zero:

```
tonnes = a + beta * mean_over_days[ max(0, premium - kappa) ]
```

| | westward | eastward |
|---|---:|---:|
| threshold | **+$0.78**/oz | **−$0.95**/oz |
| 90% CI (block) | [−$0.46, +$2.43] | [−$1.78, +$0.80] |
| slope beyond it | +8.92 t per $/oz | −7.37 t per $/oz |
| R² | 0.488 | 0.254 (straight line 0.063) |

Sanity: $0.78 an ounce is about $25,000 a tonne, and the one public component —
the COMEX delivery-out charge of $0.35 an ounce — is nearly half of it.

**This supersedes the $2.99–$3.77 used in earlier work**, and the correction
has a mechanism rather than being a revision of taste. That estimate was fitted
to the premium *before* re-timing. Noise in a regressor both attenuates the
slope and smears the kink, because the threshold is a feature of the x axis and
noise moves observations across it; halving the noise moved the estimate down
by a factor of four. Note also that the earlier "$3.00–$3.77 band" was never an
interval — it was two point estimates from two windows, whose own intervals ran
[$1.07, $5.41] and [$0.83, $10.25]. Quote a point estimate with its interval,
never the band.

**The eastward leg is priced, which contradicts this project's earlier
conclusion.** `NEXT_STEPS.md` records it as "barely priced and not reliably
so", with a threshold interval spanning zero and a straight-line R² of 0.01. On
the re-timed premium, and reading tonnage from Swiss *imports* — US Census
export figures carry no mass at all, every `net_mass_kg` is zero — the kink is
clear: below −$0.95 an ounce each further dollar of discount pulls 7.4 tonnes
east, and above it the slope is flat at +0.11. The asymmetry the earlier work
found largely disappears: +8.9 tonnes per dollar west against −7.4 east.

## Does metal move?

The premium clears $0.78 on 798 of 2,820 days (28.3%). Against Swiss customs
exports to the United States, 139 months:

| Months | n | median t | mean t | max t |
|---|---:|---:|---:|---:|
| never cleared | 30 | **1.7** | 2.9 | 14.5 |
| cleared on 1–4 days | 50 | 2.5 | 7.3 | 112.4 |
| cleared on 5+ days | 59 | **6.6** | 23.4 | 195.4 |

Monotone, and monthly pressure correlates **0.699** with tonnes — against 0.632
for the mean premium, which is the convexity argument earning its keep.

## The relationship breaks in 2025

| Months clearing on 5+ days | n | median t | median pressure | tonnes per \$ |
|---|---:|---:|---:|---:|
| before Apr 2025 | 49 | 11.4 | $0.84 | **13.6** |
| after Apr 2025 | 10 | 4.4 | $2.45 | **1.8** |

The same premium stops producing the same shipments, and the signal did not
weaken — median pressure is three times higher afterwards. August 2025 had a
premium above $10 an ounce on sixteen days and 2.7 tonnes arrived; January 2025
had $13.64 and 195 tonnes came.

This is a finding about the quantity side, not a defect of the threshold. The
candidate explanation is inventory: COMEX registered stock rose sharply through
2025, and an arbitrage can be closed by warranting metal already in New York
rather than importing any — which produces no customs record at all. That is
exactly the asymmetry `CLAUDE.md` calls the project's deepest open problem, and
confirming it needs the daily warehouse series the project does not yet have.

## Files

| File | What it is |
|---|---|
| `build_carry_threshold.py` | the test, narrating its own argument |
| `estimate_threshold.py` | where kappa comes from, both directions |
| `*_output.txt` | both narrations, saved |
| `carry_threshold_daily.csv` | carry cost, excess, threshold flags, daily pressure |
| `carry_threshold_monthly.csv` | monthly means, days clearing, tonnes |
| `threshold_estimates.csv` | every threshold fitted, with intervals |
| `carry_threshold.pdf` / `.png` | the three panels |
