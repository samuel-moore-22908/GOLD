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
| baseline | a straight line fitted to **all 118 months**, January 2015 - October 2024 |
| break | **November 2024**, the US election, when tariff risk became priceable |
| episode | November 2024 - March 2025, ending the month before the April exemption |

Both legs are the exporters' own customs figures. US import figures would do
for value but carry no mass at all, so tonnage has to come from the other side.

## The number

The line is fitted to the **whole series before the break**, not a recent
slice, so the baseline cannot be accused of being chosen to flatter the
result. It runs at **+0.11 tonnes a month**, reaching 17.8 tonnes by January
2025 against a pre-period averaging 11.1, and it is drawn across the whole
chart so the fit can be judged against the data that produced it.

| | actual | baseline | excess |
|---|---:|---:|---:|
| **all 20 months since, tonnes** | 896 | 372 | **524** |
| of which the episode, tonnes | 734 | 89 | 645 |

Twelve of the twenty months fall below the line and net off 171 tonnes;
counting only the months above it would give 695 instead of 524.

### Tonnes net cleanly; dollars do not

Metal went west at about \$2,800 an ounce during the episode and came back east
later above \$4,000, so a dollar figure netted across the whole window turns on
the price path rather than on the trade. Two defensible methods disagree by
more than a third on the same 524 tonnes:

| | |
|---|---:|
| fitting a separate line to the value series | \$58.4bn |
| valuing the excess tonnes at each month's realised price | \$41.3bn |

So the dollar figure quoted is the **episode**: **\$60.0bn** over the five
months to March 2025, at the \$2,778 an ounce those shipments actually moved
at. That is also the number that matters for the trade statistics, which record
gross flows rather than net ones - a tonne leaving later adds to exports, it
does not subtract from imports.

Where the pre-period starts moves it, but not much over the episode:

| line fitted from | slope | episode excess |
|---|---:|---:|
| January 2015 | +0.11 t a month | **645 t** |
| January 2019 | -0.22 t a month | 693 t |
| January 2021 | -0.19 t a month | 699 t |

## For scale

Measured over the same five months the dollar figure refers to: **\$60bn of
excess against a goods deficit of \$615bn - 10% of it**, and 4.1% of imports.

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
  one for "how much extra ended up there". The headline now counts every month
  after the election, so the reversal months are netted in rather than ignored
  - but a month of metal going back out does not cancel a month of it going in
  as far as the trade statistics are concerned, since both are recorded gross.

## The whole chain in one panel

`make_whole_chain_panel.py` puts the price signal and the physical response on
one axis: shipments, the extrapolated line, the shaded excess, and underneath
them a strip marking every month the spread cleared carry plus shipping.

It makes one thing plain that the excess figure alone does not. **The spread
cleared the cost of shipping in 60 of these months and the metal moved in bulk
in five.** Clearing pays for a shipment; it does not compel one. Most of 2024
clears with flows flat, and almost every month after the April 2025 exemption
clears while nothing moves - which is the inventory channel the carry-threshold
work points at, visible here as a picture rather than a table.

## Files

| File | What it is |
|---|---|
| `build_counterfactual.py` | the estimate, narrating its own argument |
| `make_whole_chain_panel.py` | the single panel: signal, response and excess |
| `whole_chain.pdf` / `.png` | that panel |
| `build_counterfactual_output.txt` | that narration, saved |
| `counterfactual_monthly.csv` | actual, baseline, excess and cumulative excess by month |
| `counterfactual.pdf` / `.png` | the figure |
