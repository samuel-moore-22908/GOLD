# The spread

The paper's price variable, built in reduced form, with the construction
narrated as it runs.

```
python claude/spread-series/build_spread.py
```

| File | What it is |
|---|---|
| `build_spread.py` | the construction; prints its own argument as it goes |
| `build_spread_output.txt` | that narration, saved |
| `spread_daily.csv` | 2,857 days, 2,820 of them usable |
| `spread_monthly.csv` | calendar-month means |
| `spread.pdf` / `.png` | the figure |

## What "the spread" means here

Not `F − S`. That is where the construction starts, not where it ends. The
spread the paper uses is the **New York premium**: the intercept of the daily
log futures curve, relative to London spot, with the New York leg read at the
London auction instant.

```
quoted spread   b(tau) = F(tau) - S
projection      ln F(tau_i) = a + b*tau_i        each day, weighted by open interest
the spread      p_hat = a - ln S                 a level, per cent of spot
excess carry    omega_hat = 365*b - r            a rate, points a year
```

## What the narration establishes

Each step prints the numbers that justify it rather than asserting it.

**The quoted spread cannot carry the argument.** Its dispersion runs from
\$4.17 in 2015 to \$39.81 in 2026 while gold quadrupled, so the same
proportional gap is worth four times the dollars at the end of the sample as at
the start; it correlates +0.40 with the gold price. It rises monotonically with
the delivery calendar — \$2.79 mean inside fifteen days, \$20.60 beyond ninety
— correlating +0.33 with days to delivery, which is carry, not dislocation.
And it mixes a level with a rate, so any single summary must pick a horizon and
the pick decides the answer.

**The projection removes both.** Median R² 0.9987 across six contracts a day,
residual 2.7 basis points of price. The fitted carry averages 2.75% a year and
correlates 0.952 with SOFR — which is a check, not an input, since no interest
rate enters the fit.

**The calendar artefact is gone.** That is the test worth running:

| | correlation with days to delivery |
|---|---:|
| quoted spread | **+0.327** |
| the premium | **−0.046** |

**The clock is gone too.** Reading the New York leg at the London auction
rather than three and a half hours later cuts the daily standard deviation from
0.499 to 0.225 percentage points of spot.

## The series

On the 2,820 usable days — excluding five market holidays with no New York
print and the 32 days in 2020 when the curve fit itself broke, both flagged
rather than dropped:

| | mean | sd | min | max |
|---|---:|---:|---:|---:|
| spread, % of spot | −0.017 | 0.169 | −0.815 | 1.489 |
| spread, \$/oz | −0.036 | 3.95 | −30.17 | 50.93 |
| excess carry, pp a year | 0.634 | 0.591 | −3.096 | 3.272 |

A mean of essentially zero over eleven years is the first thing to check:
arbitrage pins New York to London, as it should. The largest monthly readings
are April 2020 (+1.028%, on four usable days) and **January 2025 (+0.499%,
\$13.64 an ounce, on twenty-one days)**.

## The figure

Two panels, one argument. Panel A is the quoted spread in dollars, framed at
the 99.5th percentile with the nine days beyond it marked at the edge — the
January 2026 print of −\$237 would otherwise flatten eleven years into a line.
Panel B is the spread the paper uses, daily and monthly, in per cent of spot.

Both panels show gaps as gaps and mark what falls outside the frame rather than
cropping it silently.
