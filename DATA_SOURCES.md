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
| 5 | **US Census monthly HS 7108, by partner** | Export side directly, and — via the partner filter — the USA↔GBR/IND/CHN legs of the bilateral matrix in one pull | ~4 hrs |
| 6 | **WGC Goldhub country demand** | The absorption benchmark you test flows against | ~2 hrs |
| 7 | **HMRC + DGCIS, by partner** | The GBR and IND legs of the bilateral matrix (§A8) — together with #5, this covers 12 of the 16 non-Swiss flows, since CHN's legs are read off these three rather than pulled separately | ~1 day |

---

## A. National customs — the primary flow data

**Use these over Comtrade.** They're monthly, they're in mass units, and they
handle re-exports better. Comtrade is a fallback, not a first choice.

### A1. Switzerland — BAZG open data ★ critical — confirmed working, better than the interactive portal
- **Gives:** monthly gold trade by partner country, in kg and CHF/EUR/USD
- **Coverage:** confirmed live back to 2002 for the general bulk files (see below); the interactive Swiss-Impex tool's own country-level gold detail starts 2012
- **Access, confirmed working, no auth:** `opendata.swiss` → search "Aussenhandelsstatistik" for BAZG's own products. Two tiers:
  - A gold-only **import** CSV, 2021–, small (`waren-aussenhandel-goldimporte-nach-landern`) — good for a quick check, but import-only.
  - The **general bulk files** — `waren-aussenhandel-nach-tarifnummer-land` — one ~580–690MB zipped CSV each for imports and exports, every tariff code, every country, monthly since 2002. No standalone gold-only *export* product exists, so this is the only way to get Switzerland's export side (the CH→US series this whole project centers on) from open data. `src/pull_clean_che_trade.py` streams both zips directly (never extracts the ~8.5GB CSVs to disk) and filters to HS 7108/7115 for the four bilateral-matrix partners.
- **Cost:** free, no registration, no rate limit encountered (static S3/CloudFront files)
- **The old "clunky query interface" note (Swiss-Impex proper, at `www.swiss-impex.admin.ch`) still applies if you need it** — it's a CloudFront-fronted AWS QuickSight-embedded SPA that 403s a bare `curl` (needs a browser User-Agent to even load), and the actual query/export mechanism wasn't reverse-engineered since the open-data bulk files made it unnecessary.
- **Gotchas:** the domain `gate.bazg.admin.ch` referenced in earlier notes here does not resolve — use `www.swiss-impex.admin.ch` (interactive) or `opendata.swiss` (bulk, recommended) instead. Watch the HS 7108 subheading split; BAZG's own USD conversion is provided directly (`Value_USD` field), no FX math needed.

### A2. United Kingdom — HMRC uktradeinfo ★ critical
- **Gives:** monthly HS 7108 imports/exports by partner
- **Access:** `uktradeinfo.com` — has a proper REST API, documented at `uktradeinfo.com/api-documentation` (OData-style queries against a countries endpoint plus commodity-code filtering)
- **Cost:** free
- **Gotchas:** series break January 2021 (Brexit — EU trade collection method changed); confirm whether non-monetary gold is in the headline series or a separate annex; the docs confirm partner-country and commodity-code filtering separately but a single combined commodity+partner+monthly query has not been smoke-tested — verify with a real pull before relying on it structurally

### A3. United States — Census USA Trade Online ★ critical
- **Gives:** monthly HS 7108 by partner, value and quantity
- **Access:** `usatrade.census.gov` (interface) or `api.census.gov/data/timeseries/intltrade/exports/hs` and `.../imports/hs` (API) — filter on `CTY_CODE`/`CTY_NAME` for partner and `SUMMARY_LVL=DET` to get individual-partner rows rather than an aggregate. One API call set covers all of US↔GBR, US↔IND, US↔CHN, US↔CHE
- **Cost:** free; API key registration is free and lighter-weight than USA Trade Online's interface registration
- **Gotchas:** quantity fields can be sparse; cross-check tonnage against value ÷ price; also see USGS monthly Mineral Industry Surveys for a gold-specific cut. **Unit trap distinct from the general tonnes-vs-oz rule:** US export filings (AES/Schedule B) require gold reported by **net weight in grams** at fine HS detail — bullion `7108.12.1010`, doré `7108.12.1020`, concentrates `7108.12.5000`, powder `7108.11.0000` — and Census's own exporter guidance flags gram↔kg↔troy-oz conversion errors as a common mistake. Convert explicitly per subheading rather than trusting a single reported unit

### A4. Hong Kong — Census & Statistics Department ★ high value
- **Gives:** monthly gold trade with mainland China; **re-exports reported separately**
- **Access:** `censtatd.gov.hk`
- **Cost:** free
- **Why it matters:** the standard workaround for China's opacity, and one of very few sources that splits re-exports out properly

### A5. India — TradeStat FTSPCC (Ministry of Commerce) ★ critical — confirmed working, but scope-limited
- **Gives:** monthly gold exports/imports by partner country — but only via a predefined **"GOLD" commodity bucket** (code `G6`), not a raw HS code. Confirmed by cross-referencing MEIDB's HS-code-level breakdown (§ below) that this bucket = HS 7108.12/7108.13 plus incidental HS 7118.90 (coin) — **it excludes HS 7115 entirely**, with no way to reach it through this site's classification. Not scope-comparable to the US/UK/CHE pulls, which do include 7115.90.
- **Access, confirmed working:** `tradestat.commerce.gov.in/ftspcc/{export,import}_commodity_xcountry_wise_monthly` — "Commodity x Country wise (Monthly)". Despite `wire:model` attributes suggesting a Laravel Livewire app, the form submits as an ordinary POST and returns a server-rendered HTML results table; `src/pull_clean_ind_trade.py` automates this directly (session cookie + CSRF token refreshed per request, one request per country×flow covers the *entire* date range in one shot — no pagination needed).
  - `ftddp.dgciskol.gov.in` (the FTDDP portal referenced in earlier notes here) requires a login (`ng-app="dgcisLogin"`) — not pursued.
  - The site has three other products (**EIDB** = annual, **MEIDB** = monthly but no clean commodity×country cross-tab in one query, **FTPA** = annual rankings/analytics only) — FTSPCC is the only one with both a monthly date range *and* a combined commodity+country filter. MEIDB's "Country-wise Principal commodity wise all HSCode" report is the one place true 8-digit HS detail is reachable, but it only returns a single target month + same-month-prior-year per query, no date range — useful as a one-off cross-check (which is how the 7115 exclusion was confirmed), impractical for a full time series.
- **Cost:** free, no registration, no rate limit encountered
- **Gotchas:** duty-change-driven spikes (the July 2024 cut from 15% to 6% is a natural experiment worth its own event dummy); large informal inflows via Nepal/Bangladesh/Myanmar are invisible here. No quantity/mass field despite the results page labelling itself "UNIT: KGS" — value only (US$ Million and Rs. Crore).

### A6. China — GACC ✗ not a usable direct source
- **Gives:** customs headline data; detailed gold import totals only since ~2017 (1,270 t 2017, 1,506 t 2018), and even those years lack reliable **partner-country** breakdowns
- **Access:** `customs.gov.cn`
- **Cost:** free (for what little is usable)
- **Gotchas:** China treated bullion trade data as close to a state secret for years, and partner-level HS 7108 detail remains unreliable even now. **Do not use Hong Kong Census (A4) as a substitute for CHN's direct bilateral legs with USA, GBR or IND** — Hong Kong is useful specifically for CHN-mainland re-exports routed *through* Hong Kong, not for China's own direct trade with those three countries. **The practical fix: source CHN's legs from the partner's own reporting** — US Census gives CHN↔USA, HMRC gives CHN↔GBR, DGCIS gives CHN↔IND — rather than from China at all. (CHN↔CHE is already covered by Swiss-Impex.) Paid aggregators (Trade Data Monitor, S&P Panjiva, CEIC) claim to offer GACC HS-code data with partner detail, but this hasn't been verified for accuracy or current cost, and the underlying GACC data is the weak link regardless of aggregator

### A7. Secondary hubs
| Country | Agency | Note |
|---|---|---|
| Singapore | SingStat / Enterprise Singapore | entrepôt, strip re-exports |
| UAE | Federal Competitiveness and Statistics Centre | historically poor gold reporting; see §G2 |
| Turkey | TÜİK, plus Borsa Istanbul import figures | dual role: consumer market *and* transit |

### A8. The bilateral coverage matrix (USA, GBR, CHE, IND, CHN) — build complete

Five countries × four partners each = 20 reporter-partner series. All four
pullable sides (USA, GBR, CHE, IND) are done — `src/clean_us_trade_data.py`,
`src/pull_clean_gbr_trade.py`, `src/pull_clean_che_trade.py`,
`src/pull_clean_ind_trade.py` — and `src/build_bilateral_panel.py` combines
them into `data/processed/bilateral_panel_2015_2026.csv`. CHN has no
reported side by design (GACC unusable — see A6); its legs exist only as
the *partner* column in the other four countries' rows.

| Reporting country | Partner legs it covers | Source |
|---|---|---|
| CHE | ↔USA, ↔GBR, ↔IND, ↔CHN | A1 BAZG open data |
| USA | ↔GBR, ↔IND, ↔CHN, ↔CHE | A3 US Census |
| GBR | ↔USA, ↔IND, ↔CHN, ↔CHE | A2 HMRC uktradeinfo |
| IND | ↔USA, ↔GBR, ↔CHN, ↔CHE | A5 TradeStat FTSPCC — **scope caveat: excludes HS 7115** |
| CHN | ↔USA, ↔GBR, ↔IND, ↔CHE | *no direct CHN source* — read off the USA/GBR/IND/CHE rows instead |

**Building the panel required harmonizing four mismatched schemas** —
currency (GBR is natively GBP, converted via FRED's `DEXUSUK`), flow
granularity (US splits domestic/re-export, the other three don't), HS scope
(IND has none at all), and quantity availability (only GBR/CHE have
`net_mass_kg`). Full writeup in `RESEARCH_DOSSIER.md` §4, "Building the
bilateral panel: what didn't line up."

**The mirror-discrepancy question now has a real answer**, in
`data/processed/mirror_comparison.csv`: across the six pairs where both
reporter and partner data exist, only **63.4%** of corridor-months land
within a 0.5×–2× band. Two distinct causes, not one — India rounds small
values to literal `$0` (FTSPCC's US$-million column is 2-decimal, so
anything under ~$5,000/month reports as zero, not evidence of no flow), and
a separate, unexplained mismatch on GBR↔CHE specifically, where individual
months show Switzerland's reported imports from the UK at 300–2,000× the
UK's reported exports to Switzerland. That second one is a genuinely open
question — see `RESEARCH_DOSSIER.md` §7.

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

**BACI access, confirmed working:** direct zip download, no auth —
`www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS17_V202501.zip` (~691MB; one
zip per HS revision — HS17 covers 2017–2023 only, so it won't reach
2015–16 or 2024–26). Inside: one CSV per year (`t,i,j,k,v,q` — year,
exporter code, importer code, HS6 product, **value in thousand USD**,
**quantity in metric tons**), plus `country_codes` and `product_codes`
lookups. Used in `src/build_balanced_panel.py` to derive an
importer-trust reconciliation heuristic for the bilateral panel — see
`RESEARCH_DOSSIER.md` §4.

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
| GBP/USD | FRED, series `DEXUSUK` — CSV pull confirmed working, no key | used to convert the GBR trade pull to USD in `build_bilateral_panel.py`; full daily coverage 2015–2026, aggregated to monthly average |
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
- **UNCTAD** trade discrepancy work — South African gold export gaps of $78.2bn (67% of total); more broadly, Africa-wide gold export gaps ran at **106% of Africa's own reported exports (2011–18)** — rest-of-world imports *from* Africa were roughly double what Africa itself reported exporting
- Use these to bound how much of the residual is measurement failure vs. real relocation. No equivalent magnitude has been found for the USA↔GBR / USA↔CHN / USA↔IND / GBR↔IND / GBR↔CHN / IND↔CHN corridors in §A8 — don't assume those mirrors will agree just because they're all high-capacity reporters

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

**Registration required:** Swiss-Impex (bulk export), USA Trade Online or a
free Census API key, WGC Goldhub, Comtrade (API key).

**Has a real API:** HMRC uktradeinfo, US Census, Comtrade, FRED. DGCIS's
FTDDP portal is a query tool, not a REST API, but does support partner- and
commodity-filtered exports. Everything else is download-and-parse.

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
