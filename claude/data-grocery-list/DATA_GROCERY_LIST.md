# Data grocery list: spread → tariff-event instrument → vault stocks and trade legs

Compiled 21 September 2026, from scratch (it assumes nothing is already in
hand). Companion to `DATA_SOURCES.md`, which has the access mechanics for the
items it already covers.

**The design this list serves.** Build the COMEX–London spread daily, split
into its level (New York-now minus London-now) and its slope (New York carry).
Use tariff announcements to shift the spread (the first stage). Then trace the
response in COMEX stocks (daily), London stocks (monthly) and each trade leg of
the arbitrage (monthly).

**Legend:** ✅ free and public · 💲 paid · ⚠️ available with a serious caveat ·
❌ not available, so an assumption is needed

Section 2a records a second, dedicated search for storage and lease rates. It
reverses the first pass on storage (from ❌ to ⚠️/✅) and narrows the gap on
lease rates.

---

## 1. The spread (daily)

| Item | Source | Coverage | Status |
|---|---|---|---|
| LBMA Gold Price PM (and AM) | LBMA (`prices.lbma.org.uk` JSON), run by ICE Benchmark Administration (IBA) | daily, full history | ✅ |
| Finishing time of each day's LBMA auction, for the clock fix | IBA auction records | — | ❌ not found as a public series → assume 15:00 plus a few minutes |
| COMEX settlement price and open interest, **every contract month** | Databento `GLBX.MDP3` statistics schema, or CME DataMine | daily, 2010s onward | 💲 usage-based |
| COMEX **1-minute bars** for the lead contract, to price COMEX at the London auction time | Databento `ohlcv-1m` | intraday | 💲 |
| Contract rules: delivery months, first notice day, last trading day | CME rulebook, COMEX chapter 113 | static | ✅ |
| CME holiday calendar, to date first notice day correctly | CME | static | ✅ |
| Settlement procedure and its changes (October added as a lead month, effective 11 Jan 2026) | CME notices (SER-9637) | static | ✅ |
| Dealer EFP quotes, to validate the proxy | Bloomberg contributor pages | — | 💲 and entitlement-gated; optional |

## 2. Carry inputs

| Item | Source | Status |
|---|---|---|
| SOFR (from Apr 2018); effective fed funds rate before that | FRED `SOFR`, `DFF` | ✅ |
| **A term rate at the reading horizon** (overnight rates mismeasure carry when cuts or hikes are expected) | SOFR futures (`SR3`) or fed funds futures via Databento; Term SOFR (CME, licensed); T-bills (FRED `DTB3`) as a weaker proxy | 💲 via the same vendor, or ✅ with the proxy's flaws |
| **New York storage** | COMEX depositories' filed maximum fees (§2a) | ⚠️ obtainable, not as a ready-made series |
| **London lease rate** | LBMA Trade Data lease/loan/deposit reports (§2a) | 💲 Oct 2020 onward only |
| **New York lease rate** | — | ❌ no independent source (§2a) |

### 2a. Storage and lease rates: what exists

**Storage in New York: obtainable, not unavailable.**

- COMEX licensed depositories set their own storage fees. The exchange
  requires ninety days' written notice before any change, and requires that
  "each Licensed Depository's fees and charges shall be uniform for all storers
  and there shall be no preference in the fixation of fees and charges and no
  rebate of fees and charges" (NYMEX/COMEX submission #10-236 to the CFTC,
  23 Aug 2010).
- Every change is announced in a CME Market Regulation notice ("Approved
  Changes in Gold, Gold (Enhanced Delivery), and Silver Storage Rates for …").
  These notices are also attached as exhibits to COMEX's weekly CFTC Regulation
  40.6(d) notifications, which the CFTC hosts as PDFs.
- Examples found:
  - Delaware Depository: gold storage **$20.00 per contract**, delivery in
    $0.00, delivery out $35.00, effective 1 Jul 2026. The rates "reflect the
    maximum amounts of fees that can be charged" (MKR 03-18-26).
  - Brink's (MKR 11-20-25b, effective 1 Mar 2026), JPMorgan Chase (MKR
    11-20-25c) and HSBC Bank USA (MKR 08-03-26, effective 1 Nov 2026) have
    notices of the same kind. Their amounts were not retrieved.
  - A June 2010 secondary source quotes COMEX gold storage at **$12–15 per
    100-oz bar per month**, i.e. $1.44–1.80 per ounce per year.
- **The time unit of the 2026 notices is inferred, not confirmed:** per 100-oz
  contract per month, by that convention.
- **As a rate, at the sample's average LBMA PM:**

  | Fee | 2015–19 ($1,266) | 2025 ($3,434) | 2026 ($4,574) |
  |---|---:|---:|---:|
  | $1.44/oz/yr | 0.11% | 0.04% | 0.03% |
  | $1.80/oz/yr | 0.14% | 0.05% | 0.04% |
  | $2.40/oz/yr | 0.19% | 0.07% | 0.05% |

- **Cross-checks**, all at or below 0.12%:
  - BullionVault charges 0.12% a year including insurance, at the same rate in
    London, New York, Zurich, Toronto and Singapore (retail).
  - The cheapest US gold ETFs, IAUM at 0.09% and GLDM at 0.10%, have all-in
    expense ratios that bound institutional custody from above.
- **Caveats:**
  - These are **maximum** fees for exchange-stored metal. Large holders of
    eligible metal under private contract, and banks storing in their own
    vaults, may pay less.
  - Whether the fee includes insurance of the storer's metal is not stated.
    Depositories must carry all-risk cover to exchange minimums; Brink's
    reported $200m through Lloyd's in 2010.
- **Collection route:** CME's website blocks scripted access (HTTP 403 from
  both the site and the notice pages). The CFTC's copies of the weekly
  notification filings download without trouble. Building a panel of fees by
  depository and date for 2015–2026 means collecting every storage-rate notice
  from those filings.

**Storage in London:** not published at wholesale. The retail and ETF bounds
above apply. The model does not need it: the curve's level compares spot with
spot, and London carry never enters.

**London lease rate: paid, and only from October 2020.**

- GOFO, the published benchmark from which lease rates were derived, was
  discontinued in January 2015. No free benchmark has replaced it.
- **LBMA Trade Data** (distributed by Nasdaq, formerly LBMA-i) reports daily
  London OTC activity, T+1, by tenor (1 and 2 weeks; 1, 3, 6, 9 and 12
  months; 1 year+):
  - loan/lease/deposit **volumes**: fee-liable daily on Bloomberg `LBMA6`,
    tickers `LBXULL*`; free but delayed weekly on `LBMA7` (terminal
    required);
  - from 5 Oct 2020, a subscription **"Lease Loan Deposit Volume in
    Percentage Tranche"** report via Nasdaq FTP. LBMA describes it as giving
    "an exclusive look into precious metal lease rates, tenors and volumes".
    Its name suggests volumes binned by lease-rate band. **The tranche
    definitions were not confirmed.** Price on request (Nasdaq datasales,
    Bloomberg exchanges desk).
- **Bloomberg implied lease rates** are computed from OTC gold forward and swap
  points minus dollar rates, so they are independent of COMEX. Paid; tickers
  not confirmed (ask via `HELP HELP`).
- **Free "implied lease rates" circulating online** (GoldBroker's
  futures-based "GOFU"; Monetary Metals' forward-rate series) are built from
  COMEX futures against spot. **They are the curve's own slope under another
  name, so they cannot identify anything here.**

**New York lease rate: no independent source at any price.** No New York OTC
lease market is reported. It remains an assumption, or it is identified only as
a residual together with dealers' funding cost.

**Implications for the model.**

1. Replace the constant 0.25% storage assumption with **c_t / S_t**, where c_t
   is the depository fee in dollars per ounce per year. Storage is a dollar
   cost per ounce, so as a rate it falls as gold gets dearer: roughly 0.11–0.19%
   in 2015–19 and 0.03–0.07% in 2025–26. The convention overstates it by a
   factor of about 1.3–2.3 in the calm years and about 4–8 by 2025–26.
2. **The calm-slope puzzle sharpens rather than dissolves.** The calm slope is
   ω = 0.58 pp, or 0.55 net of the overnight-rate path. Storage explains at
   most 0.11–0.19 pp of it. The remaining 0.36–0.47 pp is not storage. It would
   need a New York lease rate of about −0.4%, which is implausible. The leading
   remaining candidate is dealers funding the carry trade above SOFR, the gold
   analogue of the balance-sheet costs behind post-2008 CIP deviations in FX.
   A testable implication follows: if balance-sheet costs drive it, the slope
   should jump around quarter-ends, as the FX basis does.
3. The London lease-rate data (Oct 2020 onward) cover the tariff episode but not
   the 2015–19 baseline. In the model they enter only through the cost of
   financing metal in transit, which widens the arbitrage band. In calm,
   integrated periods they are also a proxy for the New York lease rate.

## 3. The instrument: tariff events

| Item | Source | Status |
|---|---|---|
| Executive orders and annexes (e.g. EO 14257, with gold's exemption in Annex II) | Federal Register API; whitehouse.gov | ✅. Generic search misses gold because it sits in an annex table |
| CBP classification rulings (e.g. N351466: cast bars into 7108.13.55) | CBP CROSS API | ✅ |
| **First public timestamp of each event** (hour and minute) | Newswires (Bloomberg, Reuters); FT article times; timestamps of presidential social-media posts | 💲 for newswires; ⚠️ hand-collected otherwise. **Needed**: e.g. the CBP ruling is dated 31 Jul 2025 but became public around 7–8 Aug |
| Tariff rate that would apply by origin (UK, Switzerland, Canada…), to size the shock | EO country annexes; USITC HTS chapter 99 | ✅ |
| Continuous trade-policy-uncertainty index, as a complement to discrete events | Caldara–Iacoviello et al. TPU; Baker–Bloom–Davis | ✅ monthly; daily versions exist (verify) |
| Market-implied tariff probabilities | Prediction-market APIs (Kalshi, Polymarket) | ⚠️ patchy for 2024–25; optional |
| Comparison markets for a placebo or difference-in-differences: silver, platinum | COMEX/NYMEX plus LBMA/LPPM benchmarks | 💲/✅; optional. Check which exemptions covered them |

## 4. Stocks: real movement

| Item | Source | Coverage | Status |
|---|---|---|---|
| **COMEX registered and eligible, by depository** | CME daily `Gold_Stocks.xls` | **current day only**; no public archive, and scripted access is blocked | ⚠️ **the biggest data risk.** Wayback Machine snapshots are sparse (an earlier pull found 87 in 14 years). Daily history needs Bloomberg or Nick Laird (💲, verify he has it), or collecting forward from today, which cannot cover 2024–25 |
| COMEX deliveries (issues and stops) | CME daily and year-to-date reports | same archiving problem | ⚠️ optional |
| London vault holdings | LBMA | monthly, end of month, from Jul 2016, published with a lag (`DATA_SOURCES.md` says three months; verify) | ✅ but monthly |
| Bank of England gold under custody | BoE | monthly | ✅ |
| **Gold ETF holdings, by fund and vault location** (to net ETF flows out of London stock changes) | Issuers: SPDR GLD, iShares IAU (daily); WGC Goldhub (monthly, by fund) | daily or monthly | ✅ (Goldhub needs free registration) |
| Central bank holdings (their metal moves London stocks with **no** trade record) | IMF IFS; WGC | monthly | ✅ |
| Swiss vault holdings | — | — | ❌ not published |
| New York non-COMEX vaults; foreign official gold at the New York Fed | — | — | ❌ essentially unavailable |

## 5. Trade legs: the recorded footprint

HS codes for every leg: **7108.12, 7108.13 and 7115.90**. CBP has moved kilo and
100-oz bars back and forth between 7108.13 and 7115.90, so without 7115.90 part
of the arbitrage is lost. Pull the most detailed national digits available,
**in mass units**, and convert to tonnes at the boundary.

| Leg | Primary source (reporter) | Mirror | Status and gotchas |
|---|---|---|---|
| UK → CH (400-oz bars to refineries) | **Swiss imports** (BAZG open-data bulk files, kg and USD, 2002–) | HMRC UK exports | ✅ Swiss. ⚠️ The UK side is unusable: UK-reported exports to CH are 300–2,000× below Swiss-reported imports in some months, unexplained. Use the Swiss figures |
| CH → US (kilo and 100-oz bars) | **Swiss exports to US** (BAZG) | US Census imports from CH | ✅ both. ⚠️ Census records the episode under **HS 7115**, not 7108: Jan 2025 is $18.9bn under 7115 against $0.57bn under 7108 (`RESEARCH_DOSSIER.md` §4). A 7108-only pull misses it. Pull with quantity at 10-digit HTS, and check whether imports are assigned by origin or by shipment |
| UK → US direct | US Census imports from UK; HMRC exports to US | each other | ✅ both. ⚠️ origin attribution again |
| Eastward return: US → CH, US → UK, CH → UK | Census exports (domestic and re-export split); BAZG; HMRC | each other | ✅. US exports are reported **in grams** at fine detail, a units trap |
| US totals in kg, as a cross-check | USGS Mineral Industry Surveys | monthly | ✅ |
| Other US import routes (Canada, Mexico, Australia, Hong Kong…): robustness only | Census by partner | monthly | ✅ |
| GBP → USD for HMRC values | FRED `DEXUSUK` | daily | ✅ |

## 6. Transfer cost and capacity (for the threshold κ and the ceiling Q̄)

| Item | Status |
|---|---|
| Armoured air freight and insurance per ounce | ❌ private quotes (Brink's, Loomis, Malca-Amit) → **assumption**, or estimate κ from the hinge |
| Refinery recasting fees, 400-oz to kilo | ❌ only press anecdotes → **assumption** |
| Refinery and freight capacity, per month | ❌ → **assumption** (e.g. the historical maximum of Swiss exports) or estimate Q̄ |
| Days in transit, including refinery queues | ❌ → **assumption** |

## 7. Absorption benchmarks (to interpret the residual)

| Item | Source | Status |
|---|---|---|
| Country consumer demand | WGC Goldhub | ✅ quarterly (registration) |
| India imports | TradeStat FTSPCC | ✅ value only; excludes 7115 |
| China withdrawals | Shanghai Gold Exchange | ⚠️ withdrawals are not demand |

---

## Assumptions that remain

**Spread construction**

1. **New York lease rate.** No independent source exists. In calm, integrated
   periods, proxy it with the London rate where LBMA Trade Data exist (Oct 2020
   onward), and with zero before that.
2. **Dealers' funding spread over SOFR** is then identified only as a residual
   in the slope.
3. **Storage** is no longer a free assumption, but it needs the depository fee
   panel built, plus a judgement on whether large holders pay below the
   maximum.
4. The futures price equals the forward price (ignoring the margining term).
5. The term-rate proxy, if SOFR futures are not bought.
6. The auction's finishing time, if IBA round times are not obtainable.

**Instrument validity**

7. **Event timing** is the first public news, not the date on the document.
8. **Surprise:** only the unanticipated part of each announcement moves
   anything. Classify events, or use a continuous index or market-implied
   probabilities.
9. **Sign:** exemptions and walk-backs *lower* the premium, so events must be
   signed. A single dummy will not do.
10. **The exclusion restriction.** Announcements must affect stocks and trade
    only through the spread. Three things threaten it:
    - safe-haven moves in the gold price shift ETF flows and absorption. Net
      out the ETF and central-bank series and control for the price.
    - owners may relocate metal as a precaution whatever the price. This is
      untestable without owner data, which do not exist.
    - the country-wide Swiss tariff (39%) affects Swiss exports generally, not
      only gold. Prefer gold-specific events.

**Mapping flows**

11. Every recorded flow within the triangle is relocation or transformation,
    not absorption, unless netted against section 7.
12. **Recording time:** Switzerland records a shipment when it leaves and the
    US when it arrives. Shipments that cross a month boundary misalign.
13. **Which mirror to trust**, leg by leg. Swiss data for UK → CH.
14. **Unobservable relocation:** reclassification between registered and
    eligible, Swiss vault stocks and New York non-COMEX vaults. These give
    bounds, not point estimates, on the overcount/undercount multiplier.
15. **The hinge's form:** a continuous kink, κ constant in dollars (because
    costs are charged by weight), applied daily and summed to the month.

## Design risks

- **Daily COMEX stocks history is the weak link.** Without paid history, a
  daily event study on stocks cannot cover 2024–25, and COMEX stocks drop to
  the same monthly frequency as everything else.
- **Monthly outcomes plus a handful of events** make a weak first stage and
  leave few independent observations for inference. Plan on randomisation
  inference or a wild bootstrap. The daily first stage (events → spread) is
  where the instrument will be strongest.
- **London stocks** are month-end snapshots published with a lag, and only from
  2016.
- **The London lease-rate data start in October 2020**, after the calm
  baseline.

## Sources consulted for §2a

- NYMEX/COMEX submission #10-236 to the CFTC, 23 Aug 2010 (depository fee
  rules): <https://www.cftc.gov/sites/default/files/stellent/groups/public/@rulesandproducts/documents/ifdocs/rul082310nymexandcomex001.pdf>
- COMEX weekly 40.6(d) notification, filed 17 Mar 2026 (example of the
  CFTC-hosted filings that attach MKR notices): <https://www.cftc.gov/sites/default/files/filings/orgrules/26/03/rules03172641072.pdf>
- CME MKR 03-18-26, Delaware Depository storage rates: <https://www.cmegroup.com/notices/market-regulation/2026/03/mkr03-18-26.html>
  (amounts as republished by SMM: <https://news.metal.com/newscontent/103815390-cme-group-approved-changes-in-gold-gold-enhanced-delivery-and-silver-storage-rates-for-delaware-depository>)
- CME MKR 11-20-25b (Brink's): <https://www.cmegroup.com/notices/market-regulation/2025/11/mkr11-20-25b.html>
- CME MKR 11-20-25c (JPMorgan Chase): <https://www.cmegroup.com/notices/market-regulation/2025/11/mkr11-20-25c.html>
- CME MKR 08-03-26 (HSBC Bank USA): <https://www.cmegroup.com/notices/market-regulation/2026/08/mkr08-03-26.html>
- 2010 COMEX storage fees, secondary: <http://about.ag/futures.htm>
- BullionVault tariff: <https://www.bullionvault.com/help/tariff.html>
- ETF expense ratios (IAUM, GLDM): <https://www.etf.com/sections/etf-basics/gold-etfs-explained-what-investors-should-know-about-gld-gldm-iau-and-iuam>
- LBMA daily trade reporting data: <https://www.lbma.org.uk/prices-and-data/lbma-daily-trade-reporting-data>
- LBMA Trade Data product enhancements (LLD report, 5 Oct 2020): <https://www.lbma.org.uk/articles/lbma-trade-data-product-enhancements>
- LBMA Trade Data via Bloomberg (tickers, `LBMA6`/`LBMA7`): <https://cdn.lbma.org.uk/downloads/Video-Assets/lbmatradedataviabloomberg.pdf>
- Futures-implied lease rates (circular for this project): <https://goldbroker.com/news/slg-implied-gold-silver-lease-rates-713>
