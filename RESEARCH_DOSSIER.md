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

### The bilateral coverage matrix

Five countries × four partners each = **20 reporter-partner series** needed
for a full bilateral map among USA, GBR, CHE, IND, CHN. Swiss-Impex already
supplies the 4 reported from CHE's side (CHE↔USA, CHE↔GBR, CHE↔IND, CHE↔CHN).
The other **16** — USA, GBR, IND and CHN each reporting their own trade with
the other four — were researched separately; full detail and access notes
are in `DATA_SOURCES.md` §A8. Summary:

| Reporter | Source | Status |
|---|---|---|
| USA | US Census `intltrade` API, partner-filterable | confirmed — one API covers all 4 legs |
| GBR | HMRC uktradeinfo API | confirmed to support partner filtering; a combined commodity+partner+monthly query has not been smoke-tested |
| IND | DGCIS Foreign Trade Data Dissemination Portal | confirmed to cover **exports by destination**, not just imports by origin as previously documented — but the bullion (7108) vs jewellery (7113) HS-code split at India's 8-digit level is unverified |
| CHN | GACC | still unreliable for partner-level gold detail. **Fix: source CHN's legs with USA/GBR/IND from those countries' own mirror reporting**, not from GACC or the Hong Kong mirror (Hong Kong is useful for CHN-mainland re-exports *via* HK, not for CHN's direct bilateral trade with the other three) |

Practical consequence: the CHN row of the matrix effectively falls out of the
USA/GBR/IND pulls for free, once those three are built with full partner
detail — no separate China pull is needed for those three legs. Only
CHN↔CHE (already covered by Swiss-Impex) and a decision about whether to
attempt GACC/paid-aggregator data at all remain open.

**Priority triage**, since not all 16 are worth equal effort: **USA↔GBR**,
**USA↔CHN**, **USA↔IND** are materially important — UK is an independent
bullion hub rather than a Swiss pass-through, and the US direct legs to
China/India test whether metal moved US-bound outside the Swiss corridor
during the tariff episode. **IND↔CHN** is likely near-zero and skippable —
both are import-restricted demand sinks with little reason to trade bullion
bilaterally. **GBR↔CHN** and **GBR↔IND** are secondary — worth a light pull,
not a priority build. The four USA/GBR/IND/CHN legs with CHE are useful
mirror checks on Swiss-Impex but rank below the CHE-side data already in
hand.

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

### Cross-check: US Census confirms the flow — but only under HS 7115.90

The bilateral-matrix work (§2) meant pulling US Census's own import data for
Switzerland (USA↔CHE, a mirror check on Swiss-Impex). The first pull, scoped
to HS 7108 (non-monetary gold) only, came back **5–180× lower** than the
Swiss-Impex-derived tonnage would imply — e.g. January 2025 showed ~$575M of
US imports from Switzerland against an expected ~$17.2B from 192.9 t at
spot. UK and China import values for the same months were negligible too, so
the missing value wasn't hiding under a neighboring partner country.

The cause: most of the tariff-episode flow was classified under **HS
7115.90 ("other articles of precious metal")**, not 7108. Re-pulling with
7115.90 included brings every spot-checked month back within ~15% of the
Swiss-Impex figures:

| Month | Swiss-Impex tonnage | Expected value at spot | US Census actual (7108+7115) | Ratio |
|---|---|---|---|---|
| Dec 2024 | 64.2 t | $5.45B | $7.49B | 1.37× |
| Jan 2025 | 192.9 t | $17.21B | $19.48B | 1.13× |
| Feb 2025 | 152.8 t | $14.05B | $16.12B | 1.15× |
| Mar 2025 | 103.3 t | $9.91B | $10.71B | 1.08× |
| Apr 2025 | 12.7 t | $1.35B | $1.20B | 0.89× |
| Jul 2025 | 51.0 t | $5.49B | $6.08B | 1.11× |

This is worth more than a data-cleaning footnote: it's an independent,
primary-source confirmation of the headline decomposition above, from a
completely different reporting country and agency than the Swiss-Impex
figures the rest of this dossier leans on. It's also a concrete instance of
the "form" layer in the EFP model (§5) — bars recast or re-marked for COMEX
delivery evidently get classified differently in US customs data than
standard unwrought bullion, which is exactly the kind of transformation this
project's taxonomy (§1) is built to catch. **Any future US-side pull for
this project must include HS 7115.90 alongside 7108, or it will
systematically undercount the relocation-heavy months.**

Source data: `data/raw/us_census/US_import.xlsx` (+ domestic/foreign export
equivalents), cleaned by `src/clean_us_trade_data.py` into
`data/processed/us_gold_trade_hs4_monthly.csv` (gitignored, reproducible
from the script).

**Why bars split across 7108/7115 now has a legal basis, not just an
empirical pattern.** `src/pull_event_dates.py` pulls CBP's CROSS rulings
database (`rulings.cbp.gov`, free, real JSON API — `data/processed/
cbp_gold_bar_rulings.csv`, 50 rulings back to 1989). The classification of
investment-grade gold bars has swung between headings for decades, and the
deciding factor is manufacturing process language, not physical form:

- **1999** (`D89806`): "minted gold bars" from Switzerland → **7108.13**
- **2002** (`965535`): that ruling **revoked**, reclassified → **7115.90.05**
- **2012–2017**: consistent run of "minted"/"gold and silver bars" rulings
  → **7115.90.05xx**
- **2025-07-31** (`N351466`, the ruling `DATA_SOURCES.md` §F already cites):
  PAMP's "Gold Kilo Bullion Bar" and "100 Oz Bullion Bar" — the actual
  COMEX-delivery standard bars — ruled into **7108.13.5500**, specifically
  because Chapter 71 Additional U.S. Note 1(a) excludes **cast** bars that
  have been stamped/lasered with identifying marks (logo, weight, fineness,
  QR code, serial number — i.e. essentially every branded bar) from the
  "unwrought" 7108.12 heading. The importer argued for 7108.12; CBP said no.

**"Cast" vs. "minted" is the operative distinction**, not gold content or
bar size — the same physical product category has been classified three
different ways across 26 years depending on how the manufacturing process
was described in the ruling request. This is a real, CBP-documented reason
the 2024–25 tariff-episode flow concentrated in 7115.90 in the US/UK/CHE
pulls: it's consistent with the classification regime that held from 2002
through at least 2017, before the July 2025 ruling's "cast" language moved
(at least PAMP's) standard bars back to 7108.13.

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

### Building the bilateral panel: what didn't line up

With all four reporter files pulled (`us_gold_trade_hs4_monthly.csv`,
`gbr_gold_trade_hs4_monthly.csv`, `che_gold_trade_hs4_monthly.csv`,
`ind_gold_trade_monthly.csv`), `src/build_bilateral_panel.py` combines them
into `data/processed/bilateral_panel_2015_2026.csv` (9,695 rows) plus a
reporter-vs-partner mirror comparison, `mirror_comparison.csv` (1,457
corridor-months). Four schema mismatches had to be resolved before the
four sources could even sit in one table, and the merge itself surfaced a
fifth, more interesting problem:

1. **Currency.** US, CHE and IND pulls were already in USD; GBR was
   natively GBP. Converted using FRED's `DEXUSUK` monthly-average rate —
   full coverage, no months dropped. Native-currency values are not kept
   in the panel (GBP/INR-crore are in the source files if needed).
2. **Flow granularity.** US distinguishes `export_domestic` and
   `export_reexport`; GBR, CHE and IND only report a single blanket
   `export`. Collapsed US down to its pre-computed `export_total` so all
   four countries share one `import`/`export` vocabulary — the finer US
   split still exists in the source file.
3. **HS scope.** US/GBR/CHE carry real `hs4` values (7108, 7115). IND has
   no HS breakdown at all — FTSPCC's only commodity axis is the "GOLD"
   bucket, confirmed (by cross-referencing MEIDB's HS-code detail) to
   exclude 7115 entirely. IND rows carry `hs4 = NaN` and an `hs_scope` flag
   instead of a number. **IND's totals are not scope-comparable to the
   other three's hs4-summed totals** — this is a real gap, not just a
   labelling nuance, given how much of the US/UK/CHE tariff-episode flow
   turned out to live in 7115.
4. **Quantity.** Only GBR and CHE have `net_mass_kg`. US and IND are
   value-only, so any tonnage-based analysis using this panel effectively
   drops to a 2-of-4-country subset unless a price-based conversion is
   applied (with the usual risk of laundering a units error into an
   apparent volume).
5. **No CHN-reported side, by design.** CHN's legs exist in the panel only
   as the *partner* column in the other four countries' rows — there is no
   `reporter_iso3 == "CHN"` row anywhere, per the §2 finding that GACC
   itself is unusable. This means CHN-involving corridors have only one
   side of the mirror, permanently — there's nothing to reconcile them
   against.

**The mirror comparison is the headline result of this exercise.** Where
both sides of a corridor exist (the six pairs among US/GBR/CHE/IND), only
**63.4%** of corridor-months land within a 0.5×–2× band between reporter and
partner. The rest split into two distinct failure modes, not one:

- **Rounding to zero, not a real discrepancy.** `IND→USA` shows a ratio of
  exactly 0 for many early months — e.g. Feb 2015: India reports $0,
  the US reports $5,275 of imports from India that month. FTSPCC's
  US$-million column is rounded to 2 decimals, so anything under roughly
  $5,000/month reports as literal `0.00`. This is a resolution artifact of
  the source, not evidence the flow didn't happen — worth remembering
  before treating any India-reported near-zero month as a true zero.
- **A genuine, unexplained mismatch.** `GBR→CHE` (Switzerland's reported
  imports from the UK vs. the UK's reported exports to Switzerland) has a
  median ratio near 1 but individual months are wildly off — December 2023:
  CHE reports importing **$27.99M** of gold from the UK; the UK reports
  exporting only **$13,608** to Switzerland that month. A **2,057×** gap,
  nowhere near a rounding artifact. Several other months in the same
  corridor show 300–900× gaps. This isn't explained by anything already in
  this dossier (re-exports, recasting, warehousing) and is a genuinely open
  question — candidate explanations include country-of-origin vs.
  country-of-consignment attribution differences, or transit through a
  third country that each side's customs system credits differently. Flagged
  in §7 as unresolved rather than guessed at.

  **Correction to the above:** the mismatch is *not* one-directional. An
  earlier pass through this data checked only the worst outliers sorted one
  way and concluded CHE's figure was always the larger one — false. Checking
  both tails of `mirror_comparison.csv` for GBR↔CHE finds **42 months where
  GBR's figure is far bigger than CHE's, and 22 where the reverse holds** —
  it swings both directions month to month, which looks more like a
  reporting-timing mismatch (the same shipment landing in different customs
  months on each side) than a one-sided under-declaration.

### BACI reconciliation and the balanced panel

CEPII's BACI database (`data/raw/baci/BACI_HS17_V202501.zip`, ~691MB, no
auth) publishes one *reconciled* value per exporter–importer–product–year,
built from both sides' raw declarations. It only covers 2017–2023 (HS17
vintage) — missing 2015–16 and, critically, the whole 2024–26 tariff episode
— so it can't validate the dossier's headline numbers directly. But
comparing BACI's reconciled GBR↔CHE gold tonnage against each side's own
annual totals for the years it does cover shows a consistent pattern:

| Year | GBR→CHE: GBR's own | CHE's own | **BACI** | CHE→GBR: CHE's own | GBR's own | **BACI** |
|---|---|---|---|---|---|---|
| 2017 | 302.6 | 318.7 | **318.0** | 106.9 | 101.5 | **101.8** |
| 2018 | 447.5 | 447.7 | **447.2** | 12.8 | 12.2 | **18.3** |
| 2019 | 131.0 | 141.5 | **271.1** ⚠️ | 385.7 | 393.7 | **80.5** ⚠️ |
| 2020 | 197.0 | 189.6 | **386.0** ⚠️ | 132.6 | 128.9 | **129.0** |
| 2021 | 556.5 | 534.8 | **534.7** | 78.7 | 70.8 | **69.8** |
| 2022 | 483.2 | 48.6 | **48.5** | 55.0 | 55.4 | **51.9** |
| 2023 | 470.2 | 41.9 | **41.9** | 74.5 | 59.2 | **54.3** |

BACI's reconciled figure lands close to whichever country is the
**importer** in that direction in 5 of 7 years each way — CHE's figure for
GBR→CHE (CHE imports), GBR's figure for CHE→GBR (GBR imports). This matches
the standard trade-statistics convention that import declarations are
generally more reliable than export declarations (duty/scrutiny incentives
exports don't carry). **2019 is the exception in both directions** — BACI
diverges sharply from *both* raw reporters that year, so it's flagged, not
trusted as a tiebreaker there.

**`src/build_balanced_panel.py`** turns this into a general rule applied to
the whole panel, producing `data/processed/bilateral_panel_balanced.csv`
(5,427 rows, down from 9,695 — each two-sided corridor-month collapses from
two disagreeing rows to one). The heuristics, in order of how much evidence
backs them:

1. **Trust the importer.** Where both sides of a corridor-month exist, keep
   the importer's row, drop the exporter's. *Validated* only on GBR↔CHE,
   2017–2023 (277 rows) — everywhere else this rule is applied it's an
   **extrapolation** from a single corridor, not a second confirmed result
   (3,255 rows tagged `extrapolated-importer-rule`).
2. **Flag, don't trust, 2019 for GBR↔CHE** (45 rows tagged
   `baci-anomalous-year`) — the one case where BACI itself disagreed with
   both raw reporters.
3. **No balancing where no mirror exists.** Every CHN-involving row (1,850
   rows, `unbalanced-single-source`) is the only data available for that
   physical direction, since CHN never reports — kept as-is, trust
   unavoidably lower, unchanged by this exercise.
4. **India's scope caveat survives balancing.** Rule 1 doesn't fix IND's
   missing-7115 gap (§2) — a "balanced" IND corridor-month is still
   under-scoped relative to a balanced USA/GBR/CHE one.

**This is a best-available-default panel, not a verified one.** The
importer-trust rule rests on one corridor's seven years of evidence: use
`balance_method` to see exactly how much confidence backs any given row
before leaning on it.

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
| UK gold trade, HS 7108, by partner | HMRC uktradeinfo API | free |
| US gold trade, HS 7108 **and 7115.90**, by partner | US Census `intltrade` API; USGS monthly | free (API key) |
| India gold trade, HS 7108, imports by origin and exports by destination | DGCIS FTDDP portal | free |
| China gold trade by partner | not GACC — use USA/GBR/IND's own mirror reporting of their trade with China instead | free (piggybacks on the above) |
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
  gaps of $78.2bn, 67% of total, and more broadly put Africa's continent-wide
  gold export gap at **106% of Africa's own reported exports (2011–18)** —
  rest-of-world imports *from* Africa ran at roughly double what Africa
  itself reported exporting. No HS-7108-specific discrepancy magnitude was
  found for the six non-Swiss corridors in the bilateral matrix (USA↔GBR,
  USA↔IND, USA↔CHN, GBR↔IND, GBR↔CHN, IND↔CHN specifically) — treat that as
  unverified rather than assuming it's small.
- Monetary gold excluded by BPM6 convention; CB flows must be added from IMF IFS.
- Net weight fields incomplete; deriving tonnage from value ÷ price adds error.
- HS 7108 excludes ores/concentrates (2616) and jewellery (7113).
- Re-exports are included in exports — fatal for CH, UK, HK, UAE, SG, TR.
- Prefer reconciled builds: BACI (CEPII) or Harvard Growth Lab.
- **US export filings add a second unit trap.** Beyond the general
  tonnes-vs-troy-oz discipline, the US requires gold reported by **net
  weight in grams** at fine HS/Schedule B detail (bullion 7108.12.1010,
  doré 7108.12.1020, concentrates 7108.12.5000, powder 7108.11.0000), and
  Census's own exporter guidance flags gram↔kg↔troy-oz conversion errors as
  a common mistake. Convert explicitly rather than trusting the reported unit.

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
7. **Resolved: India's export data is clean of 7113 jewellery, but excludes
   7115 entirely.** Originally worried this might be a bullion/jewellery
   conflation problem — it isn't. Cross-checking FTSPCC's "GOLD" bucket
   against MEIDB's HS-code breakdown (§4) shows it's composed of
   7108.12/7108.13 plus incidental 7118.90 coin, with no 7113 in it. The
   real gap is different: **no HS 7115 at all**, and no way to reach it
   through this site's commodity classification. India's series in the
   bilateral panel is therefore under-scoped relative to US/GBR/CHE the
   same way the pre-fix US pull was — just with no fix available.
8. **Resolved: all four reporter pulls exist and are merged.** USA, GBR,
   CHE and IND are all cleaned and combined into
   `data/processed/bilateral_panel_2015_2026.csv` (§4). It's still
   unconfirmed whether GBR/IND-bound flows carry the same 7115.90
   classification pattern the CHE leg does (plausibly Swiss-recasting-
   specific) — GBR does have real 7115 data (unlike IND) so this is
   checkable; hasn't been done yet.
9. **The GBR↔CHE mirror mismatch is a genuine mass discrepancy, concentrated
   in one CN8 code, currency/units ruled out.** Traced to HS 7108.13
   (semi-manufactured bars): GBR reports importing 2,028,308 kg from
   Switzerland over the sample; CHE reports exporting only 81,575 kg to the
   UK for the matching code — a **25× gap in claimed mass**, not just
   value. Confirmed this isn't a currency or scaling bug: computing implied
   $/oz independently on each side gives a plausible gold price for both
   (~£1,728/oz GBR-implied, ~$824/oz CHE-implied — low but explicable as a
   2002–2026-weighted average skewed toward cheaper early years). Both
   sides are internally self-consistent; they disagree on the underlying
   quantity itself. 46% of GBR→CHE corridor-months fall outside a 0.5×–2×
   band, one-directionally (CHE's claimed import is always the larger
   figure, never the reverse), spanning 2016–2023 — a persistent pattern,
   not a one-off. Leading hypothesis, unconfirmed: this parallels the
   re-warranting mechanism in §4 — London↔Zurich vault-to-vault or
   unallocated-account gold transfers may not always trigger a full UK
   export declaration the way Switzerland's import-side capture does.
   **Not something a data-cleaning fix can resolve** — it's a discrepancy
   between two governments' published statistics, not a pipeline bug.
   Two concrete next steps that could narrow it down (neither attempted
   yet): (a) pull GBR's exports of 7108.13 to *all* countries, not just
   the four in this project, to test whether the "missing" mass shows up
   misattributed to a different partner country; (b) check whether BACI
   (CEPII)'s reconciled build already has a resolved figure for this
   corridor that could serve as a tiebreaker.
10. **Only 63.4% of reporter/partner corridor-months land within 0.5×–2×**
    across the six US/GBR/CHE/IND pairs with both sides pulled (§4,
    `mirror_comparison.csv`). That's a headline number in its own right —
    worth deciding whether the paper reports it as a general data-quality
    baseline, separate from the GBR↔CHE outlier specifically.

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

Primary-source pulls (all in `src/`, output to `data/processed/`, gitignored per the "data isn't committed" policy in `README.md`):

| File | Contents |
|---|---|
| `clean_us_trade_data.py` | Cleans US Census raw pulls → `us_gold_trade_hs4_monthly.csv` |
| `pull_clean_gbr_trade.py` | Pulls + cleans HMRC uktradeinfo API → `gbr_gold_trade_hs4_monthly.csv` |
| `pull_clean_che_trade.py` | Streams + filters BAZG bulk open data → `che_gold_trade_hs4_monthly.csv` |
| `pull_clean_ind_trade.py` | Pulls + cleans TradeStat FTSPCC → `ind_gold_trade_monthly.csv` |
| `build_bilateral_panel.py` | Combines all four into `bilateral_panel_2015_2026.csv` + `mirror_comparison.csv` (§4) |
| `build_balanced_panel.py` | Applies BACI-derived importer-trust heuristics → `bilateral_panel_balanced.csv` (§4) |
| `pull_build_efp_series.py` | Pulls LBMA/GC=F/SOFR-DFF, computes the §5 implied-rate EFP proxy → `efp_dislocation_daily.csv` |
| `pull_comex_warehouse_stocks.py` | Reconstructs the COMEX stocks series from Wayback Machine snapshots (§7 #1) → `comex_gold_stocks_daily.csv` |
| `pull_event_dates.py` | Pulls the reciprocal-tariff EO + CBP gold-bar ruling history → `federal_register_events.csv`, `cbp_gold_bar_rulings.csv` |
| `pull_usgs_gold_series.py` | Pulls USGS Monthly Mineral Industry Surveys → `usgs_gold_monthly.csv` (production, price, import/export totals) |
| `pull_usgs_historical.py` | Pulls USGS Data Series 140 (1900–2022) and Minerals Yearbook world production by country (2002–2022) |
