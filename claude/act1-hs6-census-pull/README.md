# Act I, step 2 — the HS6 Census pull

Pulls the US bilateral trade panel at HS6 that the Grubel–Lloyd analysis runs on.

| File | What it does |
|---|---|
| `code/01_probe_census_api.py` | Settles the three things you can't learn from docs, before the bulk loop |
| `code/02_pull_hs6_panel.py` | The resumable bulk pull, two tiers, plus consolidation |

**Untested against the live API** — `api.census.gov` rejects unkeyed requests and I had no
key. Field names, however, are *not* guesses: they were read from the endpoints' own
`variables.json` (public, no key) on 27 Aug 2026. Run the probe first.

## Run order

```bash
# 1. get a key: api.census.gov/data/key_signup.html  (usually instant)
export CENSUS_API_KEY=...

# 2. drop the concordance files into output/ — they supply the HS6 code universe offline
#    https://www.census.gov/foreign-trade/reference/codes/concordance/
#      impconcord26.xlsx, expconcord26.xlsx

# 3. probe. read the report before going further.
python claude/act1-hs6-census-pull/code/01_probe_census_api.py

# 4. set CHUNK_MODE in 02_pull_hs6_panel.py from what the probe found

# 5. gold tier first — 106 chunks, ~3 minutes, and it proves the whole path works
python claude/act1-hs6-census-pull/code/02_pull_hs6_panel.py --tier gold

# 6. universe tier — 10,494 chunks, ~4.5 hours. Resumable; rerun after any failure.
python claude/act1-hs6-census-pull/code/02_pull_hs6_panel.py --tier universe

# 7. fold per-chunk parquet into one table per tier
python claude/act1-hs6-census-pull/code/02_pull_hs6_panel.py --consolidate
```

## Design decisions worth knowing

**Window starts 2022-01, not 2015-01.** HS6 codes are revised every five years and both
HS2017 and HS2022 fall inside a 2015–2026 sample — roughly a tenth of subheadings change.
HS2022 entered force 1 Jan 2022, so starting there keeps the panel inside a single HS
edition and removes the correlation-table work entirely. Both DiD windows (pre
2023-06..2024-11, post 2024-12..2026-05) sit inside it with 35 months of pre-period to
spare. Keep the long 2015–2026 history only for the rolling-series figure, at HS2 or for
gold alone, where continuity can be hand-checked.

**Two tiers.** The universe pull carries six lean fields; country names and long
descriptions repeat on every one of ~16m rows and are cheaper to join afterwards. Chapter
71 is pulled again with a wider set — four HS6 codes, so the width is free.

**`time` is the date predicate, not `YEAR`/`MONTH`.** The endpoint metadata marks `time`
as required and predicate-only; `YEAR` and `MONTH` exist as output columns.

**`SUMMARY_LVL=DET`** drops country-grouping rows. This is the fix for the aggregate
double-counting trap — cleaner than filtering `CTY_NAME` for "TOTAL" afterwards. The chunk
validator re-checks it on every response, because a silent failure there would inflate
everything.

**Quantity fields are named asymmetrically:** imports use `GEN_QY1_MO`, exports use
`QTY_1_MO`. Only imports carry charges and duty.

## Two fields worth the wider gold tier

Found in the endpoint metadata, and both replace assumptions in the cost ledger:

- **`AIR_CHA_MO` / `AIR_WGT_MO`** — air charges and air shipping weight, by partner, by
  code, by month. Bullion moves by air, so `charges ÷ weight` is a *measured* freight and
  insurance cost per kilogram. Tier I of the ledger currently assumes $0.30–1.00/oz for
  this. Note charges exist on the import side only (US export stats are FAS), so the
  eastbound leg still needs the assumption.
- **`CAL_DUT_MO`** — calculated duty. Lets you show from the primary source that duty
  collected on the gold lines was zero throughout, rather than asserting it.

`RP` (rate provision code) may indicate which tariff provision applied, including Chapter
99 special provisions. Unverified — worth a look during the probe.

## Open questions the probe resolves

1. **How to chunk.** Whether the commodity predicate takes a prefix, a wildcard, a
   comma-separated list, or only exact codes. The script supports all four; set
   `CHUNK_MODE` from the report.
2. **General vs consumption imports.** `GEN_*` includes goods entering bonded warehouses
   and foreign trade zones; `CON_*` is goods entering the economy. For gold that gap is
   potentially load-bearing — metal in a bonded warehouse is the phenomenon under study.
   The probe reports both for chapter 71. If they diverge for gold and not elsewhere,
   that is a finding, not a nuisance.
3. **Chunk size**, which determines runtime and disk.

## Next: reconciliation (step 3)

Do not compute a single GL until the pull reproduces two known targets:

- **2024 US–Switzerland totals**, summed from the pull: imports **$63.42bn**, exports
  **$24.93bn**.
- **US–CHE gold GL**, which should come out at mean monthly **0.359** and full-window
  **0.876** on 2015–2026 value data.

Both are already on disk from the previous iteration. If the pull doesn't reproduce them,
stop and find out why.
