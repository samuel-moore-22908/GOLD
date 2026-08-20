# Deconvolving gold trade flows: working notes

Scratch analysis, not a paper. Data assembled Aug 2026 from public reporting of
Swiss customs, CME COMEX, LBMA and WGC figures. Every number carries a
provenance flag in `gold_raw_data.csv` — `reported` means a source stated it
directly, `derived` means I backed it out of a stated aggregate.

## What I could and couldn't get

The sandbox network is restricted to package registries, so I could not hit
Swiss-Impex, HMRC, CME or LBMA directly. Everything here was assembled from
figures quoted in public reporting. That means:

- **Solid**: the Swiss→US monthly series Dec 2024–Aug 2025, COMEX inventory at
  six dated points, the LBMA Dec–Jan drawdowns, the Swiss trade values.
- **Sparse**: EFP spread (3 observations), lease rates (4), Swiss→India/UK/Turkey
  (3–5 each).
- **Missing entirely**: Sep–Oct 2025 and Jan–Mar 2026 US-bound Swiss flows;
  any COMEX observation between Apr 2025 and Jul 2026.

That last gap is the biggest weakness. The unwind is currently a straight line
between two points 15 months apart. Pulling CME daily warehouse reports would
fix it in an afternoon and should be the first thing done.

## Headline result

Of roughly **871 t** that entered COMEX vaults between the US election and the
4 April 2025 peak:

| | tonnes | share |
|---|---|---|
| Relocation (address change, no owner change) | ~823 | 94.5% |
| Plausible US absorption | ~48 | 5.5% |

The absorption bound uses Ross Norman's figure of ~115 t/yr of typical US
physical coin and bar consumption. At the peak, COMEX vaults held **12.2 years**
of that segment's demand. There is no consumption story that explains this.

If the whole build round-tripped through Swiss recasting — four recorded legs
per tonne (UK→CH→US out, US→CH→UK back) — it generated on the order of
**3,480 t of recorded cross-border trade against approximately zero change in
world gold ownership**. That is 0.70× a full year of global gold supply.

## The finding I didn't expect

**Switzerland and London together don't account for the COMEX build.**

Election → 29 Jan 2025:
- COMEX build: 393 t
- LBMA London drawdown: 181 t → **46%** of the build
- Swiss exports to US: 263 t → 67%

Election → peak (4 Apr 2025):
- COMEX build: 871 t
- Swiss exports to US: 532 t → 61%
- **Unsourced residual: 339 t (39%)**

This cuts against the "London is being drained" narrative that dominated
coverage in early 2025. Less than half the New York build came out of London
vaults. Candidate sources for the residual: direct UK→US shipments of
already-conforming bars, non-Swiss refiners (Perth, Canada, UAE), US domestic
mine and refinery output diverted to vault, and — importantly — **existing US
private vault stock simply re-warranted as COMEX-eligible**.

That last channel records *no cross-border trade at all*. Which means the
relationship between trade statistics and physical relocation is not a clean
inflation factor. Trade data overstates in some directions and misses relocation
entirely in others. Any correction factor has to be asymmetric.

## Lead-lag: the practically useful bit

| month | Swiss→US (t) | spread state |
|---|---|---|
| Nov 2024 | 5.8 | not yet open |
| Dec 2024 | 64.2 | opens >$50 |
| Jan 2025 | 192.9 | peaks ~$64 |
| Feb 2025 | 152.8 | compressing |
| Mar 2025 | 103.3 | |
| Apr 2025 | 12.7 | exemption, spread gone |

Physical flow lags the spread by roughly one month — the recast-and-fly cycle.
**The EFP spread is a leading indicator of the phantom component of next month's
trade print.** That is the most exploitable result here and probably the paper's
main practical contribution.

## Where I was wrong

I claimed in advance that a coefficient of variation above ~1.5 would flag a
relocation corridor. My own data contradicted it: the US corridor scored
**CV = 1.31**, below my invented threshold, because near-zero months drag the
mean down. CV is the wrong statistic.

Max/min ratio separates cleanly instead:

| corridor | max/min | reading |
|---|---|---|
| United States | 964× | relocation |
| United Kingdom | 53× | mixed transit/relocation |
| India | 4.2× | consumption |

Better still, and untested here: correlation with the EFP spread versus
correlation with local-currency gold price. Consumption corridors should
respond to the latter, relocation corridors to the former. Needs the daily
spread series.

## The policy hook holds up

Swiss gold exports to the US, by value:

- H1 2024: CHF 1.7 bn
- H1 2025: CHF 39.0 bn (**23×**), of which CHF 37.6 bn in Q1 alone
- Q2 2025: CHF 1.6 bn — collapse immediately after the April exemption

For scale, all *non-gold* Swiss exports to the US in full-year 2025 were
CHF 54.7 bn. So six months of bullion-in-transit equalled **71%** of a full
year of actual Swiss commerce with America.

The 39% tariff rate was reportedly calibrated on 2024 trade-deficit data, a year
Swiss officials called atypical precisely because of gold. A bilateral goods
balance that counts non-monetary bullion moving between vaults is measuring
vault location, not trade.

## The 2020 analogue

April 2020: Switzerland shipped 111.7 t to the US — 85% of all its gold exports
that month, against a normal US take of under 1 t. Same mechanism (EFP
dislocation → London-to-NY relocation), different trigger (pandemic freight
disruption vs tariff risk). January 2025 was 1.73× that peak month.

Two episodes five years apart with an identical signature is enough to fit on
one and validate on the other. That's the cleanest available identification
and it costs nothing extra.

## Next steps, in order of value

1. **CME daily warehouse reports** — fills the 15-month hole, converts the
   unwind from a line segment into a series. Highest value per hour.
2. **Daily EFP spread** — COMEX front-month settle minus LBMA PM. Makes the
   lead-lag claim testable rather than illustrative.
3. **Swiss-Impex full monthly panel** by destination back to 2012 — gives ~40
   corridors × 170 months to run the classifier properly.
4. LBMA monthly vault series 2016– to close the sourcing reconciliation.
5. US Census monthly HS 7108 to get the export side directly rather than
   inferring tonnage from headline dollar values.

## Standing caveats

- US 2025 ETF demand was 437 t, taking holdings to 2,019 t. ETF metal is mostly
  vaulted in **London**, not COMEX, so it is a separate stock and does not
  justify the COMEX build. But this needs checking properly before the claim
  goes in a paper.
- Feb 2025 and May 2025 Swiss→US figures are residuals backed out of stated
  quarterly and half-year totals. If the underlying aggregates were revised,
  those two months move.
- Monetary gold is excluded from merchandise trade by BPM6 convention, so
  central bank flows are absent from everything here by construction. They must
  be added separately from IMF IFS.
