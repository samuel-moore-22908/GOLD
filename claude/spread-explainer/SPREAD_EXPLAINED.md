# The COMEX–London gold spread, from scratch

This walks through the project's one price variable: what data goes in, every
transformation applied to it, and what comes out. Every number here is printed
by `worked_examples.py` in this folder from files already in `data/processed/`
(output saved in `worked_examples_output.txt`). Where this document disagrees
with something written earlier in the project, it says so in a quoted note.

**In one paragraph.** Gold trades in two places at once. London prices it for
delivery now. New York prices it for delivery in a few months. The New York
price should be higher by exactly the cost of financing and storing gold until
then. The *spread* is how far New York actually sits above London. The
*dislocation* is what is left after taking out that financing cost. When the
leftover is big enough to pay for flying metal across the Atlantic, metal
moves. That is the link to the trade data.

---

## 1. The data: three prices and an assumption

### London: the LBMA Gold Price PM (call it **S**)

- A daily auction for the London Bullion Market Association (LBMA), run by ICE
  Benchmark Administration. The project uses the afternoon auction, set at
  **15:00 London**.
- Priced in USD per troy ounce, for **"loco London" unallocated** gold.
  "Unallocated" means a claim on a bank's pooled metal in London vaults,
  much like a bank deposit denominated in gold. No specific bars are yours.
- Pulled live from `prices.lbma.org.uk/json/gold_pm.json`. One number per
  London business day. Column `lbma_pm_usd`.

### New York: COMEX gold futures (call the price **F**)

- A **futures contract** fixes a price today for 100 troy ounces that change
  hands in a named future month. Both the money and the metal move then, not
  now. The metal comes as a **warrant**, a title document for specific bars
  in a New York vault approved by CME, the exchange group that runs COMEX.
- Many contracts trade at once, one per delivery month. Each is named by root,
  month letter and year digit: `GCJ5` = April 2025. The heavily traded months
  are G Feb, J Apr, M Jun, Q Aug, V Oct, Z Dec.
- Two numbers are taken per contract per day:
  - **Settlement price.** The official end-of-day price CME calculates from
    trading around **13:30 New York**, and uses to mark every position to
    market. It is not the last trade. Column `settle`, or `comex_settle` once
    one contract has been chosen.
  - **Open interest.** How many contracts are outstanding. It shows which
    contract the market is actually using.
- Source: Databento's CME feed (`GLBX.MDP3`), two zips downloaded by hand into
  `data/databento/`. In the statistics stream, `stat_type = 3` is settlement
  and `9` is open interest.

### The dollar interest rate (call it **r**)

- **SOFR** (Secured Overnight Financing Rate) is the overnight rate on loans
  backed by Treasuries. Think of it as the cost of borrowing dollars against
  safe collateral. It comes from FRED and starts on 3 Apr 2018. Before that
  date the effective fed funds rate (`DFF`) is spliced in. FRED reports
  percent, so values are divided by 100. Column `short_rate`.

### Storage (call it **s**)

- A flat **0.25% a year** for vaulting and insurance. **This is an
  assumption, not data**, because no free public series exists. Column
  `storage_rate_assumed`.

### Three calendar terms

- **First notice day (FND):** the last business day of the month *before* the
  delivery month. From that day, anyone still holding a contract to buy can
  be handed metal. Financial holders who do not want metal close out before it.
- **Roll:** selling the contract that is about to expire and buying the next
  one. This is how a position stays open past FND.
- **τ (tau):** calendar days from today to the contract's FND. Column
  `days_to_first_notice`.

---

## 2. Why the spread is not zero even when nothing is wrong

There are two ways to own gold in New York τ days from now:

1. Borrow S dollars today, buy London gold, store it, and wait. Cost at τ:
   S · (1 + (r + s) · τ/365).
2. Buy a futures contract today at F, and pay F at τ.

If these cost different amounts, someone earns riskless profit. So

$$F = S\left(1 + (r + s - \ell)\,\frac{\tau}{365}\right) + P$$

This adds two terms to the textbook formula:

- **ℓ, the gold lease rate.** Someone who owns gold can lend it out and earn ℓ,
  which lowers their cost of holding it. **This is covered interest parity
  with gold as the foreign currency and ℓ as its interest rate.** When London
  runs short of physical metal, ℓ rises.
- **P, the premium for being in New York rather than London**, in dollars.
  P bundles three things:
  - **place:** location risk, or tariff risk;
  - **form:** COMEX takes 100-oz or kilo bars, London trades 400-oz bars;
  - **trust:** an exchange warrant versus a claim on a bank.

  In calm markets, arbitrage holds P near zero.

**The thing to hold onto: P is a level, paid once, not a rate paid each year.**
A tariff risk does not care whether a contract expires in 10 days or 100.
Carry does. Sections 4 and 5 turn on this distinction.

The project has no lease-rate series. GOFO, the published benchmark, was
discontinued in 2015. So ℓ is never observed and ends up inside whatever gets
measured.

---

## 3. Why F − S can't be used directly

`basis_usd = F − S` is the number traders quote. Two things contaminate it.

**It scales with the gold price.** Gold went from about \$1,160 in 2015 to
over \$4,500 in 2026. The same proportional gap is roughly four times as many
dollars at the end of the sample as at the start.

**It saws up and down with the delivery calendar.** Every day the contract
being priced moves closer to expiry. Then the market rolls into a later
contract. In the data:

- the roll happens a median **10 days** before FND (range 7–16);
- the new contract starts with a median **70 days** left (range 64–135; the
  long ones are when October is skipped).

Carry is proportional to τ. On 29 Jan 2025 (S = \$2,756, carry 4.60%), pure
carry was **\$21.19/oz at 61 days** but only **\$3.47 at 10 days**. The swing
comes from nothing but the calendar, and it is as large as the episodes the
project is trying to measure.

The project has two fixes. Version 1 is older and still feeds some outputs.
Version 2 is newer and feeds the mechanism figures and the kink estimate.

---

## 4. Version 1: the front-month implied rate

**Code:** `src/build_efp_from_databento.py` → `data/processed/efp_dislocation_v2.csv`
**Used by:** `src/analysis_tariff_episode.py` (the episode table) and
`src/make_paper_figures.py` (`fig2_basis`, `fig6_kink`)

### Steps

1. **Contract-by-day table.** Parse each symbol into its delivery month. Set
   FND to the last weekday of the month before (exchange holidays are
   ignored). Compute τ. Drop spread symbols such as `GCJ5-GCV5`.
2. **One contract per day.** Among contracts with τ > 0 and a settlement,
   keep the one with the most open interest. This puts the roll wherever the
   market actually rolls, rather than on a date chosen by hand.
3. **Line up the dates.** Inner-join to the LBMA price, so both markets must
   be open. This drops **178 of 3,035 weekdays**, mostly Christmas, New Year,
   4 July and Juneteenth. Left-join the rate and carry it forward across
   non-publication days.
4. **Compute:**

| Column | Formula | Meaning |
|---|---|---|
| `basis_usd` | F − S | raw spread, \$/oz |
| `implied_rate` | (F/S − 1) · 365/τ | the annual financing rate the spread implies |
| `carry_rate` | r + 0.0025 | what that rate should be |
| `dislocation` | implied_rate − carry_rate | what is left, per year (decimal) |
| `carry_implied_basis_usd` | S · carry_rate · τ/365 | pure carry in \$/oz |
| `excess_basis_usd` | basis_usd − carry_implied_basis_usd | what is left, in \$/oz |

5. **Downstream.** Drop days with τ < 20, which is **14% of the sample**.
   Then take episode means (`analysis_tariff_episode.py`) or calendar-month
   means (`make_paper_figures.py`).

### Worked example: 29 Jan 2025, contract GCJ5

| Step | Value |
|---|---|
| F, COMEX settlement | \$2,793.50 |
| S, LBMA PM | \$2,756.30 |
| τ | 61 days |
| basis | 2,793.50 − 2,756.30 = **\$37.20** |
| F/S − 1 | 37.20 / 2,756.30 = 1.350% |
| implied rate | 1.350% × 365/61 = **8.08%** |
| carry | 4.35% SOFR + 0.25% storage = **4.60%** |
| dislocation | 8.08% − 4.60% = **3.48 pp a year** |
| carry in dollars | 2,756.30 × 4.60% × 61/365 = \$21.19 |
| excess basis | 37.20 − 21.19 = **\$16.01/oz** |

### What this fixes, and what it breaks

Plug the Section 2 identity into the formula:

$$\text{dislocation} = \frac{F/S - 1}{\tau/365} - (r+s) = \frac{P}{S}\cdot\frac{365}{\tau} \;-\; \ell$$

- **Carry cancels exactly.** Carry no longer produces a sawtooth, and the
  zero-rate years compare cleanly with the 5% years. This part works.
- **The premium gets multiplied by 365/τ.** Annualising only makes sense for
  something that builds up over time, and P does not. A *constant* premium
  therefore recreates the sawtooth, pointing the other way, and blows up as
  τ → 0. On 8 Aug 2025 the excess was \$49.24 on a \$3,394 spot, or **1.45%
  of spot**. At that day's τ of 112 it reads as a 4.7% dislocation. The same
  premium would read **17.7% at 30 days and 53% at 10**.
- **Measurement noise behaves the same way.** The noise from the clock
  mismatch (Section 6) is a dollar level too. In calm 2019, the day-to-day
  standard deviation of the dollar excess is about the same at every τ
  (\$4.6–7.6). The standard deviation of the dislocation falls from **9.4 pp
  at τ = 7–19 to 2.1 pp at τ = 70–130**. `FIGURE_PLAN.md` records a 42%
  implied rate on 12 Nov 2025 at τ = 16. That number comes from this divisor,
  not from the market.

Dropping days with τ < 20 hides the worst of the symptom but leaves the
scaling in place.

> **This qualifies an instruction in `CLAUDE.md`.** The rule "never regress on
> the raw dollar spread; convert to an implied rate" is right for the carry
> part of the spread and wrong for the premium part. Annualising removes one
> calendar artefact and adds another. Three outputs are built on the version 1
> `dislocation` column and inherit the problem: the episode table in
> `analysis_tariff_episode.py`, the lower panel of `fig2_basis`, and that
> figure's "tariff episode: mean 1.2% p.a." annotation. Their episode rankings
> should be rechecked against version 2.

---

## 5. Version 2: the constant-maturity 90-day spread

**Code:** `constant_maturity()` in `claude/mechanism-figures/validate_mechanism.py`
**Used by:** `build_figure_data.py` (mechanism Figures 2–4) and `estimate_kink.py`

**The idea.** On any day, the contracts together trace out a term structure:
a yield curve for New York gold. Version 1 reads one point on that curve, and
that point's maturity keeps drifting. Version 2 fits the whole curve and
always reads it at **the same maturity, 90 days**. With τ fixed, neither
calendar artefact can appear.

### Steps

1. **Pick the contracts for the fit.** Keep contracts with 15 ≤ τ ≤ 400, at
   least 1,000 contracts of open interest, and a settlement. A contract with
   under 15 days left is in its delivery scramble. Far-dated or thinly held
   contracts have stale settlements. What remains is a median of **6
   contracts a day** (range 4–9).
2. **Fit a straight line in logs** by weighted least squares, weighting each
   contract by √(open interest):
   $$\ln F_i = a + b\,\tau_i$$
   Logs are used because with continuous compounding F(τ) = F₀ · exp(c·τ), so
   ln F is linear in τ. exp(a) is the curve's New York "spot" price and b is
   New York's daily carry rate. The weights stop a thinly traded contract
   from tilting the line.
3. **Read the curve at 90 days:** F₉₀ = exp(a + 90b).
4. **Apply the same algebra as version 1, with τ fixed at 90:**
   - `implied_rate` = (F₉₀/S − 1) · 365/90
   - `disloc` = implied_rate − (r + s), and `disloc_pp` = disloc × 100
   - `excess_usd` = disloc · 90/365 · S, which is what is left in \$/oz over
     the 90 days
5. **Smooth for plotting.** `disloc_pp_10d` is a 10-session rolling mean that
   needs at least 6 sessions. It is the line readers follow in Figure 2.
6. **Go monthly.** Take calendar-month means of the *unsmoothed* daily
   `disloc_pp` and `excess_usd`. Merge them with Swiss customs tonnes shipped
   to the US (`swiss_tonnes()`). This monthly panel feeds the hinge buckets
   and the kink regression.

### Worked example: 29 Jan 2025 again

These contracts go into the fit:

| Contract | τ (days) | Settle | Open interest |
|---|---:|---:|---:|
| GCH5 | 30 | 2,781.5 | 10,232 |
| GCJ5 | 61 | 2,793.5 | 346,145 |
| GCM5 | 121 | 2,818.7 | 52,333 |
| GCQ5 | 183 | 2,842.9 | 20,068 |
| GCV5 | 244 | 2,867.2 | 3,754 |
| GCZ5 | 303 | 2,890.9 | 12,905 |

Left out: GCG5, which has 128k contracts open but τ = 2 and is already in
delivery; GCG6, with only 489 contracts; and every later contract.

| Step | Value |
|---|---|
| fitted line | exp(a) = \$2,769.38; b = 0.0001429 a day (**5.22% a year**) |
| F₉₀ | 2,769.38 × exp(90 × 0.0001429) = **\$2,805.23** |
| F₉₀/S − 1 | 2,805.23 / 2,756.30 − 1 = 1.775% |
| implied rate | 1.775% × 365/90 = **7.20%** |
| dislocation | 7.20% − 4.60% = **2.60 pp** |
| excess | 2.60% × 90/365 × 2,756.30 = **\$17.66/oz** over 90 days |
| 10-session mean that day | 3.56 pp |

Version 1 gave 3.48 pp for the same day.

### Why this works, in the same algebra

$$\text{disloc} \approx \frac{P}{S}\cdot\frac{365}{90} \;-\; \ell$$

The multiplier on P is now a constant, 4.06, so P no longer creates a
sawtooth. A dislocation of 1 pp simply means a New York premium of about 0.25%
of spot, net of the lease rate.

### A free extra: the fit separates level from slope

The two fitted numbers line up with the two kinds of wedge in Section 2. The
intercept is a level gap; the slope is excess carry.

| | 29 Jan 2025 | 3 Jun 2019 (calm) |
|---|---|---|
| **Level:** exp(a) − S | \$13.08 (0.47% of spot) → 1.92 pp | \$5.70 (0.43%) → 1.75 pp |
| **Slope:** 365·b − carry | 5.22% − 4.60% = +0.62 pp | 2.45% − 2.65% = −0.20 pp |
| compounding cross-term | +0.06 pp | +0.02 pp |
| **dislocation** | **2.60 pp** | **1.57 pp** |

The code does not use this split yet. The calm-day column is a warning. A
\$5.70 "premium" on a day when nothing happened is the clock mismatch from
Section 6 showing up in the data. One day's intercept is noisy, which is why
the figures rely on multi-day means.

### The two versions through the tariff episode

Monthly means, pp a year:

| Month | Version 1 (τ ≥ 20) | Version 2 (90-day) |
|---|---:|---:|
| Nov 2024 | 0.32 | −0.03 |
| Dec 2024 | 1.24 | 0.74 |
| Jan 2025 | 4.05 | 2.83 |
| Feb 2025 | 1.26 | 1.06 |
| Mar 2025 | −0.58 | 1.17 |
| Apr 2025 | −0.37 | −0.39 |

The two versions have opposite signs in March 2025. That is the month to check
first when anyone reruns results built on version 1.

---

## 6. Timing issues, in one place

1. **The two prices are not taken at the same moment.** The LBMA PM is set at
   15:00 London. COMEX settles at 13:30 New York, which is 18:30 London most
   of the year (17:30 in the few weeks when the US and UK change clocks on
   different dates). **The gap is about 3.5 hours.** Any move in gold during
   that window shows up as spread. At the 90-day horizon, a 1% intraday move
   adds 1% × 365/90 ≈ **4 pp** of false dislocation for that day.

   > **Correction.** `RESEARCH_DOSSIER.md` §6 and the "Timestamp mismatch"
   > item in `gold_tariff_episode.tex` put this gap at "roughly ninety
   > minutes". That is wrong. The later notes in `claude/mechanism-figures/`
   > have it right. The fix is item 1 in `NEXT_STEPS.md` and costs nothing:
   > take the COMEX intraday price at 15:00 London, which Databento already
   > supplies, instead of the settlement.

2. **Day-count mismatch.** The implied rate uses a 365-day year. SOFR is
   quoted on a 360-day year, so on the same basis it is about 365/360 higher:
   4.35% becomes 4.41%. This overstates the dislocation by roughly **0.06 pp**
   at 2025 rates and by almost nothing at zero rates. It is not corrected,
   and it is small next to the episodes.
3. **Horizon mismatch in the rate.** Carry uses *overnight* SOFR against a
   90-day (or τ-day) horizon. When markets expect rate cuts, the 90-day rate
   sits below the overnight rate. Carry is then overstated and the
   dislocation understated by the difference. This is neither corrected nor
   measured here. Using a term rate of matching maturity would fix it.
4. **FND ignores exchange holidays.** τ can be off by 1–2 days. This only
   matters for version 1 at short τ.
5. **Holidays are dropped, not filled.** Charts must show them as gaps.
   `build_figure_data.py` inserts break markers wherever a gap exceeds 7 days.
6. **Monthly alignment.** Each month is a calendar-month mean of daily values,
   matched to the customs month in which the shipment was recorded.
   `validate_mechanism.py` finds that same-month correlation beats a one-month
   lag. That fits a Zurich–New York shipment being recorded when it leaves.

---

## 7. What the dislocation does and does not measure

- **It nets two forces with opposite signs.** Dislocation ≈ New York premium
  − London lease rate. A rich New York pushes it up. A London short of metal
  raises ℓ and pushes it down. The dossier quotes secondary-source lease
  rates rising from 0.08% to 4.5% in January 2025. If those figures are right,
  both forces were at work, and **the measured dislocation understated New
  York's premium by up to the lease rate.** The two cannot be separated
  without a lease-rate series. This point follows from the algebra, not the
  data, but it matters for any reading of the tariff episode as "a small
  dislocation".
- **The three parts of P are not separated.** Place, form and trust all sit
  inside P. `CLAUDE.md` already concedes that trust is not separately
  identifiable.
- **It is a proxy, not a real Exchange for Physical (EFP).** An EFP is a
  privately negotiated swap of a futures position for London metal. Dealers
  quote EFPs on entitlement-gated Bloomberg pages. This series is a
  settlement price minus an auction price, built to stand in for one.
- **The unit of the flow threshold is still open.** Freight and insurance cost
  dollars per ounce, which argues for measuring the threshold in `excess_usd`.
  `estimate_kink.py` fits both units. Over its 2023–26 estimation window the
  rate version fits better (R² 0.52 vs 0.38). The full-sample comparison is in
  `claude/mechanism-figures/kink_output.txt`.

---

## 8. Cheat sheet

| Symbol | What it is | Column | Source |
|---|---|---|---|
| S | London price, 15:00 London | `lbma_pm_usd` | LBMA JSON |
| F | COMEX settlement, 13:30 New York | `settle` / `comex_settle` | Databento, stat 3 |
| OI | open interest | `open_interest` | Databento, stat 9 |
| τ | days to first notice | `days_to_first_notice` | from the contract symbol |
| r | SOFR (DFF before Apr 2018) | `short_rate` | FRED |
| s | storage, 0.25%/yr | `storage_rate_assumed` | assumption |
| F₉₀ | fitted curve at 90 days | `f90` | version 2 |
| — | dislocation | `dislocation` (v1, decimal) · `disloc_pp` (v2, pp) | derived |
| — | what is left over carry, \$/oz | `excess_basis_usd` (v1) · `excess_usd` (v2, over 90 days) | derived |

Reproduce every number, from the repo root:

```
.venv/Scripts/python.exe claude/spread-explainer/worked_examples.py
```
