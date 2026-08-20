# Data sources catalog
### Gold flow deconvolution project — everything you may need to collect

Compiled August 2026. Companion to `RESEARCH_DOSSIER.md`.

Deep links rot; domains don't. Where a path is fragile I've given the domain
plus the search term that finds it.

---

## Start here — the six pulls that matter most

Do these in order. After #3 you have a working paper; the rest is depth.

| # | Source | What it unlocks | Effort |
|---|---|---|---|
| 1 | **CME COMEX daily warehouse stocks** | Closes the 15-month hole; converts the unwind from a line segment to a series | ~2 hrs |
| 2 | **Swiss-Impex monthly by partner** | The core flow series; nothing else has this granularity | ~1 day |
| 3 | **CME settlements + LBMA benchmark** | Builds the EFP proxy; makes the lead-lag testable | ~3 hrs |
| 4 | **LBMA monthly vault holdings** | Closes the sourcing reconciliation (the 339 t residual) | ~2 hrs |
| 5 | **US Census monthly HS 7108** | Export side directly, instead of inferring tonnage from dollar headlines | ~4 hrs |
| 6 | **WGC Goldhub country demand** | The absorption benchmark you test flows against | ~2 hrs |

---

## A. National customs — the primary flow data

**Use these over Comtrade.** They're monthly, they're in mass units, and they
handle re-exports better. Comtrade is a fallback, not a first choice.

### A1. Switzerland — Swiss-Impex ★ critical
- **Gives:** monthly gold trade by partner country, in kg and CHF
- **Coverage:** country-level gold detail from 2012
- **Access:** `gate.bazg.admin.ch/swissimpex/` — Federal Office for Customs and Border Security (BAZG/OFDF)
- **Cost:** free; registration for bulk export
- **Why it matters:** most of the world's gold passes through Swiss refineries, so this is the single best gold flow dataset in existence
- **Gotchas:** clunky query interface, easier to script than to click; no country-level gold detail before 2012; watch the HS 7108 subheading split

### A2. United Kingdom — HMRC uktradeinfo ★ critical
- **Gives:** monthly HS 7108 imports/exports by partner
- **Access:** `uktradeinfo.com` — has a proper REST API (HMRC Trade Data API)
- **Cost:** free
- **Gotchas:** series break January 2021 (Brexit — EU trade collection method changed); confirm whether non-monetary gold is in the headline series or a separate annex

### A3. United States — Census USA Trade Online ★ critical
- **Gives:** monthly HS 7108 by partner, value and quantity
- **Access:** `usatrade.census.gov` (interface) or `api.census.gov/data/timeseries/intltrade` (API)
- **Cost:** free, registration required for the interface
- **Gotchas:** quantity fields can be sparse; cross-check tonnage against value ÷ price; also see USGS monthly Mineral Industry Surveys for a gold-specific cut

### A4. Hong Kong — Census & Statistics Department ★ high value
- **Gives:** monthly gold trade with mainland China; **re-exports reported separately**
- **Access:** `censtatd.gov.hk`
- **Cost:** free
- **Why it matters:** the standard workaround for China's opacity, and one of very few sources that splits re-exports out properly

### A5. India — DGCIS / Ministry of Commerce
- **Gives:** monthly gold imports by origin
- **Access:** `commerce.gov.in` → Tradestat; also RBI bulletins
- **Gotchas:** duty-change-driven spikes (the July 2024 cut from 15% to 6% is a natural experiment worth its own event dummy); large informal inflows via Nepal/Bangladesh/Myanmar are invisible here

### A6. China — GACC
- **Gives:** customs headline data
- **Access:** `customs.gov.cn`
- **Gotchas:** gold import detail historically suppressed. Use the Hong Kong mirror plus Swiss-Impex plus SGE withdrawals instead of relying on this

### A7. Secondary hubs
| Country | Agency | Note |
|---|---|---|
| Singapore | SingStat / Enterprise Singapore | entrepôt, strip re-exports |
| UAE | Federal Competitiveness and Statistics Centre | historically poor gold reporting; see §G2 |
| Turkey | TÜİK, plus Borsa Istanbul import figures | dual role: consumer market *and* transit |

---

## B. Reconciled multilateral trade databases

Only if you extend beyond the five-country core. All carry the gold-specific
hazards listed in `RESEARCH_DOSSIER.md` §6.

| Source | What it adds | Access | Cost |
|---|---|---|---|
| **UN Comtrade** | Bilateral, all HS codes, most countries | `comtradeplus.un.org` | free tier + paid API |
| **BACI (CEPII)** | Mirror reconciliation, CIF→FOB correction, harmonised | `cepii.fr` → databases → BACI | free |
| **Harvard Growth Lab** | Country reliability scores, product-code concordance, validated against IMF BoP | Harvard Dataverse | free |

**Prefer BACI or Growth Lab over raw Comtrade.** Raw mirror gaps for gold run
to two-thirds of the flow in some corridors.

### HS code reference

| Code | Covers | Include? |
|---|---|---|
| 7108.11 | Gold powder | marginal |
| 7108.12 | Unwrought, non-monetary | **yes — core** |
| 7108.13 | Semi-manufactured, non-monetary | **yes — core** |
| 7108.20 | **Monetary gold** | excluded from merchandise trade by BPM6; handle separately |
| 7112 | Precious metal waste and scrap | yes if modelling recycling |
| 7113 | Jewellery of precious metal | only with fineness assumptions (gross weight incl. stones) |
| 7118 | Coin | yes for retail investment flows |
| 2616.90 | Gold ores and concentrates | yes for producer countries (doré routing) |

---

## C. Exchange and vault data

### C1. CME COMEX daily warehouse stocks ★ do this first
- **Gives:** daily registered and eligible gold by depository
- **Access:** `cmegroup.com` → Market Data → Delivery Reports → Metals Daily Warehouse Stocks
- **Cost:** free
- **Note:** keep registered and eligible **separate**. Reclassification between them moves the headline without any metal moving — that's a phantom signal in its own right and worth a paragraph

### C2. LBMA monthly vault holdings ★ high value
- **Gives:** London vault totals, monthly, from July 2016; Bank of England reported separately
- **Access:** `lbma.org.uk` → data
- **Cost:** free
- **Note:** three-month publication lag

### C3. Bank of England vault disclosure
- **Access:** `bankofengland.co.uk` — separate monthly series
- **Note:** BoE serves central bank and ETF custody, so it behaves differently from commercial vaults. The WGC's logistics-vs-scarcity argument turns on this

### C4. Shanghai Gold Exchange
- **Gives:** weekly/monthly withdrawal data — the chokepoint that makes China tractable
- **Access:** `en.sge.com.cn`; the fuller data is Chinese-language
- **Gotchas:** withdrawals ≠ consumer demand. Apply a haircut for round-tripping and recycling recirculation (practitioners use ~20%). Read the WGC's *Understanding China's Gold Market* (2014) for the sceptical case before using this

### C5. Others
SHFE inventories; TOCOM; Dubai Gold & Commodities Exchange (DGCX). Only if
you extend the country set.

---

## D. Price, basis and rates

### D1. Free
| Series | Source | Note |
|---|---|---|
| LBMA Gold Price AM/PM | `lbma.org.uk`, ICE Benchmark Administration | full history free |
| COMEX daily settlements | `cmegroup.com` | all contract months |
| **CME Spot Spreads** | `cmegroup.com` | exchange-listed futures-vs-OTC basis — check open interest before relying on it |
| SOFR | FRED (`fred.stlouisfed.org`, series `SOFR`) | for the carry calculation |
| USD rates, storage proxies | FRED | |

### D2. Bloomberg
| Purpose | Ticker |
|---|---|
| COMEX front month | `GC1 Comdty` |
| COMEX most-active | `GCA Comdty` |
| London spot | `XAU Curncy` |
| LBMA PM benchmark | `GOLDLNPM Index` |
| True dealer EFP | contributed pages (e.g. Morgan Stanley Gold EFP Bid) — **entitlement-gated, firm-specific** |

**Finding your EFP page:** `HELP HELP` (F1 twice) → analytics desk. They can
see your entitlements and will answer in minutes. Faster than hunting.
Fallbacks: `CTRB <GO>` contributor directory, `ALLQ <GO>`, `MTL <GO>`.

**Building the proxy:** `CIX <GO>` for a quick chartable synthetic; `BDH` into
Excel/Python for the paper, so you control roll convention and timestamps.

### D3. Lease rates
- GOFO was **discontinued January 2015** — rates are now implied, not quoted
- Sources: LBMA forward curves; Bloomberg implied lease; dealer quotes via JBMA/Ikemizu commentary
- **Gotcha:** documented gap between implied (from futures) and actual dealer-quoted rates, sometimes ~2×. That gap is informative rather than an error — it's the location-risk contamination showing up

---

## E. Supply, demand and stock benchmarks

### E1. World Gold Council Goldhub ★ critical
- **Gives:** country consumer demand (quarterly, 2010–), ETF holdings (monthly), central bank reserves (monthly, ~100 countries), above-ground stock series (2010–), full supply/demand balance
- **Access:** `gold.org/goldhub` — free with registration
- **Gotchas:** country demand starts 2010, not earlier; two-month lag on reserves; underlying data is Metals Focus, so it inherits their methodology

### E2. IMF International Financial Statistics
- **Gives:** official gold reserves by country, monthly — the source WGC repackages
- **Access:** `data.imf.org`
- **Note:** use this for the monetary gold term that trade data omits by construction

### E3. USGS ★ free and deep
- **Minerals Yearbook** — annual gold production and refinery data by country
- **Data Series 140** (historical statistics for mineral commodities) — production by country back to ~1900
- **Mineral Commodity Summaries** — annual headline
- **Monthly Mineral Industry Surveys** — gold-specific US detail
- **Access:** `usgs.gov` → National Minerals Information Center

### E4. British Geological Survey
- **World Mineral Statistics** — production back to 1913
- **Access:** `bgs.ac.uk`

### E5. Commercial
| Source | What | Rough cost |
|---|---|---|
| **Nick Laird / goldchartsrus.com** | Decades of normalised customs series; **underlying data purchasable, not just charts** | ~$180/yr |
| Metals Focus *Gold Focus* | Granular country supply/demand | four figures |
| GFMS *Gold Survey* back issues (Refinitiv/LSEG) | Pre-2010 country demand | four figures |
| CPM Group *Gold Yearbook* | Alternative estimates | four figures |

Laird is the highest return per dollar here by a wide margin. Email
`nick@goldchartsrus.com` and ask what country-level cumulative series he holds
and in what format *before* subscribing — the catalogue isn't well indexed.

---

## F. Event dates for the dummies

Get exact dates from primary sources, not news summaries.

| Event | Approx date | Primary source |
|---|---|---|
| US election | 5 Nov 2024 | — |
| EFP spread opens >$50 | mid-Dec 2024 | your own constructed series |
| Tariff exemption for gold | Apr 2025 | Federal Register; USTR |
| CBP ruling: 1kg/100oz bars tariffable | 31 Jul / 8 Aug 2025 | **CBP rulings database (CROSS)** |
| White House clarification / EO | Aug 2025 | Federal Register; whitehouse.gov |
| India import duty cut 15%→6% | Jul 2024 | CBIC notification |

**CBP CROSS** (`rulings.cbp.gov`) is the authoritative source for the bar
classification ruling and is free-text searchable. Worth citing directly
rather than via press coverage.

---

## G. Context, validation and the sceptical literature

### G1. Methodology
- Müller, Hilty, Widmer et al., *Modeling Metal Stocks and Flows: A Review of Dynamic MFA Methods*, ES&T 2014 — design checklist
- Rostek & Loibl, zinc multiregional trade-linked DMFA, JIE 2025 — cleanest template
- Liu et al., China gold DMFA 2001–2020, *Resources Policy* 2023 — direct gold precedent
- YSTAFDB (*Scientific Data* 2019) — Yale stocks and flows database
- IMF, *The Structure and Operation of the World Gold Market* (1993) — early-90s regional decomposition

### G2. Trade data quality / informal flows
- **SWISSAID** reports on undeclared African gold — `swissaid.ch`. Documented 2,596 t into UAE from Africa 2012–22 with no matching export declaration
- **UNCTAD** trade discrepancy work — South African gold export gaps of $78.2bn (67% of total)
- Use these to bound how much of the residual is measurement failure vs. real relocation

### G3. The contested London-scarcity question
Collect both sides so the framework can adjudicate rather than take a position:
- WGC commentary (logistics, not shortage; BoE operates differently from commercial vaults)
- Metals Focus / FT reporting on lease rate spikes
- Nieuwenhuijs / BullionStar / Jensen material on free float exhaustion

### G4. Policy contamination evidence
- **Atlanta Fed GDPNow** — `atlantafed.org`, vintage estimates downloadable. Needed to document the nowcast distortion
- Swiss Federal Council / SECO statements on the tariff calculation
- Le Temps and Swiss press coverage of the 2024-data basis

---

## H. Practical notes

**Registration required:** Swiss-Impex (bulk export), USA Trade Online, WGC
Goldhub, Comtrade (API key).

**Has a real API:** HMRC uktradeinfo, US Census, Comtrade, FRED. Everything
else is download-and-parse.

**Rate limits:** Comtrade free tier is restrictive enough to matter if you're
pulling many country-years; budget for the paid key or use BACI instead.

**Units discipline:** decide troy ounces or tonnes on day one and convert at
the boundary. 1 tonne = 32,150.7 troy oz. Mixed units are the most common
source of silent errors in this literature.

**Frequency discipline:** monthly throughout. The entire phenomenon lives at
monthly frequency; annual aggregation erases it.

**Provenance discipline:** keep a `quality` column separating directly-reported
figures from ones derived out of stated aggregates, as in `gold_raw_data.csv`.
When aggregates get revised, you need to know which cells move.

---

## I. What you cannot get, at any price

Worth stating explicitly in the paper's limitations section:

- **Beneficial ownership of vaulted metal.** LBMA and COMEX publish location, never owner. The territorial-vs-ownership choice is unresolvable, not merely unresolved
- **Re-warranting volumes.** Metal already inside the US reclassified as COMEX-eligible generates no trade record and no public disclosure. This is the asymmetry that breaks any single correction factor
- **True dealer EFP without a terminal.** CME Spot Spreads is the closest free substitute
- **Country-level recycling.** Global figures exist; country splits are estimates with methodology that isn't published
- **ASGM production.** ~20% of mine supply, largely unrecorded; 15 African producing countries publish nothing at all
