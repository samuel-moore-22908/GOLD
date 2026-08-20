# Gold flow deconvolution

Research project. Separating financial relocation from real absorption in
international gold trade statistics, 2019–2026. Output is a short paper.

**Hypothesis to test:** gross bilateral gold trade substantially overstates
real gold movement, and the wedge is identifiable using vault inventory data
plus the COMEX–London basis. If it holds, the payoff is that phantom flows
demonstrably contaminated a US tariff calculation and a Federal Reserve GDP
nowcast — which is the reason the paper matters beyond data hygiene.

Nothing here is established yet. Treat every quantitative claim as open until
it comes out of primary-source data.

---

## Framing

Use a three-way taxonomy, not a binary. "Financial noise vs. legitimate"
invites pushback because central bank buying is neither.

| Category | Definition |
|---|---|
| **Absorption** | Metal permanently leaves the tradeable float — jewellery, retail bar/coin, industrial, central bank reserves |
| **Relocation** | Metal moves between financial vaults, same ultimate owner — LBMA ↔ COMEX ↔ ETF |
| **Transformation** | Form or location changes, no ownership change — 400 oz recast to 100 oz in Switzerland |

Relocation and transformation are the target. Transformation matters
separately because it *doubles* the recorded trade footprint of a single
relocation.

## Scope

Five countries. **US, UK, Switzerland** (the arbitrage triangle) plus
**China, India** (absorption sinks). Monthly, 2019–2026.

Turkey, UAE, Hong Kong and Singapore belong in a robustness appendix, not the
main analysis. Resist scope expansion — this is a short paper.

---

## Reference documents

| File | Contents |
|---|---|
| `DATA_SOURCES.md` | Where to get everything. Access routes, cost, coverage, gotchas. Read before any data task. |
| `RESEARCH_DOSSIER.md` | Methodology, EFP mechanics, literature. **Its results section is exploratory scratch work — do not build on those numbers.** |

---

## Conventions

- **Tonnes, not troy ounces.** Convert at the boundary. 1 t = 32,150.7 oz.
  Mixed units are the most common silent error in this literature.
- **Monthly frequency throughout.** The phenomenon lives at monthly
  frequency; annual aggregation erases it entirely.
- **Tag every observation with provenance** — directly reported by a primary
  source vs. derived from an aggregate. Revisions to published aggregates
  must be traceable to the cells they move.
- **National customs over Comtrade.** Monthly, mass units, better re-export
  handling.
- Reproducible scripts over notebook state.

---

## Specification pitfalls

These are structural properties of the instruments, not empirical findings.
They hold regardless of what the data turns out to say.

**The roll sawtooth.** `GC1 Comdty` is the generic front month; COMEX gold
delivers Feb/Apr/Jun/Aug/Oct/Dec, so time-to-delivery cycles from ~2 months
to zero and back. Carry scales with it. At 4.5% financing on $4,400 gold that
is a ~$33/oz sawtooth driven purely by the delivery calendar — comparable in
magnitude to the dislocations being hunted. **Never regress on the raw dollar
spread.** Convert to an implied rate:

```
implied_rate = (GC1 / XAU - 1) * 365 / days_to_delivery
dislocation  = implied_rate - (SOFR + storage_rate)
```

This also makes the near-zero-rate era comparable to the 4–5% era, which a
fixed dollar threshold cannot do.

**The relationship is kinked, not linear.** Arbitrage triggers only above
all-in transfer cost — freight, insurance, recasting, transit financing.
Below that, nothing moves. Specify a hinge:

```
flow ~ beta * max(0, EFP - carry - transfer_cost)
```

Estimate the kink rather than assuming it. Its value is publishable on its
own — transatlantic gold transfer cost has not been cleanly estimated.

**Sign is directional.** Above carry → New York rich → metal flows west.
Below carry → New York cheap → metal flows east. Both regimes occur in the
sample window. Any specification must handle both.

**Four things sit inside `GC1 Comdty - XAU Curncy`:** time (carry, always
present), place (location risk), form (400 oz vs 100 oz bars), and trust
(exchange warrant vs unallocated claim). Arbitrage pins the last three near
zero in calm markets. The trust layer is probably not separately
identifiable — acknowledge that rather than attributing the whole residual to
location risk.

**Monetary gold is invisible in trade data.** Excluded by BPM6 convention.
Central bank flows must come separately from IMF IFS.

**Re-exports sit inside export figures** in Comtrade. Fatal for Switzerland,
UK, Hong Kong, UAE, Singapore, Turkey. Hong Kong is one of the few sources
that reports them separately.

---

## Open conceptual problem

**The correction factor is asymmetric and its net direction is unknown.**
Round-tripping through Swiss recasting records four trade legs per tonne
relocated. But metal already inside the US, re-warranted as COMEX-eligible,
records *zero* cross-border trade. So trade statistics overstate relocation
in some directions and miss it entirely in others. A single multiplier cannot
be correct. This is the deepest unresolved question in the project and
probably where the contribution is.

---

## Ruled out

- **20-country dynamic MFA.** Gold's stock-to-flow ratio near 60 means the
  base-year assumption dominates any result; flows barely move it. Evaluated
  and rejected. Reasoning in the dossier.
- **Annual Comtrade.** Destroys the phenomenon.
- **Weibull lifetime distributions for jewellery outflow.** Jewellery
  hibernates and returns on price and liquidity shocks, not wear-out.
- **Coefficient of variation as a corridor classifier.** Near-zero months
  compress it, so relocation corridors can score below consumption corridors.
  Prefer max/min ratio, or correlation with the basis versus correlation with
  local-currency price.

---

## Build order

1. **CME daily warehouse stocks** — registered and eligible kept separate;
   reclassification between them is a phantom signal in its own right.
2. **Swiss-Impex monthly by partner** — the core flow series.
3. **EFP series** — CME settlements minus LBMA PM, converted to implied rate.
   Control the roll convention explicitly.
4. **LBMA monthly vault holdings** plus Bank of England — for the sourcing
   reconciliation.
5. **US Census and HMRC monthly HS 7108** — the other two legs of the
   triangle.
6. **WGC Goldhub country demand** — the absorption benchmark flows are
   tested against.
7. Event dummies from primary sources: CBP CROSS rulings database, Federal
   Register, CBIC notifications for the India duty change.

---

## Working style

- Charts must show data gaps as gaps. No silently skipped periods, no solid
  lines drawn across long interpolations.
- When a result contradicts something asserted earlier in this project, say
  so explicitly rather than quietly correcting it. The record of what failed
  is part of the output.
- Distinguish reported figures from derived ones in prose, not just in the
  data.
