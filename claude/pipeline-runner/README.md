# Pipeline runner

One file that takes a bare clone to a re-timed New York premium, on any
machine. Written to the convention in `RESEARCH_DOSSIER.md` §10: everything
machine-specific sits in a marked block at the top, and nothing else needs
touching to move it to another computer.

```
python claude/pipeline-runner/run_pipeline.py                     # check, quote, stop
python claude/pipeline-runner/run_pipeline.py --confirm-rebuy     # + buy source data
python claude/pipeline-runner/run_pipeline.py --confirm-minutes   # + buy the minutes
```

## What you edit

```python
REPO_ROOT          = ""         # blank = infer from this file's location
PYTHON             = ""         # blank = the repo's .venv, else this interpreter
DATA_ROOT          = ""         # blank = REPO_ROOT/data
ENV_FILE           = ""         # blank = REPO_ROOT/.env
MINUTE_ROUTE       = "windowed" # or "batch"
PRICE_CEILING_USD  = 5.00
JOB_WAIT_MINUTES   = 90
```

Every one of them may be left blank on a normal clone, because each has a
sensible derivation. Set `REPO_ROOT` if you move this script out of the
repository, `DATA_ROOT` if the clone sits on a small disk, `PYTHON` if the
interpreter is somewhere unusual. The Windows and POSIX virtual-environment
layouts are both detected, so the same file runs on either.

## What it does

| Step | Action | Cost |
|---|---|---|
| 0 | Preflight: repository markers, interpreter, packages, key, disk | — |
| 1 | Re-buy the two expired Databento source jobs, wait, download | **$1.91** |
| 2 | `src/build_efp_from_databento.py` → the contract panel | — |
| 3 | `build_premium_carry.py` → the premium and carry series | — |
| 4 | Verify against the reference run on the original machine | — |
| 5 | `timing_instants.py` → the minute-data specification | — |
| 6 | Buy the minutes by the configured route | **$2.24** or **$43.09** |
| 7 | `apply_timing_fix.py` → the re-timed premium and its five checks | — |

Steps skip themselves when their outputs already exist, so the script is safe
to re-run and picks up where it stopped. `--force` redoes them anyway.

## How it handles money

It stops at each of the two purchases. Every spend is quoted first through
Databento's free costing endpoint, printed, and then **not made** unless the
matching flag is present — the script exits cleanly with the exact command to
continue, rather than failing. `PRICE_CEILING_USD` is a backstop rather than a
budget: any quote above it aborts the run, so a mistyped date range cannot
become a large bill.

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

- The script changes directory to the repository root before doing anything,
  so the scripts it calls — all of which expect to be run from there — work
  regardless of where you launch it from.
- `--bootstrap-venv` creates `.venv` and installs `requirements.txt` first, for
  a machine with nothing set up.
- `--dry-run` prints every step and buys nothing, which is the safe first run
  on an unfamiliar machine.
