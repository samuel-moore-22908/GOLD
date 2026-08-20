# Gold

Separating financial relocation from real absorption in international gold
trade statistics, 2019–2026.

## The problem

When gold crosses a border, customs records a trade. But gold crosses borders
for two unrelated reasons: someone will *use or hold* it, or someone is
*moving it between vaults*. Trade statistics cannot distinguish these. At
roughly $150m per tonne, a few hundred tonnes of vault shuffling appears as
tens of billions of dollars of apparent commerce.

Between late 2024 and early 2026 the market ran this experiment at scale.
Tariff risk drove a large transatlantic relocation of bullion, then reversed
it. Three dated policy shocks generated substantial recorded trade with no
consumption content — a natural experiment for identifying the wedge between
gross trade flows and real gold movement.

## Hypothesis

Gross bilateral gold trade substantially overstates real gold movement, and
the wedge is identifiable using vault inventory data plus the COMEX–London
basis.

If it holds, the consequence is not merely cleaner data: the same phantom
flows appear to have contaminated a US bilateral tariff calculation and a
Federal Reserve GDP nowcast.

**Status: hypothesis stage.** No quantitative claim in this repository should
be treated as established until it comes out of primary-source data.

## Approach

A three-way taxonomy rather than a binary, since central bank buying is
neither noise nor consumption:

| Category | Definition |
|---|---|
| **Absorption** | Metal permanently leaves the tradeable float |
| **Relocation** | Metal moves between financial vaults, same ultimate owner |
| **Transformation** | Form or location changes, no ownership change |

Scope is five countries — US, UK and Switzerland as the arbitrage triangle,
China and India as absorption sinks — at monthly frequency.

## Repository contents

| Path | Contents |
|---|---|
| `CLAUDE.md` | Project context, conventions, specification pitfalls, build order |
| `DATA_SOURCES.md` | Full data source catalog: access routes, cost, coverage, gotchas |
| `RESEARCH_DOSSIER.md` | Methodology, EFP mechanics, literature review |
| `data/` | Raw data (not committed — see below) |
| `src/` | Analysis code |

## Data is not committed

Deliberately. Three reasons:

1. Most of it is freely re-fetchable from primary sources, and
   `DATA_SOURCES.md` documents exactly how.
2. Some sources are licensed or paid — WGC Goldhub requires registration,
   Metals Focus and goldchartsrus data are commercial. Redistributing them
   would breach their terms.
3. Published aggregates get revised. A committed snapshot silently goes stale;
   a documented fetch procedure does not.

Start with `DATA_SOURCES.md` §"Start here" for the six pulls that matter most.

## Key methodological notes

Three things that are easy to get wrong and expensive to discover late:

- **Never regress on the raw COMEX–London dollar spread.** The generic front
  month carries a sawtooth from the delivery calendar that is comparable in
  magnitude to the dislocations being measured. Convert to an implied rate
  first.
- **The spread-to-flow relationship is kinked, not linear.** Arbitrage
  triggers only above all-in transfer cost. Specify a hinge and estimate the
  threshold.
- **Any correction factor is asymmetric.** Round-tripping through Swiss
  recasting records four trade legs per tonne relocated; metal already inside
  the US and re-warranted as exchange-eligible records zero. A single
  multiplier cannot be correct.

Full detail in `CLAUDE.md` and `RESEARCH_DOSSIER.md`.

## Working with Claude Code

`CLAUDE.md` loads automatically at session start. Run `claude` from the
repository root; use `/memory` to confirm what loaded.
