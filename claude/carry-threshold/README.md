# When the spread clears carry, and whether metal moves

The cash-and-carry test, run properly. Buy London metal, finance and store it
to the delivery date, deliver against a COMEX contract: it pays only if the
spread exceeds carry, and metal only moves if what is left also covers the cost
of shipping it.

```
python claude/carry-threshold/build_carry_threshold.py
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
| excess | mean −$0.25/oz |

Panel A of the figure shows why the raw number is useless as a signal: the
carry line is itself a sawtooth, resetting every delivery cycle, and the quoted
spread oscillates around it. Almost everything in `F − S` is the calendar.

## The decomposition checks out — and the check is the finding

| Excess compared with | corr | sd of difference |
|---|---:|---:|
| the premium **before** re-timing (same settlement) | **0.998** | $0.78 |
| the premium **re-timed** to the London auction | 0.276 | $12.14 |

The first line is the identity: subtracting carry from one contract's spread
reproduces the curve's intercept to 78 cents an ounce, which is just the
difference between reading one contract and fitting six.

The second is not a failure of it. The quoted spread is struck at the New York
settlement and London spot three and a half hours earlier, so the excess
carries the whole timing error. The arithmetic confirms it: a premium with
standard deviation $3.95 against a timing error of $12.14 implies a correlation
of 0.309, and 0.276 is observed. Averaging recovers it — 0.737 monthly, 0.822
quarterly.

**So the textbook test cannot be run on the quoted spread at daily frequency.**
The measurement error is $12 an ounce against a shipping cost of about $3: the
thing being measured is a third the size of the error in measuring it. It needs
the re-timed premium, or monthly averaging, or both.

## Does metal move?

The threshold is `kappa` = $3.00–$3.77 an ounce — freight, insurance,
recasting, handling. **This is the weakest number here**: only the COMEX
delivery-out charge of $0.35 is public, and the band is the hinge estimated
from flows in earlier work. Note that transit financing is *not* added on top:
financing from purchase to delivery is already inside the carry subtracted in
step 1, and adding it again would double-count.

The premium clears $3.00 on 296 of 2,820 days (10.5%) and $3.77 on 227 (8.0%).
It is crossed rarely, which is the point — for most of eleven years arbitrage
holds the premium inside the cost of acting on it and nothing moves.

Against Swiss customs exports to the United States, 139 months:

| Months | n | median t | mean t | max t |
|---|---:|---:|---:|---:|
| never cleared | 82 | **2.3** | 4.7 | 32.0 |
| cleared on 1–4 days | 36 | 4.7 | 12.9 | 112.4 |
| cleared on 5+ days | 21 | **14.8** | 47.1 | 195.4 |

Monotone, and a sixfold step in the median. Monthly pressure — the daily hinge
`max(0, X − kappa)` averaged within the month, not the hinge of the monthly
average, since the function is convex — correlates **0.681** with tonnes.

## The relationship breaks in 2025

| Months clearing on 5+ days | n | median t | median pressure | tonnes per \$ |
|---|---:|---:|---:|---:|
| before Apr 2025 | 15 | 44.5 | $1.82 | **24.4** |
| after Apr 2025 | 6 | 5.8 | $3.07 | **1.9** |

The same premium stops producing the same shipments, and it is not that the
signal weakened — the median pressure is *higher* afterwards. August 2025 had a
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
| `build_carry_threshold_output.txt` | that narration, saved |
| `carry_threshold_daily.csv` | carry cost, excess, threshold flags, daily pressure |
| `carry_threshold_monthly.csv` | monthly means, days clearing, tonnes |
| `carry_threshold.pdf` / `.png` | the three panels |
