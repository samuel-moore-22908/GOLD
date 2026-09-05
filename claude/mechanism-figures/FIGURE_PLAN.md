# Three figures for the mechanism section

These follow Figure 1 (`claude/gold-panel/figures/gold_panel.png`) and its
chronology. Figure 1 establishes *that* gold made a round trip no other traded
good made. These establish *why*: a price opened on the location of metal, metal
responded to it above a threshold and not below, and the return leg obeyed a
different rule entirely.

Every number below is printed by `validate_mechanism.py` (output preserved in
`validation_output.txt`). Nothing here is a guess about how the data might
behave; the series were built and checked first. Build order is 2, 3, 4 — each
depends on the one before it.

---

## Current state, and how it differs from what is planned below

Three figures, in `figures/`:

| File | What it is |
|---|---|
| `fig2_dislocation.png` | The price of location. Unchanged. |
| `fig3_two_legs.png` | **Both legs on one pair of axes** — westward with the estimated threshold, eastward with none. This merges what the plan below calls figure 3 and the left panel of figure 4. |
| `fig4_monthly_path.png` | **The monthly path, standing alone.** Formerly the right panel of figure 4. |

**Figure 3 is estimated on January 2023 to the end of the data**, currently July
2026, n = 43. 2020 and the March 2022 sanctions shock are location dislocations
of a different kind — grounded aircraft and shut refineries in one case, a
payments and counterparty rupture in the other — and folding them into an
exercise about a tariff threat widens the scope of the claim past what the paper
argues.

The cost is precision, not the result. The westward threshold comes out at
**$3.77** against **$2.99** on the full 2015–2026 series — comfortably inside its
own interval, which is about as close as two independent windows get. But that
interval is **[$0.83, $10.25]**, so the threshold is well located and poorly
pinned. Every estimate quoted on the figure is now interpolated from
`kink_estimates.csv` at draw time rather than typed into the do-file, because an
earlier revision shipped a chart captioned $3.02 with its dashed line standing
at $3.77.

Two things were lost with the earlier window, and both are worth remembering
rather than pretending away:

- **The three-unrelated-causes argument is no longer on the figure.** It was the strongest thing in the exercise — covid, sanctions and tariffs producing one response — and it now lives only in this document and in `validation_output.txt`. If a reviewer asks whether the hinge is an artefact of one episode, the full-sample fit is the answer and it should be reported in the text.
- **The dollar-versus-rate comparison reverses on the short window.** Rate space fits better by 15% of SSR on 2023–2025, where it lost by 13% on 2015–2026. The two specifications are only distinguishable when the gold price moves a lot, and the short window has a third of the observations and half the price variation, so this is weak evidence against a prior that never came from the data: freight, insurance and recasting are charged on weight, so a physical transfer cost is a dollar figure. The figures stay in dollars and `estimate_kink.py` prints the caution.

### The eastward leg now carries a fitted line, and my earlier claim was too strong

The first version of this panel had no fitted line, on the grounds that its
below-kink slope rested on two discount months. **Extending the window to the
present changed that.** There are now nine months with a premium below −$2, and
the fit is no longer hostage to a pair of points:

| | westward | eastward |
|---|---|---|
| threshold | **$3.77** | −$0.17 |
| 90% interval | [$0.83, $10.25] | **[−$2.69, +$4.65]** — spans zero |
| slope below | +0.5 t/$ | **−3.0 t/$** |
| slope above | +7.8 t/$ | +0.8 t/$ |
| R² kink | 0.38 | 0.13 |
| R² straight line | 0.27 | 0.01 |
| correlation | +0.52 | −0.11 |

So the flat statement made earlier in this project — that the return leg shows
*no* price response at all — does not survive the longer window and should not be
repeated. What survives is weaker and worth stating as such: **when New York goes
to a discount, more metal does appear to leave**, which is the direction
`CLAUDE.md`'s "sign is directional" prediction called for. But the threshold
interval spans zero, the straight-line R² is 0.01, and a correlation of −0.11 on
43 months cannot be told from noise. Report it; do not rely on it.

The asymmetry that motivates the figure is intact, and sharper for being
quantified rather than asserted: westward has a threshold six times its own
below-slope, eastward has one that cannot be distinguished from zero.

Everything below describes the full-sample version and is kept as the record of
how the estimate was arrived at.

## The kink, estimated

`estimate_kink.py` replaces the drawn hinge with a fitted one. Model, threshold
found by profile least squares with 15% trimming, 90% interval from 2,000 iid
and moving-block bootstrap replications:

```
tonnes = a + b1*(x - g) + b2*max(0, x - g)
```

**The unit matters, and it is an economic question rather than a modelling
preference.** Freight, insurance and recasting scale with weight, not value, so
a threshold that is a physical cost should be constant in dollars an ounce — and
a constant *rate* threshold would then have to fall as gold rises. Gold ran from
$1,068 to $5,022 across this sample, a factor of 4.7, so the two specifications
are far apart. Fitting both:

| Specification | Threshold | R² | SSR |
|---|---|---|---|
| rate space, pp a year | +0.42 | 0.460 | 62,518 |
| **dollar space, $/oz over 90 days** | **+2.99** | **0.532** | **54,156** |
| straight line, no kink | — | 0.426 | — |

Dollar space wins by 13% of the sum of squares. **The threshold is a physical
cost**, which is the claim the paper wanted to be able to make and now can.

**ĝ = $2.99 an ounce over ninety days, 90% CI [$0.97, $5.58].** That is
**$96,000 a tonne**, or 0.11% of the metal's value at January 2025 prices —
squarely in the range air freight, insurance and recasting would plausibly cost,
which is a reassuring external check on a number estimated purely from
behaviour. Slope below the threshold 0.2 tonnes per dollar, indistinguishable
from flat; above it, 6.5.

Robustness: dropping the three largest months moves ĝ to $2.69. **Fitting on
2015–2023 alone, with the entire tariff episode excluded, gives $3.58** — the
episode is not what identifies the threshold. In logs no interior kink is
identified at all; the profile is flat to the trimming boundary. That is a real
limitation and worth stating: the hinge is a claim about quantities, and logs
compress precisely the months that make it.

### What the estimate exposed that the bucket medians hid

The hinge does not hold after the exemption. Splitting the months with a premium
above $6 an ounce:

| Window | n | Median tonnes shipped |
|---|---|---|
| before April 2025 | 13 | **68.7** |
| April 2025 onward | 7 | **5.8** |

Same price signal, a twelvefold difference in response. August and September
2025 carried premiums of $12.8 and $11.1 and moved 2.7 and 6.9 tonnes. The
relationship is therefore conditional, not structural, and the obvious candidate
for the conditioning variable is the stock already sitting in New York: COMEX
registered went from 440 t in January 2025 to 752 t in April, and once the metal
is there an arbitrage can be closed by delivering it rather than by importing
more.

If that is right it cuts *for* the paper rather than against it — it is the
sharpest available evidence that the flows were relocation and not absorption,
since a genuine demand shock would not switch itself off the moment the
warehouse filled. It also raises the priority of the CME vault pull, which is
now the missing variable in the specification rather than just a nice figure.
Until that exists this stays an interpretation, not a finding.

## Built

All three now exist, in `figures/`, drawn by `mechanism_figures.do` from inputs
written by `build_figure_data.py`. Two things came out of the drawing that the
plan below had wrong, and both are kept here rather than quietly edited out.

**Figure 2 does not show a return to zero.** The plan said April 2025 put the
premium "back inside the band". It does not. The collapse at the exemption is
violent and unmistakable — the smoothed series goes from +3.8 to −2.1 inside a
fortnight — but it then settles around **+0.5 points for the rest of 2025**,
above the ±0.41 calm band and never back inside it. The honest sentence is that
the premium fell hard and stayed at a lower plateau, not that arbitrage was
restored.

That reads as a problem for the story until Figure 3 is laid beside it, where it
becomes the opposite. Half a point is *below the hinge*. A premium that size
does not pay for a shipment, so metal stops moving even though the spread has
not closed — which is exactly what the flow data does from April onward. The two
figures corroborate each other precisely where the plan expected only one of
them to speak.

**The daily series is plotted as dots, not a line.** A faint line underneath the
read line was the plan, and it fails twice. Stata's `yscale(range())` only ever
widens an axis, so it cannot clip: the frame stretched to the daily minimum near
−6 and left two-thirds of the panel empty. More substantively, a line asserts
continuity between consecutive settlements that these data do not have — the
three-hour gap between the London fix and the New York settle makes each day an
independent draw carrying about four points of noise. Dots say that; a line
denies it. 41 of 389 sessions fall outside the frame and the note says so.

---

## Before anything else: the spread series in the repo cannot be used as it is

`data/processed/efp_dislocation_v2.csv` has two candidate measures and both are
contaminated by the delivery calendar.

`basis_usd` carries the roll sawtooth `CLAUDE.md` already warns about — over the
episode window, time to first notice cycles between 8 and 128 days, and carry
scales with it.

`implied_rate` was the prescribed fix, and it introduces the mirror-image
artefact. It divides by `days_to_first_notice`, so as delivery approaches the
annualised rate explodes on an unchanged dollar spread. The five largest
"dislocations" in the episode window are all within 16 days of first notice:

| Date | Contract | Basis $/oz | Days to notice | Implied rate |
|---|---|---|---|---|
| 2025-11-12 | GCZ5 | 76.85 | 16 | **42.4%** |
| 2025-07-22 | GCQ5 | 33.85 | 9 | 40.3% |
| 2025-01-23 | GCG5 | 20.75 | 8 | 34.5% |
| 2025-01-15 | GCG5 | 40.10 | 16 | 34.2% |
| 2025-01-17 | GCG5 | 33.50 | 14 | 32.2% |

A 42% annualised financing rate on gold did not happen. The divisor did.

**The fix, implemented in `validate_mechanism.py`:** a constant-maturity spread.
Each day, fit `log(settle)` on days-to-notice across every contract with 15–400
days left and at least 1,000 lots of open interest, weight by `sqrt(open
interest)`, and read the fit at a fixed 90-day horizon. The horizon never
changes, so neither artefact can survive. Then annualise against the LBMA PM fix
and subtract carry, exactly as `CLAUDE.md` specifies:

```
disloc = (F90 / XAU - 1) * 365/90  -  (SOFR + storage)
```

One honest caveat that shapes Figure 2's design. COMEX settles at 13:30 in New
York; the LBMA PM fix is struck around 10:00 there. A 1% intraday move therefore
injects roughly 4pp of pure timing noise into a single day's annualised figure,
which is the same order as the signal. Every daily-frequency claim must rest on a
10-session mean, and the real fix — a London quote contemporaneous with the COMEX
settle — belongs on the data to-do list.

---

## Figure 2 — The price of being on the right side of the border

**What it shows.** The constant-maturity 90-day COMEX–London dislocation, in
excess of carry, annualised, daily, June 2024 through December 2025. A quantity
that arbitrage is supposed to pin at zero, going to nearly four points and
staying there for four months.

**Form.** Single panel, time on the horizontal. Faint raw daily series
underneath, 10-session mean as the read line in Economist red. A grey band at
±1 s.d. of the June–November 2024 window — the "arbitrage-pinned" reference,
which is what the quantity looks like when nothing is wrong. Vertical rules at
2 April 2025 (exemption) and 31 July 2025 (customs ruling), labelled directly on
the plot rather than in a legend. Nine gaps over five days exist in the daily
series; draw them as gaps.

**What the reader gets, in the numbers already computed:**

| Window | Smoothed dislocation, pp annualised |
|---|---|
| Calm, Jun–Nov 2024 | mean **−0.18**, s.d. **0.41** |
| Dec 2024 | mean +0.62 |
| **Jan 2025** | mean **+2.47**, peak **+3.78** (23 Jan) |
| Feb–Mar 2025 | +1.46, +1.03 |
| **Apr 2025** | mean **−0.44** |
| Jul–Sep 2025 | +1.02, +0.92, +1.76 |
| Oct 2025 | −0.45 |

January runs six standard deviations above the calm mean and April is back inside
the band. The $26/oz at the January peak is the number to put in the text: that
is what the market was paying, over ninety days, purely for the metal being in
the right country.

**Scale reference worth keeping.** The largest smoothed value anywhere in
2015–2026 is +7.31pp on 9 April 2020, when flights were grounded and Swiss
refineries were shut. The tariff scare was the second-worst location dislocation
in eleven years, not the worst — which is a more interesting sentence than
claiming a record.

---

## Figure 3 — Nothing moves until the premium clears the cost of moving

**What it shows.** The hinge. 139 monthly observations, January 2015 to July
2026. Horizontal: mean constant-maturity dislocation that month, in pp.
Vertical: Swiss customs gold exports to the United States, tonnes, on a linear
scale so the flat stretch reads as flat.

**Form.** Scatter, one dot per month. Three colours: the 2024–25 tariff months in
Economist red, the 2020 COVID months in a second accent, everything else grey. A
hinge drawn on the cloud — sketched from the bucket medians, not fitted, since
the article is not the place for a regression and the shape does not need one.
An inset table or a small second panel carrying the bucket medians, which are the
honest summary of a relationship this lopsided.

**The relationship, as computed:**

| Dislocation, pp | n | Median t | Mean t | Max t |
|---|---|---|---|---|
| < −0.5 | 13 | 2.8 | 3.0 | 6.6 |
| −0.5 to 0 | 28 | 2.0 | 4.8 | 25.6 |
| 0 to 0.5 | 47 | 3.2 | 5.5 | 31.0 |
| 0.5 to 1 | 29 | 4.7 | 10.4 | 73.1 |
| 1 to 1.5 | 11 | 6.9 | 31.1 | 155.8 |
| **> 1.5** | 11 | **63.9** | 69.3 | 195.4 |

Flat at two or three tonnes a month across two and a half points of spread, then
a step to sixty-four. The kink sits somewhere between +0.5 and +1.0pp, which at
90 days and January's gold price is roughly $3–7 an ounce. That is an estimate of
the all-in transatlantic transfer cost obtained from behaviour rather than from
freight invoices, and `CLAUDE.md` is right that it is publishable on its own.
Worth saying in the text that it looks *higher* than physical freight, insurance
and recasting alone — which would put a risk premium, or the option value of
waiting, inside the threshold.

**The single strongest sentence available anywhere in this project.** Of the ten
largest months of Swiss gold shipped to the United States in eleven years, all
ten came when New York was paying a premium for location. Not one came when it
was not.

| Month | Tonnes | Dislocation, pp |
|---|---|---|
| Jan 2025 | 195.4 | +2.8 |
| Feb 2025 | 155.8 | +1.1 |
| May 2020 | 127.1 | +4.0 |
| Apr 2020 | 112.4 | +5.4 |
| Mar 2025 | 110.6 | +1.2 |
| Mar 2022 | 85.5 | +1.6 |
| Dec 2024 | 73.1 | +0.7 |
| Jun 2020 | 68.7 | +3.5 |
| Jul 2020 | 63.9 | +3.9 |
| Jul 2025 | 54.1 | +0.9 |

**Why the colouring matters more than the fit.** The top bucket is not the tariff
episode wearing eleven years of disguise. It is COVID, the sanctions shock of
March 2022, and the tariff scare — three unrelated causes producing one response.
That is what turns the article's claim from "here is what happened in 2025" into
"here is how this market works, and 2025 is the third time we have watched it."

**Two things to be straight about.** The correlation is contemporaneous
(+0.633) and beats the one-month lag (+0.507), because Zurich to New York is a
flight and the shipment is booked when it leaves — so this is a within-month
response, not a lagged one. And Spearman is only +0.379 against a Pearson of
+0.633, because a handful of extreme months carry the linear correlation. That
is a hinge behaving like a hinge, not a weakness, but the bucket medians rather
than the correlation should be what the text quotes.

---

## Figure 4 — The return leg is not priced, and that is the finding

**What it shows.** The same axes as Figure 3 with the flow reversed: US shipments
to Switzerland against the dislocation. The cloud is flat. There is no hinge,
no slope, and no sign.

| Dislocation, pp | n | Median t | Mean t |
|---|---|---|---|
| < −0.5 | 13 | 17.4 | 23.9 |
| −0.5 to 0 | 28 | 15.3 | 18.6 |
| 0 to 0.5 | 47 | 16.5 | 18.1 |
| 0.5 to 1 | 29 | 18.0 | 21.6 |
| 1 to 1.5 | 11 | 24.5 | 30.2 |
| > 1.5 | 11 | 12.7 | 12.8 |

Correlation with the dislocation is **−0.082**, and −0.113 at a month's lag. A
six-month inventory-overhang measure does no better: **−0.044**.

**This contradicts a standing claim in the project, and the article should say
so.** `CLAUDE.md` asserts under "Specification pitfalls" that sign is
directional — above carry, metal flows west; below carry, New York is cheap and
metal flows east; both regimes occur in the sample. The first half holds
emphatically. The second half does not hold at all. Metal did not go back
because New York went cheap. It went back because the reason to be there
stopped existing, which is a different event and is not in the spread.

**The four largest eastbound months in eleven years are all 2025, and their
dislocations have no common sign:**

| Month | Tonnes east | Dislocation, pp |
|---|---|---|
| Oct 2025 | 79.4 | −0.7 |
| Apr 2025 | 64.0 | −0.4 |
| Nov 2025 | 63.3 | +0.8 |
| May 2025 | 62.0 | +0.6 |

**Form.** Main panel is the flat scatter, drawn deliberately in the same frame
and scale as Figure 3 so the contrast is structural rather than argued. A small
paired time-series panel underneath — westbound above the axis, eastbound below,
tonnes per month, 2023 to 2026 — carries the timing that the scatter cannot: the
unwind is enormous and it begins the month the exemption lands.

**Why this is the most valuable of the three.** It is the empirical form of the
open conceptual problem in `CLAUDE.md`. The outbound leg is arbitrage: priced,
threshold-triggered, symmetric in the sense that a bigger premium buys more
metal. The return is inventory liquidation: unpriced, triggered by a legal event,
and spread over eight months rather than concentrated. A correction factor built
by assuming the two legs are the same mechanism run backwards will be wrong in
both directions, and this figure is the evidence for saying so.

---

## Considered and not proposed

**COMEX vault stocks, build and drain.** This would be the natural fourth figure
and it is item 1 of `CLAUDE.md`'s build order. It is not buildable.
`data/processed/comex_gold_stocks_daily.csv` is assembled from Internet Archive
snapshots and holds **six observations** between January 2025 and January 2026 —
30 Jan, 28 Mar, 7 Apr, 10 Jul, 31 Dec 2025 and 30 Jan 2026. Registered stock runs
440 t → 752 t → 628 t → 602 t across them, which is the right story and nothing
like enough points to draw. Needs the direct CME pull before it can be a figure.

**Value density: why gold and not cars.** The cleanest possible answer to the
outlier question — freight as a share of value, gold against every other heading
in the top hundred — and it would make the "no premium could pay for flying a car
across the ocean and back" line quantitative. Not buildable either:
`us_hs4_universe_monthly.csv` carries a quantity for **0 of 63,628 rows** and the
only unit present is `-`. The pull requests `GEN_QY1_MO`/`QTY_1_MO`, but Census
returns nothing for them at the country-aggregated HS4 level. An HS6 or HS10
re-pull would fix it, and it is worth doing.

**A regression of flow on the spread.** The hinge is the result, and a hinge
drawn on 139 dots is more convincing to this article's reader than a coefficient.
If a specification is wanted later, `CLAUDE.md` already gives the right one —
`flow ~ beta * max(0, EFP - carry - transfer_cost)` with the kink estimated
rather than assumed — and `mechanism_monthly.csv` is the panel to fit it on.
