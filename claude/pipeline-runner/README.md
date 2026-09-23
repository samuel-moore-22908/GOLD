# Pipeline runner

One file that takes a bare clone to a re-timed New York premium, on any
machine. Written to the convention in `RESEARCH_DOSSIER.md` §10: everything
machine-specific sits in a marked block at the top, and nothing else needs
touching to move it to another computer.

```
run_pipeline.py                     # check, quote both, buy nothing
run_pipeline.py --confirm-rebuy     # + buy the source jobs
run_pipeline.py --confirm-minutes   # + buy the minutes
run_pipeline.py --confirm-all       # + buy both, in one run
```

**From an IDE: press run.** It uses the interpreter it was started with, so
whichever environment the IDE has selected is the one the whole pipeline uses,
and there is no interpreter path to configure. It also changes directory to the
repository root before doing anything, so the IDE's working directory does not
matter either.

## What you edit

Two settings, and only two, are machine-specific:

```python
REPO_ROOT = ""        # blank = infer from this file's location
ENV_FILE  = ".env"    # relative to REPO_ROOT, or an absolute path
```

`REPO_ROOT` can stay blank on a normal clone — the script finds the repository
from its own location — and needs setting only if you move this file out of the
repository. `ENV_FILE` takes an absolute path if you keep the key outside the
clone.

Everything else is a relative path into the repository, grouped just below
those two:

```python
DATABENTO_DIR = "data/databento"          # the delivered source jobs
PROCESSED_DIR = "data/processed"          # panels derived from them
MINUTE_DIR    = "data/databento/minute"   # minute bars, after reduction
SERIES_DIR    = "claude/premium-carry-series"
TIMING_DIR    = "claude/timing-fix"
```

These mirror the paths the pipeline scripts use internally, so change them only
if you move the data and change those scripts to match. If the two ever drift
apart, the runner says so by name — "`X` ran, but `Y` is not there" — rather
than failing obscurely two steps later.

Then three behaviour settings: `MINUTE_ROUTE` (`"windowed"` or `"batch"`),
`PRICE_CEILING_USD`, and `JOB_WAIT_MINUTES`.

## What it does

| Step | Action | Cost |
|---|---|---|
| 0 | Preflight: repository markers, packages, key, interpreter | — |
| 1 | Buy the two Databento source jobs, wait for them, download, unpack | **$1.90** |
| 2 | `src/build_efp_from_databento.py` → the contract panel | — |
| 3 | `build_premium_carry.py` → the premium and carry series | — |
| 4 | Verify against the reference run on the original machine | — |
| 5 | `timing_instants.py` → the minute-data specification | — |
| 6 | Buy the minutes by the configured route | **$2.24** or **$43.09** |
| 7 | `apply_timing_fix.py` → the re-timed premium and its five checks | — |

Steps skip themselves when their outputs already exist, so the script is safe
to re-run and picks up where it stopped. `--force` redoes them anyway.

## How it handles money

It buys twice — the source jobs, then the minutes — and stops at each. Every
spend is quoted first through Databento's free costing endpoint, printed, and
then **not made** unless the matching flag is present; the script exits cleanly
with the exact command to continue, rather than failing. `--confirm-all`
authorises both in a single run.

`PRICE_CEILING_USD` is a backstop rather than a budget: any quote above it
aborts the run, so a mistyped date range cannot become a large bill. Raise it
deliberately before switching `MINUTE_ROUTE` to `"batch"`, which quotes at
about $43.

## Step 4, the part worth keeping

The rebuild is only trustworthy if it reproduces what the original machine
produced. Step 4 reads the rebuilt series and prints it against the reference:

```
                               here   reference
   trading days                2857        2857
   premium sd, pp             0.499       0.499
   carry vs SOFR corr         0.952       0.952
   median contracts/day           6           6
```

Small differences mean the source data has been revised or extended since.
Large ones mean something did not carry across, and the later steps should not
be trusted until that is understood.

## Notes

- `--dry-run` prints every step and buys nothing, which is the safe first run
  on an unfamiliar machine.
- If the interpreter is missing a package, preflight names it and prints the
  `pip install -r requirements.txt` line for that exact interpreter — the usual
  IDE failure is simply the wrong environment being selected.
- The source jobs both expired on 20 September 2026, which is why step 1 buys
  rather than downloads. At about $1.90 for the pair that is cheaper than
  moving 236 MB between machines.
