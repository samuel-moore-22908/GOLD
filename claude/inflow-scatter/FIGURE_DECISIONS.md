# Inflow figure — design decisions

One figure showing that during the tariff scare gold became an outlier in **both**
the direction of its trade and its magnitude: it flipped to flowing into the US,
and it did so through a channel carrying real value.

Status: **built.** Figure at `claude/inflow-scatter/inflow_scatter.html`,
underlying points at `inflow_scatter_points.csv`, data from
`data/processed/us_hs4_universe_monthly.csv` (fresh Census API pull, all 1,229
HS4 headings, Jan–Apr 2024 and 2025, both flows).

---

## The correction that shapes the whole figure

The Grubel–Lloyd index runs the opposite way to how we first framed it.

```
GL = 1 − |X − M| / (X + M)
```

- `GL = 1` → **perfectly balanced two-way trade** (X = M)
- `GL = 0` → **completely one-directional** (X = 0 or M = 0)

So GL *falls* toward zero as trade becomes one-directional. Plotting GL on the
y-axis and expecting gold in the upper right inverts the geometry — gold would
sink to the bottom. GL is also **unsigned**: a pure exporter and a pure importer
both sit at 0, which cannot express "flowing *into* the US".

## Chosen y-axis: import share

```
import share = M / (M + X)
```

| Value | Meaning |
|---|---|
| 0 | pure export |
| 0.5 | balanced two-way trade |
| 1 | pure import |

Rising = shifting toward net imports, which is exactly the claim. It is bounded,
has a natural reference line at 0.5, and is a signed rescaling of the normalized
trade balance: `import share = (1 − NTB)/2` where `NTB = (X−M)/(X+M)`.

### Alternatives considered

| Measure | Formula | Why not |
|---|---|---|
| Grubel–Lloyd | `1 − \|X−M\|/(X+M)` | Inverted for this claim, and unsigned |
| 1 − GL | `\|X−M\|/(X+M)` | Right direction, still unsigned — a pure exporter also scores 1 |
| Normalized trade balance | `(X−M)/(X+M)` | Signed and symmetric, but puts gold at the *bottom*; only an axis flip from import share |
| Log ratio | `ln(M/X)` | Best statistical properties, unbounded, undefined at zero. **Use as a robustness check, not the display axis** |
| Lafay index | — | Controls for country size; unnecessary for a single reporter |

## Chosen x-axis: US imports, log scale

Log10 because HS4 import values span five orders of magnitude. Imports rather
than total trade (X+M) keeps the axis reading as "how much came in", which is the
magnitude half of the claim.

## Marks

Two points per commodity joined by an arrow pointing at the Jan–Apr 2025
position. Gold highlighted and labelled; all others neutral grey. A dashed
reference line at 0.5 separates import- from export-dominated.

## Periods

- **Before:** Jan–Apr **2024**
- **During:** Jan–Apr **2025**

Same months year-over-year rather than an adjacent-quarter comparison, because
commodity trade is strongly seasonal.

---

## Gold's real position (mirror-derived)

| Window | Imports | Exports | Import share | GL | Net mass in |
|---|---|---|---|---|---|
| Jan–Apr 2024 | $1.16bn | $8.24bn | 0.12 | 0.25 | 17 t |
| Jan–Apr 2025 | $43.15bn | $17.70bn | 0.71 | 0.58 | 639 t |

Gold crosses the 0.50 balance line and moves an order of magnitude right. The
**37× rise in tonnage** is what rules out a pure gold-price explanation, and is
worth stating in the caption — value alone would be contaminated by the price
move over the same window.

---

## Blockers

**1. The US-reported import series is wrong by roughly 50×.**
`data/processed/us_gold_trade_hs4_monthly.csv` reports US imports from
Switzerland of **$0.82bn** for Jan–Apr 2025. Swiss-reported exports to the US for
the same window and HS code are **$43.15bn**. The file also carries only four
partner countries and no quantity field. This is almost certainly the same defect
noted earlier as "the export pulls get double the rows the import pulls get".
The figure cannot use the US import series until this is re-pulled.

**2. There is no all-commodity monthly pull.** The processed data covers HS 7108
and 7115 only. BACI is all-commodity but **annual and ends before 2025**, so it
cannot cover the window. A fresh Census pull is required: all HS4, monthly,
imports and exports, Jan–Apr 2024 and Jan–Apr 2025.

**3. No quantity field on the US pull.** Needed to separate price from volume.
The Swiss file has `net_mass_kg`; the US file does not.

## Open questions

- **HS level.** HS4 gives ~1,250 codes — too many to plot legibly. Either plot
  all in faint grey with a labelled subset, or restrict to the top ~50 by 2024
  trade value. Leaning toward all-faint-plus-highlight, since "gold is an
  outlier" is a claim about the whole distribution.
- **Quantifying the outlier.** Compute each commodity's displacement in
  standardised (Δlog imports, Δimport share) space and report gold's percentile
  in the caption, so "outlier" is a number rather than an impression.
- **UK corridor.** `gbr_gold_trade_hs4_monthly.csv` returned zero US-bound flows
  in this window, which is implausible given London vault drawdowns. Needs
  checking before the UK is treated as absent.
- **7115 vs 7108.** Whether to show only 7108 or both gold codes.


---

## Correction to the project's stated data plan

`CLAUDE.md` build order item 5 says "US Census and HMRC monthly **HS 7108**".
For the US leg that is wrong for the 2025 episode, and following it would miss
the entire inflow.

**Switzerland reports the bullion as HS 7108. US Census books the same
shipments as HS 7115** ("articles of or clad with precious metal, NESOI").

US imports from Switzerland, January 2025:

| Heading | Value |
|---|---|
| 7115 | **$18.90bn** |
| 7108 | $0.58bn |

HS 7115 US imports run at $0.4–0.6bn/month through 2024, then $30.4bn in Jan
2025, $24.7bn Feb, $17.1bn Mar, collapsing to $1.6bn in April as exports spike
to $8.6bn — the round trip. Any US-side gold series must carry **both**
headings or it is measuring the wrong thing.

This also explains the mirror gap flagged earlier: `us_gold_trade_hs4_monthly.csv`
looked broken because it was being read at 7108 only. The corridor pull is
still limited to four partners, but the headline discrepancy was the code.

## What the figure actually shows

Gold combined (7108+7115) moves from **$5.25bn imports / share 0.30** to
**$81.71bn / share 0.72** — a 15.6× rise in import value and a crossing of the
balance line. Displacement rank **#2 of 100**.

**It is not rank #1.** HS 2937 (hormones and steroids) moved further on the
standardised measure: $2.68bn → $36.90bn with share going 0.44 → 0.92. That is
consistent with pharmaceutical tariff front-running, and it means the honest
claim is "gold was *among* the most extreme movers and the largest by value",
not "gold was the single biggest anomaly". HS 7106 (silver) is also in the top
five, which suggests a precious-metals cluster rather than a gold-specific
effect — worth addressing directly rather than leaving for a referee to find.

### Why the combined heading, and not 7115 alone

7115 alone rises 40× in import value but its share barely moves (0.81 → 0.89):
it was *already* import-dominated before the episode, so on its own it cannot
show a switch in direction. Only the combined series crosses 0.50. Both are
plotted, and the combined point is the one the directional claim rests on.
