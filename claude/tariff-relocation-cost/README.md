# The tariff relocation cycle, identified and priced

A causal analysis of the 2024–26 gold relocation episode, followed by a costed ledger of what
the tariff threat consumed. Seventeen pages, seven figures, eight scripts.

| File | What it is |
|---|---|
| `tariff_relocation_cost.tex` / `.pdf` | The memorandum |
| `code/*.py` | Everything that produced it, numbered in run order |
| `output/*.json`, `*.csv` | Every number cited in the memorandum. Not committed — the repo ignores `output/` under its regenerate-from-source policy, so these appear after a run |
| `figures/*.pdf` | The seven figures |

Build the PDF with `pdflatex tariff_relocation_cost.tex` twice.

## The argument

**A classification, not a tariff.** A COMEX delivery bar is cast, then stamped and lasered with
weight, purity and a serial. Additional US Note 1(a) to Chapter 71 says that further processing
takes it out of "unwrought." EO 14257's Annex II (2 Apr 2025) excluded only unwrought gold,
`7108.12.10`. CBP ruling N351466 (31 Jul 2025) put the bar in `7108.13.5500` and attached
`9903.01.25`, the Chapter 99 duty provision. EO 14346 (5 Sep 2025) closed the gap.

The hole is visible in EO 14346's own annex, where every gold line carries the order's
"Addition" flag **except** `7108.12.10` — which was already excluded. This pins the third event
to a document, which the project's earlier memorandum recorded as unpinnable. The Federal
Register's full-text search does not index tariff annexes, which is why: querying its API for
"7108" over Aug 2025 – Mar 2026 returns one document, about social security fees.

**The market responded to the dates, in the price of location, not the price of gold.** Five
narratively dated events, signs fixed in advance, randomization inference against every
non-event date 2015–2026:

| Event | Excess basis | Gold price (placebo) |
|---|---|---|
| Election, 5 Nov 24 | +$9.6 (z +0.6, ns) | **−3.0σ, p = 0.012** |
| EO 14257 Annex II, 2 Apr 25 | **−$48.2 (z −4.4, p = 0.003)** | ns |
| CBP N351466 reported, 8 Aug 25 | **+$27.5 (p = 0.028)** | ns |
| "Gold will not be Tariffed", 11 Aug 25 | **−$46.9 (p = 0.010)** | ns |
| EO 14346 signed, 5 Sep 25 | **−$28.4 (p = 0.012)** | ns |

Joint test: +$139.4/oz of sign-adjusted one-day moves, p = 0.0039. The election is the
falsification test — the biggest macro event in the sample moved gold three standard deviations
and the location premium not at all.

**The metal moved: 511 tonnes, and it is first of seventeen.** Two-way fixed-effects
difference-in-differences on Swiss gold exports by destination, 2015–2026, with sixteen control
corridors. Dec 2024 – Mar 2025: **510.7 t** excess westbound (127.7 t/month), placebo rank 1/17,
median absolute placebo 18.4 t. The treated-only estimate is 495.5 t, so the answer brackets at
496–511 t. Pre-trends average 6.4 t/month. The eastbound leg is ~0 during the surge (rank 40/41)
and 348.4 t over the return window — the internal placebo the design needs.

**Interference is real and quantified.** 57% of the US corridor's rise was offset by falls
elsewhere: India −25.0, China −23.6, Hong Kong −13.2 t/month. Roughly 283 tonnes was diverted
from consumption markets. Reported, not priced — pricing it needs local premium series we don't
have.

**The same shock ran twice.** Dec 2024 – Mar 2025 the arbitrage was executable, so quantity
adjusted and price stayed near cost: mean excess basis $5.44, 511 tonnes moved. Aug 2025 the
duty was already attached to the bar, so quantity could not adjust and price took everything:
mean $18.82, peak $63.60 over carry ($102.20 raw, the widest of the era), ~0 tonnes. That is
the kinked-arbitrage prediction, and it resolves the puzzle the earlier memorandum left open.

## The ledger

| Tier | Item | Low | High |
|---|---|---|---|
| I | Physical relocation, real resources | $29m | $119m |
| I | Physical relocation, all in | $42m | $286m |
| III | Immobilised registered COMEX metal (226 tonne-years) | $214m | $928m |
| | **Resources and opportunity cost** | **$243m** | **$1,214m** |
| II | Hedged short book revaluation, Aug 2025 | $585m | $1,977m |
| II | Hedged short book revaluation, surge window | $182m | $1,232m |
| | **Including transfers** | **$425m** | **$3,191m** |
| | *Duty collected on gold* | | *$0* |

Gross bilateral flow over the episode: 1,381 t. Net position change: **−1.5 t**.

Tiers are kept apart deliberately. Tier I is deadweight. Tier II is a transfer — real to whoever
paid it, not a resource loss to the system — measured against the CFTC's disaggregated
producer/merchant plus swap-dealer short book, which ran at 31–33 Moz, about two-thirds of open
interest. Tier III is forgone lease income on metal held under warrant.

## Things this corrects

- **The August 2025 resolution is pinnable.** EO 14346, 5 Sep 2025, FR 2025-17507.
- **Phantom gold did *not* inflate Switzerland's tariff rate.** On the 2024 vintage it *lowered*
  it, 30.3% → 34.3% ex gold, because the corridor is close to balanced in gold while the rest of
  the relationship is one-sided. The real problem is variance: with gold in the data the formula
  swings 20.3 pp across five adjacent vintages; ex gold, 6.6 pp. **3.1× more sensitive.** Run on
  2024 data Switzerland gets 31%; run on 2026 H1 the identical formula gives the 10% floor.
- **The "threshold is near zero" finding is a weak-identification artefact.** The flow hinge's
  R² varies by 0.047 across the whole grid, so the argmin is uninformative. The better
  estimator — a band of inaction on the basis — also fails: it gives $0.00, $26.00 and $0.75 at
  three sampling frequencies with φ_outside ≈ −1 everywhere, which is white noise, not a band.
  The excess basis built from a 13:30 ET settlement against a 15:00 London auction carries ~$16/oz
  of non-synchronous pricing error per day, and at these frequencies that error *is* the series.
  This is why the ledger uses an assumed unit-cost range with sensitivity carried through.

## Data pulled live at run time

Federal Register API, Census country trade-balance pages, CFTC `publicreporting.cftc.gov`. All
free and unkeyed, all paced. `api.census.gov` now rejects unkeyed requests, hence the balance
pages — same published aggregate. FRED was unreachable from this environment, so nothing depends
on it. Everything else comes from `data/processed/` as built by `src/`.

`code/02_che_all_destinations.py` re-streams the BAZG bulk zips with the country filter removed,
to build a donor pool. It takes several minutes per file and its output is cached in `output/`.
