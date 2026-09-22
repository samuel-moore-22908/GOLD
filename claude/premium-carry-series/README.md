# The premium and the carry: two series from one daily projection

Both series come out of the same regression, run once per trading day. Nothing
here needs a lease rate, a storage schedule, or — for the premium — any
interest rate at all. The method is the one in
`claude/spread-reduced-form/REDUCED_FORM_MODEL.pdf`.

```
.venv/Scripts/python.exe claude/premium-carry-series/build_premium_carry.py
.venv/Scripts/python.exe claude/premium-carry-series/make_premium_carry_figure.py
```

| File | What it is |
|---|---|
| `build_premium_carry.py` | the builder; every specification choice is a named constant at the top |
| `premium_carry_daily.csv` | 2,857 days, 2 Jan 2015 – 20 Aug 2026 |
| `premium_carry_monthly.csv` | calendar-month means of the daily series |
| `build_premium_carry_output.txt` | the diagnostics below, as printed |
| `make_premium_carry_figure.py` → `premium_carry.pdf`/`.png` | the two panels |
| `raw_cache/` | LBMA and FRED responses, fetched once and reused |

The two CSVs and the cache are not in git: the repository's policy is that data
regenerates from source rather than being committed (`*.csv` is gitignored at
the root, with the fetch procedures in `DATA_SOURCES.md`). The builder rebuilds
both files, and re-fetches the public series it needs, in one command and under
a minute. The script, the diagnostics it printed, and the figure are the
committed record.

---

## The recipe

**1. Assemble the day's cross-section.** From
`data/processed/comex_contract_daily.csv` (Databento `GLBX.MDP3`: settlement
prices and open interest by contract), keep the contracts with
`15 ≤ τ ≤ 400` days to first notice, open interest of at least 1,000 lots, and
a settlement. That leaves a median of six contracts a day, range four to nine.

**2. Fit the curve.** Weighted least squares of `ln(settlement)` on `τ`, with
weight `OI^0.5` on the squared residual. Two numbers come out: the intercept
`a` and the slope `b`. Keep the standard errors and the R², which are the
quality control in step 6.

**3. The premium is the intercept, relative to London.** `exp(a)` is the
forward curve extrapolated to zero horizon — the price today of
New-York-deliverable metal. Against the London benchmark fetched from
`prices.lbma.org.uk/json/gold_pm.json`:

```
premium_log = a - ln(S)          premium_pct = 100 × premium_log
premium_usd = S × (exp(premium_log) - 1)
```

**4. The carry is the slope, annualised.** `carry_pct = 100 × 365 × b`,
continuously compounded. This is what the market charges to hold gold in New
York for a year, revealed by the shape of the curve.

**5. Attach rates for comparison only.** SOFR from April 2018, effective fed
funds before it, and the three-month bill, all from FRED's keyless CSV
endpoint. Each is quoted ACT/360, so each is scaled by 365/360 before being
compared with a carry annualised on 365. `excess_carry_pp = carry_pct − rate`.
None of this enters the fit.

**6. Flag rather than drop.** `fit_ok` marks days where the curve fit has
R² ≥ 0.90. `gap_days` records the days since the previous observation so that
plotting code can break the line instead of drawing across a hole.

**7. Aggregate to monthly.** Calendar-month means, with the day count kept, for
anything that will be matched to customs data.

---

## What comes out

| | mean | sd | min | max |
|---|---:|---:|---:|---:|
| premium, % of spot | 0.002 | 0.499 | −5.548 | 4.111 |
| premium, \$/oz | 0.21 | 12.81 | −268.87 | 80.11 |
| carry, % a year | 2.754 | 1.793 | −0.026 | 6.033 |
| excess carry, pp a year | 0.636 | 0.592 | −3.096 | 3.272 |

The curve fits well: median R² 0.9987, median residual 2.73 basis points of
price. The 32 days below R² 0.90 are **all in 2020**, mostly April and March —
the projection breaks exactly where the market did, and nowhere else in eleven
years.

The mean premium of essentially zero is the first reassurance: over eleven
years arbitrage pins New York to London, which is what it should do.

---

## The sanity check: carry against rates that are not in the fit

| sample | n | corr | slope | const | R² |
|---|---:|---:|---:|---:|---:|
| full sample, daily | 2,857 | 0.952 | 0.884 | 0.881 | 0.907 |
| monthly means | 140 | 0.955 | 0.887 | 0.876 | 0.913 |
| vs 3-month T-bill | 2,857 | 0.969 | 0.909 | | |
| zero rates 2015–19 | 1,230 | 0.903 | 0.941 | 0.619 | 0.815 |
| hiking 2022–23 | 485 | 0.953 | 0.754 | 1.876 | 0.908 |

A slope near one means a point of SOFR shows up as a point of carry, and it
does. The fit against the three-month bill is tighter than against the
overnight rate, which is what should happen: the curve is priced off a term
rate, not an overnight one.

**Two things in that table are not noise and should not be read as failures.**

*The constant of about 0.88 points.* Carry sits systematically above the
dollar short rate. That wedge is `storage − lease rate + funding spread`, and
it is the project's open question, not a defect of the estimator. It is the
same object the earlier notes called the calm slope, measured here at 0.64
points on average over the full sample.

*Changes correlate far less than levels.* Day-on-day, carry and SOFR correlate
0.008. That is expected: an overnight rate is a step function that moves on
eight scheduled dates a year, so at daily frequency there is nothing to
correlate with. Against the three-month bill, which moves with expectations,
the daily change correlation is 0.185 and the monthly change correlation 0.603
with a slope of 0.88. Levels are the informative comparison here; changes are
informative only against a forward-looking rate.

---

## What the premium series says about its own noise

The London leg is struck at 15:00 London and the New York leg about three and a
half hours later, so any move in between lands in the premium. The next day's
London auction has already absorbed that move, which makes the next-day London
return a usable proxy for it:

- `corr(premium_t, next-day London return) = 0.394`, R² 0.155;
- the premium's standard deviation is 0.420 pp of spot on calm days and 0.674
  on volatile ones, and the correlation with the proxy rises from 0.086 to
  0.477 across those groups;
- the six largest absolute readings are all days of violent intraday moves —
  30 January 2026 prints −5.5% on a day when the London benchmark fell from
  5,405 to 4,982 and kept falling after the auction. The curve fit that day has
  an R² of 0.9986: the whole curve shifted down together, exactly as a common
  timing shock should.

Two conclusions follow, and they are the practical payoff of the diagnostic.
The daily series has a noise floor of roughly 0.4 pp of spot, so **single days
cannot carry an argument**. Averaged over a 21-day month that floor falls to
about 0.09 pp, against a January 2025 monthly mean of 0.52 pp — comfortably
above it. The monthly series is the one to use for anything matched to trade
data, and re-timing the New York leg to the London auction instant is the fix
that would make daily readings usable.

Through the episode, monthly means:

| month | premium % | \$/oz | carry % | SOFR % | excess pp |
|---|---:|---:|---:|---:|---:|
| 2024-11 | 0.057 | 1.54 | 4.613 | 4.702 | −0.089 |
| 2024-12 | 0.178 | 4.76 | 4.778 | 4.605 | 0.174 |
| **2025-01** | **0.523** | **14.28** | 5.207 | 4.376 | 0.832 |
| 2025-02 | 0.109 | 3.15 | 5.180 | 4.404 | 0.776 |
| 2025-03 | 0.190 | 5.80 | 4.912 | 4.387 | 0.525 |
| 2025-04 | −0.151 | −4.25 | 4.778 | 4.410 | 0.368 |

Reported as a check that the series is not garbage, not as a result.

---

## Specification choices, and how much they matter

Every variant is a column in the daily file, so this can be checked rather than
argued about.

| variant | corr with baseline | mean diff | max abs diff |
|---|---:|---:|---:|
| premium, unweighted | 0.9975 | 0.014 | 0.307 |
| premium, open-interest weights | 0.9992 | −0.010 | 0.166 |
| premium, quadratic fit | 0.9871 | −0.038 | 0.877 |
| carry, unweighted | 0.9992 | −0.033 | 0.628 |
| carry, open-interest weights | 0.9991 | 0.035 | 0.745 |
| carry, quadratic fit | 0.9697 | 0.256 | 3.835 |

**A discrepancy in the project's existing code, recorded rather than quietly
fixed.** Every document here specifies weighting by `√(open interest)`, and
`claude/mechanism-figures/validate_mechanism.py` implements it as
`np.polyfit(x, y, 1, w=np.sqrt(OI))`. But numpy applies `w` to the *unsquared*
residual, so that call minimises `Σ OI·e²` — it weights by open interest, not
its square root. Verified directly against an explicit WLS solve. This builder
takes the documented convention as the baseline (`WEIGHT_POWER = 0.5`) and
carries the implemented one as a robustness column. The two agree to a
correlation of 0.999, so nothing published so far turns on it, but the
documents and the code should be brought into line.

---

## What would improve these series

1. **Re-time the New York leg** to the London auction instant using
   intraday bars. It is the largest available improvement and removes most of
   the 0.4 pp daily noise floor.
2. **Add the loco-London forward curve** (ICE Gold Daily Futures, on Databento
   as `IFUS.IMPACT`) and measure the premium as one exchange-cleared curve
   against another, at a settlement struck inside the London auction window.
3. **Replace the overnight rate** in `excess_carry_pp` with a term rate built
   from SOFR futures, which are in the CME dataset already in use. The excess
   is currently measured against the wrong maturity.
