# How much gold trade would not otherwise have happened

Back of the envelope. Fit a straight line to gold shipments into the United
States before the tariff episode, extrapolate it, and measure the area between
the actual series and that line.

```
python claude/counterfactual/build_counterfactual.py
```

| | |
|---|---|
| series | Swiss and UK exports to the US, tonnes and dollars, both HS headings |
| baseline | a straight line fitted to January 2021 - October 2024, 46 months |
| break | **November 2024**, the US election, when tariff risk became priceable |
| episode | November 2024 - March 2025, ending the month before the April exemption |

Both legs are the exporters' own customs figures. US import figures would do
for value but carry no mass at all, so tonnage has to come from the other side.

## The number

The fitted line runs at **-0.19 tonnes a month**, reaching 6.9 tonnes by
January 2025 against a pre-period averaging 11.7.

| | actual | baseline | excess |
|---|---:|---:|---:|
| episode, tonnes | 734 | 35 | **699** |
| episode, \$bn | 65.5 | 2.6 | **62.9** |
| to date, tonnes | 896 | 110 | 786 |
| to date, \$bn | 81.8 | 9.4 | 72.3 |

The implied price of the excess is **\$2,799 an ounce**, which is where gold
traded over those months - the tonnage and the value agree rather than telling
two stories, which is the first thing to check when a counterfactual is this
simple.

Where the pre-period starts moves it, but not much over the episode:

| line fitted from | slope | episode excess |
|---|---:|---:|
| January 2021 | -0.19 t a month | **699 t** |
| January 2019 | -0.22 t a month | 693 t |
| January 2015 | +0.11 t a month | 645 t |

## For scale

\$63bn is **4.3% of US goods imports** over those five months and **10% of the
goods deficit**.

None of this metal was consumed, imported for use, or in any economic sense
bought by America. It was moved between vaults because a tariff might otherwise
have applied to it, and a fifth of it went back out within five months (see
`claude/spread-vs-hurdle`). It still enters the trade balance at full value.

## What this is not

A difference from an extrapolated line, not a causal estimate. The baseline
assumes that absent the episode, shipments would have carried on along their
pre-election path - a statement about counterfactual quiet that the data cannot
verify. Three specific threats:

- **Other shocks.** Anything else moving gold westward in those five months is
  counted as tariff excess. The spread evidence in `claude/carry-threshold`
  argues against coincidence but does not rule it out.
- **Anticipation.** If shipments rose before November 2024 in expectation of
  the election, the baseline is contaminated upward and the excess understated.
- **The end date.** Ending at March 2025 captures the episode and excludes the
  reversal. That is the right window for "how much extra crossed" and the wrong
  one for "how much extra ended up there". Months after March add a further
  87 tonnes, which the headline excludes and the figure leaves unshaded.

## Files

| File | What it is |
|---|---|
| `build_counterfactual.py` | the estimate, narrating its own argument |
| `build_counterfactual_output.txt` | that narration, saved |
| `counterfactual_monthly.csv` | actual, baseline, excess and cumulative excess by month |
| `counterfactual.pdf` / `.png` | the figure |
