# Spread-only data list, with the best storage and lease rates obtainable

Compiled 22 September 2026. A narrower rewrite of
`claude/data-grocery-list/DATA_GROCERY_LIST.md`, which serves the full
event-study design. This one lists **only what enters the spread**, and it
takes seriously the instruction to use the best approximations of storage and
lease rates we can actually get, rather than the flat assumptions now in the
code.

**Scope.** I read "steps 1–5, 7" as equations (1)–(5) and (7) of the system in
`claude/spread-explainer/spread_system.tex` — the structural equations, leaving
out (6), which is the measurement-error equation and has no data of its own.
Everything that feeds those equations *on the price side* is below. The three
items from (4), (5) and (7) that are not spread inputs — transfer-cost quotes
and the shipped-tonnes series — are parked in §8 so the boundary is explicit
rather than silent. If "steps" meant the sections of the earlier grocery list,
say so and I will widen it back out.

**Legend:** ✅ free and public · 🟢 already on disk · 💲 paid · ⚠️ available with
a caveat · ❌ not available at any price, so an assumption is needed ·
🔍 promising but unverified.

---

## 0. What changed since the 21 September list

Three findings, in descending order of how much they buy.

1. **A loco-London forward curve exists and is cleared.** ICE Futures U.S.
   lists **Gold Daily Futures**: 100 oz, LBMA Good Delivery, held in an LPMCL
   London vault **on an unallocated account basis**, with **"up to 70
   consecutive Eligible Contract Dates"** — a daily-dated London forward curve
   running about three and a half months out (ICE Futures U.S. rulebook
   ch. 30.A, read directly). Its slope *is* GOFO, the London gold forward rate
   that was discontinued in 2015, and GOFO plus the dollar rate gives the
   London lease rate. The previous list concluded that no lease-rate source
   existed below a Bloomberg or Nasdaq subscription. That conclusion was
   wrong in the direction that matters.
2. **It settles in the LBMA auction window.** ICE's *Daily Settlement Windows
   by Contract* (February 2026) gives "**Daily Gold Futures 15:00 to 15:05
   London Time**" — every other ICE Futures U.S. contract on that sheet is
   listed in New York time, and this one is not. So the London forward curve
   is struck at the same moment as the LBMA PM benchmark. The 3½-hour clock
   mismatch that dogs the COMEX–LBMA pair does not exist within the London
   pair.
3. **Two things we would otherwise buy are already inside subscriptions we
   hold.** ICE Futures U.S. is a Databento dataset (`IFUS.IMPACT`, history
   from 23 December 2018 — the sample starts in 2019). And SOFR futures sit in
   `GLBX.MDP3`, the CME dataset already used for COMEX, so a term rate matched
   to the contract horizon costs no new vendor.

Storage did not change: the route to the depository fee panel is confirmed
again below, and the CME notice pages still refuse automated access.

---

## 1. The whole list in one table

Symbols follow `spread_system.tex`. "Eq." is the equation the item feeds.

| Item | Symbol | Eq. | Source | Status |
|---|---|---|---|---|
| LBMA Gold Price PM, daily | $S_t$ | (2) | `prices.lbma.org.uk/json/gold_pm.json` | 🟢 2015-01-02 → 2026-08-20, 2,857 days |
| COMEX settlement + open interest, every contract month | $F_t(\tau)$, weights | (1), (8) | Databento `GLBX.MDP3`, statistics schema (`stat_type` 3 and 9) | 🟢 same span, 120 symbols, 82,240 rows |
| COMEX 1-minute bars, lead months, 14:55–15:05 London | $F_t$ re-timed | (6) | Databento `GLBX.MDP3`, `ohlcv-1m` | 💲 small incremental pull |
| Contract calendar: delivery months, first notice day, CME holidays | $\tau$ | (1) | CME rulebook ch. 113; CME holiday calendar; SER-9637 for October as a lead month from 11 Jan 2026 | ✅ |
| **ICE Gold Daily Futures, all listed contract dates: settlement, open interest, volume** | $F^{L}_t(\tau)$ | new | Databento `IFUS.IMPACT` | 🔍 💲 from 2018-12-23; coverage to verify (§3) |
| SOFR; effective fed funds before Apr 2018 | $r_t$ | (1), (5) | FRED `SOFR`, `DFF` | 🟢 in `short_rate` |
| Term dollar rate at horizon $\tau$ | $r_t(\tau)$ | (1) | SOFR futures `SR1`/`SR3` (and `ZQ`) in `GLBX.MDP3` | 💲 no new vendor |
| COMEX depository storage fees, by depository and effective date | $s^{N}_t$ | (1) | CME MKR notices, collected from CFTC-hosted weekly 40.6(d) filings | ⚠️ build it (§4) |
| Depository shares of registered stock, for weighting the fees | weights on $s^N$ | (1) | CME daily gold stocks report, by depository | ⚠️ 🟢 87 snapshots only |
| London lease rate | $\ell^{L}_t$ | (1), (5) | implied from the ICE curve; else LBMA Trade Data LLD report | 🔍 / 💲 (§5) |
| New York lease rate | $\ell^{N}_t$ | (1) | no direct source; identified as a residual once $s^N$ and $\ell^L$ are pinned | ❌ → identified (§5) |
| Applicable tariff rate by origin, as a bound on $\theta_t$ | $\theta_t$ | (3) | EO country annexes; USITC HTS ch. 99 | ✅ |
| Event timestamps, to date the curvature | $h_t$ | (3) | Federal Register API; CBP CROSS; newswire times | ✅ / ⚠️ (§6) |

---

## 2. The two price legs

### London spot, $S_t$ 🟢

The LBMA Gold Price PM is a daily auction run by ICE Benchmark Administration
and struck at 15:00 London, in USD per troy ounce, for **unallocated** loco
London metal — a claim on a bank's pooled London gold, the gold analogue of a
deposit rather than a safe-deposit box. Free JSON, full history, already in
`efp_dislocation_v2.csv`.

The old list flagged the auction's *finishing* time as an unobtainable input.
It matters much less now: ICE's London gold contract settles into the same
15:00–15:05 window, so anything priced against that contract is aligned with
the auction by construction.

### New York futures, $F_t(\tau)$ 🟢 + 💲

Settlements and open interest by contract month are in hand for 2015–2026. The
one purchase worth making is the **1-minute bar slice around 15:00 London** for
the lead contracts, which lets the COMEX leg be read at the London auction
instant instead of at the 13:30 New York settlement. That is item 1 in
`claude/mechanism-figures/NEXT_STEPS.md`, and it is worth restating why it is
first: a 1% intraday move in the 3½-hour gap enters the 90-day dislocation as
about 4 pp, the same order as the signal being measured.

With the ICE curve added, the three legs line up at one instant:

| Leg | Struck at | Aligned? |
|---|---|---|
| LBMA PM, $S_t$ | 15:00 London | reference |
| ICE Gold Daily settlement, $F^L_t$ | 15:00–15:05 London | yes, as listed |
| COMEX settlement, $F_t$ | 13:30 New York ≈ 18:30 London | no — re-time with 1-minute bars |

---

## 3. The London forward curve: what to get and what to check 🔍

**What it is.** A futures contract whose delivery is loco London unallocated
metal, listed for every London business day that is also a New York banking
day, up to 70 consecutive dates. Read across those dates on one day, it is a
forward curve for London gold — the object GOFO used to publish.

**Why it is worth the trouble.** Three things fall out that are currently
assumed.

1. **The London gold forward rate, and hence the lease rate.** For unallocated
   metal there is no storage cost to the holder, so the forward satisfies
   $F^{L}_t(\tau)=S_t\exp[(r_t-\ell^{L}_t)\tau/365]$. Fit $\ln F^L$ on $\tau$
   across the listed dates; the slope annualised is the forward rate, and
   $\ell^{L}_t = r_t - \text{GOFO}_t$. Daily, 2019–2026, non-circular — it
   comes from a different exchange, a different deliverable and a different
   clearing house than COMEX.
2. **The location premium with no carry assumption at all.** Matching
   maturities across the two curves,
   $$\frac{F_t(\tau)}{F^{L}_t(\tau)} = \bigl[1+p_t+\Lambda_t(\tau)\theta_t\bigr]\exp\!\Bigl[\bigl(s^{N}_t-\ell^{N}_t+\ell^{L}_t\bigr)\frac{\tau}{365}\Bigr]$$
   The dollar rate cancels: it is the same currency on both legs. The
   intercept of this ratio is the location premium, and its slope is the
   *cross-location* carry differential. Nothing here needs SOFR, a term rate
   or a day-count convention.
3. **The New York lease rate becomes identified.** From that slope, with
   $s^{N}_t$ taken from the fee notices (§4) and $\ell^{L}_t$ from the London
   curve, $\ell^{N}_t$ is the only unknown left. It stops being an assumption
   and becomes a residual of a *difference in slopes*, which is a far weaker
   thing to lean on than the current "assume zero".

**What to verify before relying on any of it.** The contract exists to let
auction participants convert into cleared positions, so its liquidity may live
almost entirely at the nearest dates. In order:

1. `metadata.get_dataset_range("IFUS.IMPACT")` and
   `metadata.list_schemas("IFUS.IMPACT")` — free metadata calls. Confirm the
   `statistics` schema is offered, which is what carries settlement price and
   open interest.
2. Pull one `definition` day and find the gold daily root and its symbology —
   the symbol convention for a date-dated contract is not the CME
   month-letter convention, and this is where a pull silently returns nothing.
3. Pull `statistics` for a single quiet week in 2019 and a single week in
   January 2025. Count, per day: how many contract dates carry a settlement,
   how far out the furthest one is, and how many carry non-zero open interest.
4. **Decision rule.** If settlements exist across most of the 70 dates, fit the
   curve. If they exist but open interest is concentrated at the front, the
   settlements are a committee's mark rather than a traded price — which is
   precisely what GOFO was, a quoted rate, so it is still usable, but every
   figure must say "quoted, not traded". If settlements exist only for a
   handful of near dates, the curve is too short to fit and this item reduces
   to a **synchronous London spot cross-check** on the LBMA auction, which is
   still worth having.

**Cost.** Databento is usage-based ($10/GB, subscriptions from $199/month).
A statistics-schema pull for one product over seven years is small; the risk is
accidentally pulling book data for the whole exchange, so restrict by symbol
and schema.

**Sample:** 23 Dec 2018 onward, which covers the project's 2019–2026 window but
**not** the 2015–2018 calm baseline the COMEX series reaches back to. Two
possible spread series then exist over different spans; the overlap from 2019
is what lets the shorter one discipline the longer one.

---

## 4. Storage, $s^{N}$: from an assumption to a measured schedule ⚠️

The code currently uses a flat 0.25% a year. That is wrong in a knowable
direction: storage is charged **per ounce in dollars**, so as a rate it falls
when the gold price rises, and the gold price roughly quadrupled over the
sample.

**What to collect.** COMEX licensed depositories file their maximum storage and
handling fees with the exchange, which requires ninety days' notice of any
change and requires the fees to be uniform across storers with no rebates
(NYMEX/COMEX submission #10-236 to the CFTC, 23 Aug 2010). Every change is
announced in a CME market-regulation notice titled "Approved Changes in Gold,
Gold (Enhanced Delivery), and Silver Storage Rates for …".

**The route, re-verified today.** CME's own notice pages still block automated
access — both notice URLs timed out again on this pass, consistent with the
403s recorded in the earlier list. The CFTC's copies do not: the weekly
Regulation 40.6(d) notification filings that carry these notices as exhibits
download cleanly and are text-extractable (I pulled COMEX submission 26-159,
filed 17 March 2026, and read its exhibits as plain text with `pypdf`; that
particular week happened to carry copper regularity items rather than storage
rates). So the collection job is: walk the COMEX and NYMEX weekly filings on
`cftc.gov/sites/default/files/filings/orgrules/<yy>/<mm>/`, extract text, keep
the exhibits whose subject line matches the storage-rate title, and parse the
fee tables.

**What is known so far.**

| Depository | Notice | Effective | Gold storage | Delivery in / out |
|---|---|---|---|---|
| Delaware Depository | MKR 03-18-26 | 1 Jul 2026 | $20.00 per contract | $0.00 / $35.00 |
| Brink's, New York and New Jersey | MKR 11-20-25b | 1 Mar 2026 | not retrieved | — |
| JPMorgan Chase, New York | MKR 11-20-25c | 1 Mar 2026 | not retrieved | — |
| HSBC Bank USA, New York | MKR 08-03-26 | 1 Nov 2026 | not retrieved | — |

The notices state the amounts are "the maximum amounts of fees that can be
charged". The **time unit of the $20.00 is inferred, not confirmed** — per
100-oz contract per month is the market convention, and a 2010 secondary source
puts COMEX gold storage at $12–15 per 100-oz bar per month, but the notice text
should be read before the number is used.

**How it enters.** Build $c_t$ in dollars per ounce per year per depository,
then $s^{N}_t = c_t / S_t$. Weight depositories by their share of registered
stock, which the daily CME gold stocks report gives by depository — we hold 87
snapshots, enough for a slowly moving weight but not a daily one; a constant
weight from a few snapshots is defensible and should be stated.

Order of magnitude, at the sample's average LBMA PM:

| Fee | 2015–19 ($1,266) | 2025 ($3,434) | 2026 ($4,574) |
|---|---:|---:|---:|
| $1.44/oz/yr | 0.11% | 0.04% | 0.03% |
| $1.80/oz/yr | 0.14% | 0.05% | 0.04% |
| $2.40/oz/yr | 0.19% | 0.07% | 0.05% |

So the flat 0.25% overstates storage by roughly 1.3–2.3× in the calm years and
4–8× by 2025–26.

**Upper bounds, for a sanity check:** BullionVault charges 0.12% a year
including insurance, at the same rate in London, New York and Zurich; the
cheapest US gold ETFs (IAUM 0.09%, GLDM 0.10%) bound institutional custody from
above, since their all-in expense ratio includes custody plus everything else.

**Caveats to carry into the text.** These are maxima, not transacted rates;
large holders of eligible metal under private contract may pay less. Whether
the fee includes insurance is not stated in the notices. And the in/out
handling charges are **not** storage: $35.00 per contract out is $0.35 an
ounce, a one-off level, which belongs in the transfer cost $\kappa$ rather than
in the carry rate — a small public component of a quantity we otherwise have no
public number for.

**London, $s^{L}$.** Zero is the right assumption for the ICE contract's
deliverable: unallocated metal is a bank liability, and the holder pays no
vaulting fee. Allocated London storage is roughly 0.10–0.15% a year. This
matters only for the transit-financing term in equation (5).

---

## 5. Lease rates, $\ell^{L}$ and $\ell^{N}$ 🔍 💲 ❌

A lease rate is what an owner earns for lending metal out; in the parity
condition it plays exactly the role of the foreign interest rate. GOFO — the
published London forward rate from which lease rates were derived — was
discontinued in January 2015, which is why the project has been running without
one.

Ranked by what we can actually obtain:

1. **Implied from the ICE London curve (§3).** 🔍 Daily, 2019–2026, inside a
   vendor we already use, and non-circular. This is the one to try first.
2. **LBMA Trade Data, "Lease Loan Deposit Volume in Percentage Tranche".** 💲
   From 5 October 2020, distributed by Nasdaq, with Bloomberg and Refinitiv
   feeds. The free LBMA page publishes only 12-week moving-average turnover in
   dollars — volumes, no rates. The tranche report is described as giving "an
   exclusive look into precious metal lease rates, tenors and volumes", which
   suggests volumes binned by rate band rather than a rate series; **the
   tranche definitions are still unconfirmed**. Price on request, and LBMA
   offers free sample data on request, which is the cheap way to find out what
   the fields actually are.
3. **Bloomberg implied lease rates.** 💲 Computed from OTC gold forward and
   swap points minus dollar rates, so independent of COMEX. Terminal and
   entitlement required; confirm tickers on the terminal rather than from a
   remembered one.
4. **GOFO history to January 2015.** ✅ via Nasdaq Data Link's LBMA series.
   Useless for the sample, which starts in 2015, but it gives a prior on the
   level and volatility of the lease rate in calm conditions — worth one
   sentence, not a variable.
5. **Excluded as circular:** Monetary Metals' MM GOFO and GoldBroker's
   "implied lease rates" are built from COMEX futures against spot. They are
   the COMEX curve's own slope under another name, so regressing our
   dislocation on them would be regressing a variable on itself.

**New York, $\ell^{N}$.** ❌ There is no reported New York OTC lease market, at
any price. Three ways to handle it, in order of preference:

- **Identified.** With $s^{N}$ from §4 and $\ell^{L}$ from §3, the slope of the
  COMEX-to-ICE ratio pins $\ell^{N}$ (§3, point 3).
- **Restricted.** Impose $\ell^{N}=\ell^{L}$ in calm, integrated windows, and
  let it break only in episodes. This is testable once $\ell^{L}$ exists.
- **Residual.** As now, absorbed into the fitted slope $\hat\omega$ together
  with dealers' funding spread.

**What this buys, concretely.** The calm-period slope is
$\hat\omega \approx 0.58$ pp, of which storage can explain at most 0.11–0.19 pp
on the numbers above. The rest is currently unattributed, and the leading
candidate is dealers funding the carry trade above SOFR — the gold analogue of
the balance-sheet costs behind post-2008 deviations from covered interest
parity. A measured $\ell^{L}$ turns that from a story into a test: if
$\ell^{L}>0$ in calm periods, then $s^{N}-\ell^{N}$ should be *negative* under
the restriction $\ell^{N}=\ell^{L}$, and the unexplained slope widens rather
than closes. Then the quarter-end test follows — if balance-sheet costs drive
it, the slope should jump at quarter-ends, as the FX basis does.

---

## 6. The dollar rate, $r$ 🟢 + 💲

- **Overnight.** SOFR from FRED, spliced to the effective fed funds rate before
  3 April 2018. Already in the panel as `short_rate`.
- **Term rate at the horizon.** ⚠️ Carry currently uses an overnight rate
  against a 90-day horizon, so when cuts are expected the carry is overstated
  and the dislocation understated. The fix is a term rate matched to $\tau$.
  **SOFR futures (`SR1`, `SR3`) and fed funds futures (`ZQ`) are CME products
  and therefore inside `GLBX.MDP3`**, the dataset already used for COMEX
  settlements — same statistics schema, no new vendor, no licence. Strip a
  forward curve from the futures strip and read it at $\tau$.
- **CME Term SOFR** is the published alternative: 1, 3, 6 and 12-month
  forward-looking rates, but its use as a data input in a service requires an
  Information Licence Agreement with CME, free to license in certain cash-market
  uses until the end of December 2026. Building the rate from SOFR futures
  ourselves avoids the question.
- **Day count.** SOFR is quoted on a 360-day year; the implied rate uses 365.
  Multiply SOFR by 365/360 before subtracting — about 0.06 pp at 2025 rates,
  and nothing at zero rates. Currently not corrected.
- Note that the ICE-to-COMEX ratio in §3 needs none of this, since the dollar
  rate cancels. The term rate only matters for the single-leg dislocation.

---

## 7. The policy term inside the spread, $h_t\theta_t$ ✅

Equation (3) puts tariff risk inside the spread itself, not merely in the
instrument set: a contract delivering in nine months is likelier to be caught by
a tariff than one delivering next month, so the hazard enters the *slope* and,
because $\Lambda$ is concave in the horizon, bends the curve down. Only two
data items are needed for that part, and neither is the full event chronology:

| Item | Use | Source | Status |
|---|---|---|---|
| Tariff rate that would apply by origin | bounds $\theta_t$, so $h_t$ can be read off the curvature | EO country annexes; USITC HTS ch. 99 | ✅ |
| Date and first public *time* of each gold-relevant announcement | dates the curvature break | Federal Register API; CBP CROSS; newswire timestamps | ✅ dates / ⚠️ times hand-collected |

The rest of the event apparatus — signing exemptions and walk-backs,
trade-policy-uncertainty indices, prediction-market probabilities — belongs to
the instrument, not the spread, and stays in the earlier list.

---

## 8. Named in the system, but not spread inputs

Listed so the omission is deliberate rather than an oversight.

| Item | Eq. | Why it is not here | Status |
|---|---|---|---|
| Swiss customs tonnes shipped to the US, $Q_t$ | (7) | the dependent variable of the flow equation, not an input to the price | 🟢 in hand, monthly |
| Armoured freight, insurance, recasting quotes, transit days | (5) | private quotes; $\kappa$ is estimated from the hinge instead, and the $0.35/oz handling charge in §4 is the only public piece | ❌ |
| Refining and freight capacity, $\bar{Q}$ | (7) | assumption or estimated ceiling | ❌ |
| COMEX and London vault stocks, trade legs, absorption benchmarks | — | outcome variables | see the earlier list |

---

## 9. Order of work

| # | Task | Cost | What it unlocks |
|---|---|---|---|
| 1 | Verify ICE `IFUS.IMPACT` coverage and symbology (§3, four steps) | metadata calls are free | decides items 2 and 3 |
| 2 | Pull the ICE gold daily statistics series, fit the London curve | small 💲 | $\ell^{L}$ daily 2019–2026; GOFO restored |
| 3 | Pull COMEX 1-minute bars around 15:00 London | small 💲 | kills the 3½-hour clock error in the COMEX leg |
| 4 | Collect the storage-fee panel from CFTC filings | free, a day's scraping | $s^{N}_t=c_t/S_t$ replaces the flat 0.25% |
| 5 | Build a term rate from `SR3`/`ZQ` in the existing CME dataset | none | removes the horizon mismatch in carry |
| 6 | Ask LBMA for the LLD sample and a price | free to ask | tells us whether item 2 needs a paid backstop |

Items 1–3 are where the leverage is: after them, the location premium can be
measured as one exchange-cleared London price against one exchange-cleared New
York price at the same instant, with no interest rate, no storage figure and no
lease rate in the calculation at all.

## 10. What each current assumption becomes

| Assumption now | Best available replacement | Residual assumption |
|---|---|---|
| storage = 0.25%/yr flat | $c_t/S_t$ from filed depository maxima, weighted by registered stock | fees are maxima; the time unit needs confirming; the weight is near-constant |
| London lease rate = 0 | implied from the ICE London forward curve | settlements may be quoted rather than traded; 2019 onward only |
| New York lease rate = 0 | identified from the COMEX-to-ICE slope difference | needs $s^{N}$; or restricted to $\ell^{L}$ in calm windows |
| overnight rate for a 90-day horizon | term rate from SOFR futures in the dataset we hold | the futures strip is a forward, not a term deposit rate |
| COMEX settle vs 15:00 London auction | re-time COMEX with 1-minute bars; ICE settles in the auction window | 1-minute bars are still not the auction print itself |
| futures price = forward price | unchanged | margining term ignored |
| SOFR used on a 365 basis | multiply by 365/360 | none, it is arithmetic |

---

## Sources

- ICE Futures U.S. rulebook ch. 30.A, Gold Daily Futures (contract dates,
  listing cycle, LPMCL unallocated delivery):
  <https://www.ice.com/publicdocs/rulebooks/futures_us/30A_Gold_Daily_Futures.pdf>
- ICE Futures U.S., *Daily Settlement Windows by Contract*, February 2026
  ("Daily Gold Futures 15:00 to 15:05 London Time"):
  <https://www.ice.com/publicdocs/futures_us/Settlement_Window.pdf>
- ICE Gold Daily Futures product page:
  <https://www.ice.com/products/62026758/Gold-Daily-Futures>
- Databento ICE Futures U.S. dataset (history from 23 Dec 2018; usage-based
  pricing): <https://databento.com/datasets/IFUS.IMPACT> and
  <https://databento.com/blog/introducing-ice-futures-us>
- Databento CME Globex MDP 3.0 (covers CME, CBOT, NYMEX and COMEX, so SOFR
  futures and COMEX gold are one dataset):
  <https://databento.com/datasets/GLBX.MDP3>
- CME Term SOFR reference rates and licensing:
  <https://www.cmegroup.com/market-data/cme-group-benchmark-administration/term-sofr.html>
- NYMEX/COMEX submission #10-236 to the CFTC, 23 Aug 2010 (depository fee
  rules):
  <https://www.cftc.gov/sites/default/files/stellent/groups/public/@rulesandproducts/documents/ifdocs/rul082310nymexandcomex001.pdf>
- COMEX weekly 40.6(d) notification, submission 26-159, filed 17 Mar 2026
  (example of the CFTC-hosted filings that attach MKR notices, and machine
  readable):
  <https://www.cftc.gov/sites/default/files/filings/orgrules/26/03/rules03172641072.pdf>
- CME storage-rate notices (pages block automated access; titles and effective
  dates confirmed via search): MKR 03-18-26 Delaware
  <https://www.cmegroup.com/notices/market-regulation/2026/03/mkr03-18-26.html>,
  MKR 11-20-25b Brink's
  <https://www.cmegroup.com/notices/market-regulation/2025/11/mkr11-20-25b.html>,
  MKR 11-20-25c JPMorgan
  <https://www.cmegroup.com/notices/market-regulation/2025/11/mkr11-20-25c.html>,
  MKR 08-03-26 HSBC
  <https://www.cmegroup.com/notices/market-regulation/2026/08/mkr08-03-26.html>
- LBMA daily trade reporting data (free page shows 12-week moving-average
  turnover only):
  <https://www.lbma.org.uk/prices-and-data/lbma-daily-trade-reporting-data>
- LBMA Trade Data product enhancements, the lease/loan/deposit tranche report,
  5 Oct 2020:
  <https://www.lbma.org.uk/articles/lbma-trade-data-product-enhancements>
- LMEprecious loco-London gold futures, withdrawn 11 July 2022 (checked as an
  alternative London curve and ruled out):
  <https://www.lme.com/en/metals/precious/lmeprecious>
- Futures-derived "implied lease rates", excluded as circular:
  <https://goldbroker.com/news/slg-implied-gold-silver-lease-rates-713>,
  <https://www.monetary-metals.com/home/about-forward-rates/>
</content>
