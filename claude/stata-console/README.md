# A Stata environment that runs from the console

Stata 18 MP is installed at `C:\Program Files\Stata18`, single-user, 2-core,
licensed to Samuel Moore. It ships **no console binary** — `StataMP-64.exe` is a
GUI application, and its only headless mode is a one-shot batch run that opens
no window. There is no `stata` on the PATH to type into.

This folder builds the missing piece two ways.

| File | What it gives you |
|---|---|
| `code/stata_console.py` | A real interactive Stata prompt in the terminal |
| `code/run_do.py` | Batch `.do` execution with an **honest exit code** |
| `code/stata_env.py` | Shared: finds Stata, starts it, moves data across the boundary |
| `code/99_smoke_test.py` | Nine checks, each one a thing that actually broke during setup |
| `stata.ps1` | Launcher — picks console or batch from whether you passed a `.do` |

## Use it

```powershell
.\claude\stata-console\stata.ps1                  # interactive prompt
.\claude\stata-console\stata.ps1 analysis.do      # batch, real exit code
.venv\Scripts\python.exe claude\stata-console\code\99_smoke_test.py
```

Interactive session, doing something this project actually needs:

```
. %parquet transfer/raw/gold_exports_2024.parquet E_COMMODITY.str.startswith('7108')
loaded 2,102 obs, 18 vars from gold_exports_2024.parquet

. collapse (sum) ALL_VAL_MO, by(DF)
. gen bn = ALL_VAL_MO/1e9
. list DF bn

     +------------+
     | DF      bn |
     |------------|
  1. |  1   22.86 |
  2. |  2    6.78 |
     +------------+
```

That is the 2024 domestic/re-export split of US HS 7108 exports, $22.86bn against
$6.78bn, reproducing the pandas figure exactly.

### Console commands

Anything not starting with `%` goes straight to Stata. A line ending in an open
brace keeps reading until the braces balance, so `foreach` and `program` blocks
paste in whole.

| Meta-command | Effect |
|---|---|
| `%parquet PATH [QUERY]` | Load parquet into Stata. `QUERY` is a pandas `.query()` string, applied **before** the handoff |
| `%use PATH` / `%save PATH` | `.dta` in and out |
| `%df NAME` | Copy Stata's dataset into a pandas frame in the same session |
| `%py EXPR` | Evaluate Python. Same namespace, so `%df out` then `%py out.shape` works |
| `exit`, `quit`, Ctrl-D | Leave |

## Why Python is in the loop at all

Not preference — capability. **Stata 18 cannot read parquet**, and every dataset
this project has produced is parquet. `pystata` is StataCorp's own embedding
interface, shipped inside the install at `utilities/pystata`, and it is the
supported way to get a Stata session that a terminal can drive. Going through it
means parquet, a live pandas frame beside the Stata one, and no window.

`pystata` is **not on PyPI** and must not be added to `requirements.txt`. It is
imported from the Stata install directory, which `stata_env.find_stata()` locates
by scanning Program Files — so a Stata 19 upgrade needs no edit here, and
`STATA_HOME` overrides it if the install ever moves.

## Three traps, all silent, all handled

Each was observed on this machine during setup. They are the reason this is a
wrapper and not a one-line alias.

**1. Batch mode always exits 0.** This is the serious one.

```
StataMP-64.exe /e do broken.do    ->    exit code 0
```

Verified: a do-file dying on `r(111)` returns the same 0 as a clean run. Nothing
in a shell, Makefile, or CI step can tell the difference without reading the log.
`run_do.py` parses the log for the `r(nnn)` Stata wrote there and exits 1. If you
run Stata from a script by any other route, do this yourself or your pipeline
will report success over a failed regression.

**2. A UTF-8 BOM breaks the first command.** PowerShell's `Set-Content -Encoding
utf8` and `>` both write one by default, so this is easy to hit:

```
. display "before"
'display is not a valid command name
r(199);
```

The error names a command that looks correct, because the BOM is invisible.
`run_do.py` detects it, warns loudly, and runs a stripped copy.

**3. pandas 3 dtypes do not survive the handoff.** Parquet reads into
pyarrow-backed dtypes, and arithmetic on those can land in `object` — dividing an
`int64` column by one holding `<NA>` yields an object column of Python floats.
`pdataframe_to_data()` then fails with `failed to store the string value in the
current Stata dataset`, naming neither the column nor the cause.
`coerce_for_stata()` fixes the dtypes first: object-that-is-really-numeric back to
numbers, datetimes to `%tc` doubles, nullable numerics to `float64` (Stata has no
missing integer), everything else to `str` with missing as `""` rather than the
literal text `"None"`.

One difference worth knowing between the two modes: **interactive errors raise and
the session survives**; batch errors stop the do-file. `pystata` surfaces a Stata
error as a Python `SystemError` carrying the `r(nnn)` message, which the console
catches so a typo does not end your session.

## Optional

`pip install pyreadline3` gives arrow-key history and line editing at the prompt.
Not required; the console detects it and works without it.
