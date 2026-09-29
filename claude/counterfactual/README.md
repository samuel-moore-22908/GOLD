# How much gold trade would not otherwise have happened

A back-of-the-envelope counterfactual. Fit a baseline to gold shipments into
the United States before the tariff episode, project it through, and call the
gap excess trade.

```
python claude/counterfactual/build_counterfactual.py
```

| | |
|---|---|
| series | Swiss and UK exports to the US, tonnes and dollars, both HS headings |
| break | **November 2024**, the US election, when tariff risk became priceable |
| episode | November 2024 – March 2025, ending the month before the April exemption |
| baseline | seasonal monthly mean fitted to January 2021 – October 2024 |

Both legs are the exporters' own customs figures. US import figures would do
for value but carry no mass at all, so tonnage has to come from the other side.

## The headline

| | tonnes | dollars |
|---|---:|---:|
| Switzerland | 483 | $45.0bn |
| United Kingdom | 185 | $16.5bn |
| **Both legs** | **667** | **$61.5bn** |

The implied price of the excess is **$2,867 an ounce**, which is where gold
traded over those months — the tonnage and the value are telling the same
story rather than two different ones, which is the first thing to check when
a counterfactual is this simple.

## The baseline is fragile, and that is the finding

A single baseline would hide how much the answer depends on it, so sixteen are
fitted: two pre-periods (2021–24, and 2015–24 excluding 2020), with and
without a trend, with and without seasonality, in levels and in logs.

| window | range across 16 specifications | median |
|---|---|---:|
| **Episode**, Nov 2024 – Mar 2025 | **637 to 699 t** — a spread of 10% | 683 |
| Full window, Nov 2024 – Jul 2026 | 457 to 786 t — a factor of 1.7 | 704 |

Over five months any sane baseline predicts a small number against an actual
one that is very large, so the choice barely matters. Over twenty-one months
the baseline accumulates and the trend assumption starts to drive the answer:
a log-linear trend fitted to 2021–24 falls at 1.65% a month, and extrapolating
that for two years is not something to rest a number on.

**Quote the episode. Treat the longer window as an illustration, not an
estimate.**

## What it is next to the statistics it lands in

| | |
|---|---:|
| US goods imports, Nov 2024 – Mar 2025 | $1,451bn |
| US goods deficit, same months | $615bn |
| excess gold | **$61.5bn** |

That is **4.2% of imports and 10.0% of the goods deficit** over those five
months.

None of this metal was consumed, imported for use, or in any economic sense
bought by America. It was moved between vaults because a tariff might otherwise
have applied to it, and a fifth of it went back out within five months of the
exemption (see `claude/spread-vs-hurdle`). It still enters the trade balance at
full value.

## What this is not

It is a difference from a projected baseline, not a causal estimate. The
baseline assumes that absent the tariff episode, shipments would have continued
at their pre-election seasonal average — which is a statement about
counterfactual quiet, not something the data can verify. Three specific threats:

- **Other shocks.** Anything else moving gold westward in those five months is
  counted as tariff excess. The spread evidence in `claude/carry-threshold`
  argues against a coincidence, but does not rule one out.
- **Anticipation.** If shipments rose before November 2024 in expectation of
  the election, the baseline is already contaminated upward and the excess is
  understated.
- **The end date.** Ending at March 2025 captures the episode and excludes the
  reversal. That is the right window for "how much extra crossed", and the
  wrong one for "how much extra ended up there".

## Files

| File | What it is |
|---|---|
| `build_counterfactual.py` | the estimate, narrating its own argument |
| `build_counterfactual_output.txt` | that narration, saved |
| `counterfactual_monthly.csv` | actual, baseline, excess and cumulative excess by month |
| `counterfactual_specifications.csv` | all sixteen baselines and what each implies |
| `counterfactual.pdf` / `.png` | the two panels |
