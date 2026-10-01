# gold_final

Six files that build the four figures from nothing but two API keys and the
purchased Databento archives. Two pulls in Python, four cleaning-and-figure
scripts in Stata.

```
gold_final/
  code/      the six files
  data/      raw pulls and run logs - regenerate, not committed
  figures/   the four PDFs
  letter/    the write-up that uses them
  reference/ static inputs that can no longer be fetched - committed
```

`reference/lbma_gold_pm.json` is the London PM benchmark back to 1968. It is the
one data file in this project that is committed rather than pulled, because
prices.lbma.org.uk now sits behind Cloudflare and returns 403 to scripted
clients. A file a script can no longer fetch is an input, not a cache. Refresh
it by opening the URL in a browser, which Cloudflare passes, and saving the JSON
over it.

`letter/gold_letter.tex` is the write-up: a policy letter in the format of a
Chicago Fed Letter, roughly 4,100 words, using the four figures in order -
observe the flow, explain it, quantify the excess, then the consequences. Build
it with two passes of `pdflatex` (latexmk is avoided here: MiKTeX exits
non-zero on an unsupported Windows build even when the PDF is fine).

## Run order

```
python gold_final/code/pull_us_customs.py
python gold_final/code/pull_databento.py

.venv/Scripts/python.exe claude/stata-console/code/run_do.py gold_final/code/fig1_gold_panel.do
.venv/Scripts/python.exe claude/stata-console/code/run_do.py gold_final/code/fig2_spread_vs_hurdle.do
.venv/Scripts/python.exe claude/stata-console/code/run_do.py gold_final/code/fig3_counterfactual.do
.venv/Scripts/python.exe claude/stata-console/code/run_do.py gold_final/code/fig4_deficit_gold.do
```

The four do-files are independent of each other. Both pulls are idempotent:
they skip what is already on disk, so a rerun costs nothing and buys nothing.

## The six files

| File | What it does |
|---|---|
| `pull_us_customs.py` | Census API. Writes the HS4 universe, gold by heading back to 2015, gold by partner, and the FT-900 balance. |
| `pull_databento.py` | Decodes the Databento archives into the futures curve, computes the two daily instants, reduces the minute bars to the windows around them, and fetches LBMA and the short rates. |
| `fig1_gold_panel.do` | `gold_panel.pdf` - the round trip by commodity and by partner, on the balance plane. |
| `fig2_spread_vs_hurdle.do` | `spread_vs_hurdle.pdf` - the daily curve fit, the premium, the re-timing, the hurdle, and the metal that moved. |
| `fig3_counterfactual.do` | `counterfactual.pdf` - US gold imports against a pre-trend fitted to 2015-2024. |
| `fig4_deficit_gold.do` | `deficit_gold.pdf` - the monthly trade deficit as published and with the gold removed. |

## What each figure reports

| | |
|---|---|
| **fig1** | 100 commodity series, 5 partners. Gold and Switzerland both go up and to the right in the surge, then back. |
| **fig2** | 2,862 days in the fit, 2,851 re-timed. Re-timing cuts the premium's standard deviation from **0.499% to 0.235%**. 835 days clear westward, 1,169 eastward. Episode Dec 2024-Mar 2025: **+867 t** net west; Apr-Aug 2025: **-281 t**. |
| **fig3** | Line fitted to 118 months, slope +0.090 t a month. Episode excess **873 t**; over all 21 months since, **540 t** after netting the 15 below the line. |
| **fig4** | January 2025 deficit \$124.7bn reported, **\$92.2bn** without the gold. October 2025 \$37.4bn reported, **\$52.6bn** without it. Rolling twelve-month deficit overstated by **\$79.5bn** at its March 2025 peak. |

## What changed from the earlier versions

- **Figures 2 and 3 now use US customs, not Swiss.** The originals took mass
  directly from Swiss and UK export returns. Census reports value and not mass
  for HS 7108 and 7115, so tonnage here is **derived** - the month's customs
  value over the LBMA benchmark - and is labelled as derived wherever it
  appears. It is a different measurement of the same flow and will not agree to
  the tonne: figure 3's episode excess is 873 t on US imports against 645 t on
  Swiss and UK exports.
- **Everything runs longer.** The old universe pull stopped at November 2025;
  this one reaches July 2026, and gold goes back to 2015. Figure 4 in
  particular went from 26 months to 139, which removes the main caveat the
  earlier version carried.
- **The panel exporter is gone.** Figure 1's partner data used to come from a
  parquet file via a separate script; it is now one of the customs pull's
  outputs.

## Prerequisites

- **`CENSUS_API_KEY`** in the repo `.env`. The Census API stopped serving
  keyless requests: without a key it redirects to an HTML "Missing Key" page
  with a 200 status, which is why the pull checks that the body is JSON rather
  than trusting the status code. Free signup at
  `api.census.gov/data/key_signup.html`.
- **The Databento archives** under `data/databento/`, plus the minute files
  under `data/databento/minute/`. These are paid batch downloads and are not in
  git. With them present the pull spends nothing; without them it says exactly
  what to re-request and stops unless `--buy` is passed.
- **Stata 18** and `claude/stata-console/code/run_do.py`, which is what turns
  Stata's always-zero batch exit code into a truthful one.

## Traps found building this, all fixed in place

- **Stata will not do HTTPS here.** `import delimited` on a `https://` URL hangs
  the process indefinitely rather than failing, and has to be killed. Every
  series a do-file reads is therefore fetched to disk by a pull script first,
  including the FT-900 balance, which is why that lives in the customs pull.
- **Databento reuses one-digit year codes.** `GCZ5` is December 2015 in 2015 and
  December 2025 in 2025. Resolving the contract year once per symbol dates every
  modern observation of a reused code to the decade it first appeared, puts
  first notice ten years in the past, and silently drops the entire sample after
  November 2024. It has to be resolved per observation.
- **`twoway` defaults to `cmissing(y)`**, which skips missing observations and
  joins straight across them. Blanking a series to break a shaded area does
  nothing without `cmissing(n)`; the first draft of figure 4 had pale wedges
  spanning whole years that corresponded to no data at all.
- **`barwidth` is in axis units, not points.** On a monthly axis `barwidth(28)`
  is twenty-eight months, which drew figure 2's lower panel as solid blocks.
- **Census returns aggregates on the partner endpoint** - TOTAL FOR ALL
  COUNTRIES, OECD, EUROPEAN UNION, continent rows coded `1XXX`. Left in, the top
  five partners are five ways of saying "everywhere". Real countries are the
  four-digit numeric codes not starting with zero.
- **LBMA now sits behind Cloudflare** and returns 403 to non-browser clients, so
  the price comes from a cached copy and the pull says which source it used
  rather than serving stale data silently.
- **`graph set window fontface ""`** is a syntax error, not a no-op, and
  `c(graphfontface)` can come back empty in batch - so the font restore is
  guarded.

## Note on the figures being committed

`.csv` and `gold_final/data/` are gitignored; the four PDFs are committed
because they are the deliverable. Figure 1 can also write a PNG, but that calls
a helper outside this folder, so it is off by default (`global MAKE_PNG 1` turns
it back on).
