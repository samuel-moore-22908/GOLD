# Deconvolving gold trade flows
### Separating financial relocation from real absorption, 2019–2026

Master working dossier. Compiled August 2026. Companion to `FINDINGS.md`
(raw analysis notes) and the data files listed at the end.

---

## 1. The question

When gold crosses a border, customs records a trade. But gold crosses borders
for two unrelated reasons: someone will *use or hold* it, or someone is
*moving it between vaults*. Trade statistics cannot distinguish these. At
roughly $150m per tonne, a few hundred tonnes of vault shuffling shows up as
tens of billions of dollars of apparent commerce.

**Objective:** build a defensible filter that separates the two, using the
2024–26 tariff episode as a natural experiment.

### Use a three-way taxonomy, not a binary

"Noise vs. legitimate" invites pushback because central bank buying is
neither. Use instead:

| Category | Definition | Examples |
|---|---|---|
| **Absorption** | Metal permanently leaves the tradeable float | Jewellery, retail bar/coin, industrial use, CB reserves |
| **Relocation** | Metal moves between financial vaults, same ultimate owner | LBMA ↔ COMEX ↔ ETF |
| **Transformation** | Form or location changes, no ownership change | 400 oz → 100 oz recasting in Switzerland |

Relocation and transformation are the "noise." The distinction matters because
transformation *doubles* the trade footprint of a single relocation.

---

## 2. Scope decisions (and what was ruled out)

### Ruled out: 20-country dynamic MFA

Gold's stock-to-flow ratio is ~60 (220,700 t above ground vs ~3,600 t/yr mine
production). Consequences:

- **Inflow-driven stock modelling fails.** You'd need inflow history back to
  the 19th century. Pick a 2010 base and ~80% of your answer is the base
  assumption; the flows barely move it.
- **Jewellery has no lifetime distribution.** It hibernates for decades and
  returns on price/liquidity shocks, not wear-out. A Weibull outflow function
  produces confidently wrong scrap series.
- **No published country-level cross-section of total stock exists for any
  year.** The base is constructed, not retrieved.

Effort estimate was 9–15 months. Wrong project for a short paper.

### Base-year anchors that do exist (kept for reference)

| Anchor | Value | Source |
|---|---|---|
| China private stock, 1994 | 2,500 t | Precious Metals Insights |
| India household stock, ~2016 | 23,500 t (incl. ~4,000 t temples) | WGC India report 2017 |
| India, cumulative, mid-2025 | 34,600 t | Morgan Stanley |
| China total, ~2023 | ~29,700 t | Nieuwenhuijs; Laird independently ~28,911 t |
| Global regional, early 1990s | regional split | IMF (1993) |

### Prior work worth knowing

- **Nieuwenhuijs / Jansen** — China private stock = 2,500 t (1994) + mine +
  non-monetary imports − pre-2007 PBoC domestic purchases. Works *because
  China has a chokepoint* (SGE) and bans export. Does not generalise.
- **Nick Laird (goldchartsrus.com)** — decades of normalised customs series.
  ~$180/yr, and **the underlying data is purchasable, not just the charts.**
  Probably the highest-return few hundred dollars available.
- **Industrial ecology MFA literature** — Rostek & Loibl (zinc, JIE 2025) is
  the cleanest trade-linked multiregional template; Liu et al. (*Resources
  Policy* 2023) is the direct gold precedent for China 2001–20.

### Adopted scope

Five countries — **US, UK, Switzerland** (the arbitrage triangle) plus
**China, India** (absorption sinks). Monthly, 2019–2026. Turkey, UAE, Hong
Kong, Singapore to a robustness appendix if time allows.

---

## 3. What happened: the 2024–26 arc

| Date | Event | Metal response |
|---|---|---|
| Nov 2024 | Election, tariff threats | Premium opens NY vs London |
| Dec 2024 | Spread >$50/oz | Swiss→US jumps to 64 t |
| Jan 2025 | Spread peaks ~$64/oz | **192.9 t** — record since 2012 |
| Apr 2025 | Gold exempted | Reverses; Swiss *imports* from US hit record 63 t |
| Aug 2025 | CBP rules 1kg bars tariffable | Spread >$100; Swiss→US collapses to 0.3 t |
| Early 2026 | The unwind | Gold becomes top US export item, 3 months running |

Swiss gold exports to the US, tonnes:

| Month | t | Month | t |
|---|---|---|---|
| Nov 2024 | 5.8 | May 2025 | 14.0 |
| Dec 2024 | 64.2 | Jun 2025 | 0.3 |
| Jan 2025 | 192.9 | Jul 2025 | 51.0 |
| Feb 2025 | 152.8 | Aug 2025 | 0.3 |
| Mar 2025 | 103.3 | Nov 2025 | 0.2 |
| Apr 2025 | 12.7 | Dec 2025 | 5.8 |

Sep–Oct 2025 unavailable. Feb and May 2025 are residuals backed out of stated
quarterly/half-year totals.

---

## 4. Results

### Headline decomposition

| Measure | Value |
|---|---|
| COMEX vault build, Nov 2024 → Apr 2025 | **871 t** |
| Plausible US absorption over window | 48 t |
| **Relocation share** | **94.5%** |
| Years of US retail coin/bar demand held at peak | 12.2 |
| COMEX drain, Apr 2025 → Jul 2026 | 675 t |
| Recorded trade if fully round-tripped (4 legs) | ~3,480 t |
| — as multiple of 2025 world gold supply | 0.70× |

Absorption bound uses ~115 t/yr typical US physical coin and bar consumption
(Norman). There is no consumption story that explains a 12-year inventory.

### The unexpected finding: a sourcing gap

Switzerland and London together do **not** account for the COMEX build.

| Window | COMEX build | London drawdown | Swiss→US | Residual |
|---|---|---|---|---|
| Election → 29 Jan 2025 | 393 t | 181 t (46%) | 263 t (67%) | — |
| Election → 4 Apr 2025 peak | 871 t | — | 532 t (61%) | **339 t (39%)** |

This cuts against the "London is being drained" narrative that dominated
early-2025 coverage. Candidate residual sources: direct UK→US shipments of
conforming bars, non-Swiss refiners, US domestic output, and — critically —
**existing US private vault stock re-warranted as COMEX-eligible.**

> **That last channel records no cross-border trade at all.** Trade data
> overstates relocation in some directions and misses it entirely in others.
> Any correction factor must be asymmetric. This is the most important
> methodological consequence in the whole project.

### Policy contamination (the publishable hook)

Swiss gold exports to the US, by value:

| Period | CHF bn |
|---|---|
| H1 2024 | 1.7 |
| H1 2025 | 39.0 (**23×**) |
| — of which Q1 | 37.6 |
| Q2 2025 (post-exemption) | 1.6 |

All *non-gold* Swiss exports to the US, full-year 2025: CHF 54.7 bn. Six
months of bullion-in-transit equalled 71% of a year of real commerce. The 39%
Swiss tariff was reportedly calibrated on 2024 deficit data — a year Swiss
officials called atypical precisely because of gold. The same flows distorted
the Atlanta Fed's GDPNow model.

### Where I was wrong

Predicted that coefficient of variation >1.5 would flag a relocation corridor.
It failed:

| Corridor | CV | Max/min | Reading |
|---|---|---|---|
| United States | 1.31 ❌ | **964×** | relocation |
| United Kingdom | 0.87 | 53× | mixed transit |
| India | 0.58 | 4.2× | consumption |

Near-zero months drag the mean down and compress CV. Max/min separates
cleanly. Better still, untested: correlation with EFP spread vs correlation
with local-currency gold price.

---

## 5. The EFP spread — core methodology

### What it is

Exchange for Physical: a privately negotiated swap of a COMEX futures position
for an equivalent London OTC position at an agreed differential, under CME
Rule 538. Dealers quote it as the **price of relocating your exposure** —
which is why it leads physical relocation.

### The four layers inside `GC1 Comdty − XAU Curncy`

| Layer | Difference | Normal state |
|---|---|---|
| **Time** | future delivery vs now | always present, scales with rates |
| **Place** | New York vault vs London vault | zero unless location risk |
| **Form** | 100 oz warrants vs 400 oz Good Delivery | zero unless refining jams |
| **Trust** | exchange warrant vs unallocated claim | zero unless counterparty doubt |

Arbitrage enforces the top three to ~zero in calm markets. That arbitrage is
what makes London gold and New York gold the same asset. When it severs, the
prices are free to diverge.

### Trap: the roll sawtooth

COMEX gold active months are Feb/Apr/Jun/Aug/Oct/Dec, so `GC1` time-to-delivery
cycles from ~2 months to zero. At 4.5% financing and $4,400 gold:

| Days to delivery | Carry |
|---|---|
| ~60 | ~$33/oz |
| ~30 | ~$16/oz |
| ~0 | ~$0/oz |

**A $33 sawtooth driven purely by the delivery calendar** — same order as the
January 2025 dislocation. Regressing on raw dollar spread partly fits the
COMEX calendar.

### Fix: work in implied rates

```
implied_rate = (GC1 / XAU − 1) × 365 / days_to_delivery
dislocation  = implied_rate − (SOFR + storage_rate)
```

Kills the sawtooth, makes 2020 comparable to 2025 across rate regimes. Note
the implied rate is closely related to the gold lease rate — a basis below
full carry implies positive lease, i.e. physical scarcity. When implied and
dealer-quoted lease rates diverge, that gap *is* the location contamination.

### Specification: the relationship is kinked, not linear

Arbitrage only triggers above all-in transfer cost (freight, insurance,
recasting, transit financing). Below, nothing moves. Use a hinge:

```
flow ~ β · max(0, EFP − carry − transfer_cost)
```

**Estimate the kink rather than assuming it.** Its value is itself publishable
— nobody has cleanly estimated the transatlantic gold transfer cost.

### Sign is directional

Above carry → NY rich → metal flows west. Below carry → NY cheap → metal flows
east. Negative EFP alongside CME vault withdrawals marked the Oct 2025
normalisation and the 2026 unwind. Specify the model to handle both signs.

### The spread as market-implied tariff probability

When arbitrage severs, the spread ≈ (probability × tariff cost) + transfer
cost. Inverted on 31 Jan 2025 (spread $64, London spot $2,798):

| Assumed tariff | Cost/oz if it lands | Implied probability |
|---|---|---|
| 10% | $280 | ~23% |
| 25% | $700 | ~9% |
| 39% | $1,091 | ~6% |

A policy expectation extracted from a commodity basis, with a natural
validation event at the April exemption. Cross-checks against reporting that
banks acted because even 5% probability was unacceptable.

### Episode comparison

| Episode | Peak spread | Trigger |
|---|---|---|
| Normal carry (zero-rate era) | $1–2/oz | — |
| Normal carry (2025, 4–5%) | $10–20/oz | — |
| Mar 2020 | ~$70–80/oz | COVID: refineries shut, passenger freight grounded |
| Jan 2025 | $64/oz | Tariff anticipation |
| Aug 2025 | >$100/oz | CBP bar reclassification |

Aug 2025 was widest but produced the *smallest* flow response — everyone
expected reversal within days. Do not read magnitude as intensity.

### Lease rates: the confirming variable

| Date | 1-month gold lease |
|---|---|
| 2 Jan 2025 | 0.08% |
| 20 Jan 2025 | 3.25% |
| 3 Feb 2025 | 4.5% |
| Jan 2025 peak | ~5% (WGC); overnight to 12% (Metals Focus/FT) |
| Late Feb 2025 | ~1% |

Distinguishes "NY is bid" from "London is actually short." Caveats: GOFO
discontinued 2015 so rates are implied not quoted; WGC argues BoE queues are
logistics not scarcity. **The framework can adjudicate this rather than take
a side** — that's more valuable than joining the argument.

### Silver leads gold

Smaller market, thinner float, dislocates first. Oct 2025: silver lease rates
~35–39% (vs normal <1%) after London free float fell to ~136 Moz — under a
third of one day's turnover. Silver EFP went from a 25¢ historic average to
$1.10, then negative as metal flew back. Cheap robustness section.

---

## 6. Data sources

| Series | Source | Cost |
|---|---|---|
| Swiss gold trade by partner, monthly, kg | Swiss-Impex (Federal Office for Customs) | free |
| UK gold trade, HS 7108 | HMRC uktradeinfo | free |
| US gold trade | US Census USA Trade Online; USGS monthly | free |
| COMEX warehouse stocks, daily | CME (registered + eligible separately) | free |
| London vault holdings, monthly 2016– | LBMA | free |
| Country demand, quarterly 2010– | WGC Goldhub | free (registration) |
| ETF holdings, CB reserves, monthly | WGC Goldhub / IMF IFS | free |
| COMEX settlement | `GC1 Comdty` / `GCA Comdty` | Bloomberg |
| London spot | `XAU Curncy` | Bloomberg |
| LBMA PM benchmark | `GOLDLNPM Index` | Bloomberg |
| True dealer EFP | contributed pages (e.g. Morgan Stanley Gold EFP Bid) | entitlement-gated |
| Exchange-listed basis | CME Spot Spreads on COMEX | free settlements |
| Normalised historical customs | Nick Laird / goldchartsrus | ~$180/yr |

**Bloomberg notes.** No canonical public EFP ticker — it's contributed dealer
data, firm-specific entitlements. Fastest route to yours is `HELP HELP` (F1
twice) to the analytics desk. `CIX <GO>` builds a synthetic
`GC1 Comdty − XAU Curncy` as a chartable ticker; for the paper use `BDH` into
Excel/Python so you control roll convention and timestamp alignment.

**Timing caveat.** LBMA PM fixes 3pm London; COMEX settles 1:30pm ET — ~90 min
mismatch. Noise monthly; not noise daily during a window where the spread
moved $20+ intraday.

**Use monthly national customs, not annual Comtrade.** The whole phenomenon
lives at monthly frequency; annual data erases it.

### Comtrade hazards (if used at all)

- Mirror discrepancies are enormous — UNCTAD found South African gold export
  gaps of $78.2bn, 67% of total.
- Monetary gold excluded by BPM6 convention; CB flows must be added from IMF IFS.
- Net weight fields incomplete; deriving tonnage from value ÷ price adds error.
- HS 7108 excludes ores/concentrates (2616) and jewellery (7113).
- Re-exports are included in exports — fatal for CH, UK, HK, UAE, SG, TR.
- Prefer reconciled builds: BACI (CEPII) or Harvard Growth Lab.

---

## 7. Open problems

1. **The 15-month COMEX hole** (Apr 2025 → Jul 2026). The unwind is currently
   a straight line between two points. CME daily warehouse reports close this
   in an afternoon. **Highest value per hour of anything on this list.**
2. **Daily EFP series** — makes the lead-lag testable rather than illustrative.
3. **The asymmetric correction factor.** Re-warranting records no trade;
   round-tripping records four legs. Net direction unknown. Unsolved.
4. **Identifying the "trust" layer.** Probably impossible to separate cleanly
   from location risk. Acknowledge rather than pretend the residual is all
   location.
5. **Swiss-Impex full panel** 2012– × ~40 destinations to run the corridor
   classifier properly.
6. **ETF vaulting location.** US 2025 ETF demand was 437 t (holdings 2,019 t),
   but ETF metal is mostly vaulted in *London*, not COMEX. Verify before
   claiming it doesn't justify the COMEX build.

---

## 8. Known weaknesses

- Sandbox network was restricted to package registries, so no direct pulls
  from Swiss-Impex, CME, LBMA or HMRC. Everything assembled from figures
  quoted in public reporting, with a provenance column separating `reported`
  from `derived`.
- Feb and May 2025 Swiss→US figures are residuals from stated aggregates. If
  those aggregates are revised, the months move.
- Corridor classifier runs on n = 3–12 observations. Illustrative only.
- Monetary gold absent from all trade data here by construction.

---

## 9. Files

| File | Contents |
|---|---|
| `RESEARCH_DOSSIER.md` | This document |
| `DATA_SOURCES.md` | Full data source catalog: access, cost, coverage, gotchas |
| `FINDINGS.md` | Raw analysis notes from the first pass |
| `gold_raw_data.csv` | Monthly observations, long format, provenance-flagged |
| `gold_context_data.csv` | Annual/structural: WGC supply-demand, stocks, trade values |
| `gold_monthly_panel.csv` | Wide monthly panel, Nov 2024– |
| `headline_decomposition.csv` | The relocation/absorption table |
| `corridor_classifier.csv` | CV and max/min by destination |
| `analysis.py` | Round-trip accounting, phantom multiplier, absorption test |
| `analysis2.py` | Sourcing reconciliation, lead-lag, charts |
| `analysis3.py` | Honest-chart rewrite, revised classifier, headline table |
| `gold_flows.png` | Two-panel chart (gaps visible, interpolation dotted) |
