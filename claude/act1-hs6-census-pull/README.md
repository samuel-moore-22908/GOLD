# Act I, step 2 — the HS6 Census pull

Pulls the US bilateral trade panel at HS6 that the Grubel–Lloyd analysis runs on.

| File | What it does |
|---|---|
| `code/00_bootstrap.py` | **Standard library only.** Rebuilds every reference list from four public URLs |
| `code/01_probe_census_api.py` | Settles the three things you can't learn from docs, before the bulk loop |
| `code/01b_build_worklist.py` | Same plan via the concordance spreadsheets, plus the chunk-mode probe |
| `code/02_pull_hs6_panel.py` | Executes the plan: resumable bulk pull, two tiers, plus consolidation |

## Starting from nothing, on a machine with no repository

`00_bootstrap.py` is the whole starting point. **No pandas, no requests, no openpyxl, no
repo** — if you can run Python and reach `census.gov`, it reproduces all four reference
files. Nothing is transcribed by hand, which matters because the commodity universe is
5,630 codes.

Four public URLs, none needing a key:

```
https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.json
https://api.census.gov/data/timeseries/intltrade/exports/hs/variables.json
https://www.census.gov/foreign-trade/schedules/b/2026/imp-code.txt
https://www.census.gov/foreign-trade/schedules/b/2026/exp-code.txt
https://www.census.gov/foreign-trade/schedules/c/country.txt
```

Expected output — check these, and stop if yours differ, because it means a source layout
changed:

```
variables  70 valid on imports, 41 on exports; all 42 chosen fields resolve
commodities  5,630 HS6 across 98 chapters
countries    241 individual codes
worklist_gold.csv          106 requests, longest predicate   377 chars
worklist_universe.csv   11,342 requests, longest predicate 1,049 chars
```

`01b_build_worklist.py` builds the identical worklist from the concordance spreadsheets
instead — verified to agree exactly at 5,630 / 98 / 241. Use it when pandas is available
and you want the chunk-mode probe, and note that the concordance files carry the end-use,
SITC and NAICS mappings that Act V needs later. `00_bootstrap.py` is the dependency-free
path to the same plan.

## Why the code files are plain text, not the spreadsheets

`imp-code.txt` and `exp-code.txt` are the fixed-width editions of HTSUS and Schedule B.
That they disagree at **ten** digits — 20,393 import lines against 9,779 export lines — is
not a defect to reconcile. HTSUS subdivides wherever a duty rate differs, and the United
States constitutionally cannot tax exports, so Schedule B never had a reason to. That 2:1
ratio is the reason bilateral Grubel–Lloyd has to be computed at **HS6**: it is the finest
level at which both systems describe the same object.

## Countries are not an iteration dimension

The most expensive mistake available here. `SUMMARY_LVL=DET` returns **every partner in a
single response**, so looping over countries multiplies the call count by ~230 and returns
exactly the same data. The chunk key is `(flow, month, chapter)` and nothing else.

The Schedule C country list is still pulled, for two jobs that happen *after* the data
arrives: validating that nothing but individual countries came back (a grouping leaking
past `SUMMARY_LVL` would double-count everything, silently), and joining names on without
carrying `CTY_NAME` through sixteen million rows.

**Untested against the live API** — `api.census.gov` rejects unkeyed requests and I had no
key. Field names, however, are *not* guesses: they were read from the endpoints' own
`variables.json` (public, no key) on 27 Aug 2026. Run the probe first.

## Run order

```bash
# 1. get a key: api.census.gov/data/key_signup.html  (usually instant)
export CENSUS_API_KEY=...

# 2. build every reference list. Standard library only; needs no key.
python claude/act1-hs6-census-pull/code/00_bootstrap.py

# 3. probe. read the report before going further.
python claude/act1-hs6-census-pull/code/01_probe_census_api.py

# 4. optional: same plan via the concordance route, plus the chunk-mode probe
python claude/act1-hs6-census-pull/code/01b_build_worklist.py --probe-chunk-mode

# 5. set CHUNK_MODE in 02_pull_hs6_panel.py from what the probe reported

# 6. gold tier first — 106 chunks, ~3 minutes, and it proves the whole path works
python claude/act1-hs6-census-pull/code/02_pull_hs6_panel.py --tier gold

# 7. universe tier — 11,342 chunks, ~4.5 hours. Resumable; rerun after any failure.
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
