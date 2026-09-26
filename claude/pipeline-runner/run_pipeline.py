#!/usr/bin/env python3
"""
Take a bare clone of this repository to a re-timed New York premium, on any
machine, from an IDE or a terminal.

The repository does not commit data, so a fresh clone has working code and no
inputs. This rebuilds the whole chain: buy the two Databento source jobs,
derive the contract panel, build the premium and carry series, write the
minute-data specification, buy the minutes, and apply the timing correction.

It buys twice -- the source jobs, then the minutes -- and both purchases are
quoted through Databento's free costing endpoint before anything is spent.

    run_pipeline.py                     check everything, quote both, buy nothing
    run_pipeline.py --confirm-rebuy     + buy the source jobs
    run_pipeline.py --confirm-minutes   + buy the minute data
    run_pipeline.py --confirm-all       + buy both, in one run

    --force      redo steps whose outputs already exist
    --dry-run    print what each step would do, touch nothing

Running it from an IDE: press run. It uses the interpreter it was started with,
so whichever environment the IDE has selected is the one the whole pipeline
uses, and there is no interpreter path to configure.

Only two settings are machine-specific, and they are the first two below.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# ============================================================================
# EDIT THESE TWO
# ============================================================================

# The clone. Leave blank to infer it from this file's own location, which is
# correct whenever this script still sits inside the repository -- including
# when it is run from an IDE.
REPO_ROOT = ""

# The file holding DATABENTO_API_KEY=db-... Relative to REPO_ROOT unless you
# give an absolute path, so a key kept outside the repository also works.
ENV_FILE = ".env"

# ============================================================================
# Relative to REPO_ROOT. These mirror the paths the pipeline scripts use
# internally, so change them only if you move the data and change those too.
# ============================================================================

DATABENTO_DIR = "data/databento"          # the delivered source jobs
PROCESSED_DIR = "data/processed"          # panels derived from them
MINUTE_DIR = "data/databento/minute"      # minute bars, after reduction
SERIES_DIR = "claude/premium-carry-series"
TIMING_DIR = "claude/timing-fix"

# ============================================================================
# Behaviour, not paths.
# ============================================================================

# "windowed" buys only the minutes the correction needs (about $2.24, thousands
# of small requests, 30-60 minutes unattended). "batch" buys every contract's
# minutes as one job (about $43.09, one download, and room to re-time at
# another instant later). Raise PRICE_CEILING_USD before choosing "batch".
MINUTE_ROUTE = "windowed"

# A backstop, not a budget: any quote above this aborts the run, so a mistyped
# date range cannot become a large bill.
PRICE_CEILING_USD = 5.00

# How long to wait for an asynchronous Databento job. Jobs of this size have
# taken 2-16 minutes in practice.
JOB_WAIT_MINUTES = 90

# ============================================================================
# Nothing below here is machine-specific.
# ============================================================================

# The two source jobs, as they were originally delivered, so they can be bought
# again. Both expired on 20 September 2026.
SOURCE_JOBS = [
    {"schema": "statistics", "split_duration": "day"},
    {"schema": "ohlcv-1d"},
]
SOURCE_JOB_COMMON = {
    "dataset": "GLBX.MDP3",
    "symbols": "GC.FUT",
    "stype_in": "parent",
    "start": "2015-01-01",
    "end": "2026-08-21",
    "encoding": "csv",
    "compression": "zstd",
    "pretty_px": True,
    "pretty_ts": True,
    "map_symbols": True,
}

# What the original machine produced, to check a rebuild against.
REFERENCE = {"days": 2857, "premium_sd_pp": 0.499,
             "carry_sofr_corr": 0.952, "median_contracts": 6}

REQUIRED_PACKAGES = ("pandas", "numpy", "requests", "zstandard", "databento")


class Config:
    """Every path the runner uses, resolved once from the two settings above."""

    def __init__(self) -> None:
        self.repo = (Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT
                     else Path(__file__).resolve().parents[2])
        env = Path(ENV_FILE).expanduser()
        self.env = env if env.is_absolute() else self.repo / env
        self.databento = self.repo / DATABENTO_DIR
        self.processed = self.repo / PROCESSED_DIR
        self.minutes = self.repo / MINUTE_DIR
        self.series = self.repo / SERIES_DIR
        self.timing = self.repo / TIMING_DIR
        # The interpreter running this file. From an IDE that is whatever
        # environment the IDE has selected, which is the point.
        self.python = Path(sys.executable)

    def describe(self) -> str:
        return "\n".join([
            f"   repository   {self.repo}",
            f"   key file     {self.env}",
            f"   source data  {self.databento}",
            f"   panels       {self.processed}",
            f"   minutes      {self.minutes}",
            f"   interpreter  {self.python}",
            f"   route        {MINUTE_ROUTE}",
        ])


# --- helpers -----------------------------------------------------------------

def say(step: str, text: str = "") -> None:
    print(f"\n{'=' * 78}\n{step}\n{'=' * 78}" if not text else f"   {text}",
          flush=True)


def stop(message: str, command: str = "") -> None:
    """A designed stop, not a failure: how to continue, then exit cleanly."""
    print(f"\n{message}")
    if command:
        print(f"\n    {command}\n")
    sys.exit(0)


def die(message: str) -> None:
    sys.exit(f"\nSTOPPED: {message}")


def run_script(cfg: Config, script: str, *flags: str, dry: bool = False) -> None:
    cmd = [str(cfg.python), str(cfg.repo / script), *flags]
    if dry:
        print(f"   would run: {' '.join(cmd)}")
        return
    print(f"   running {script} {' '.join(flags)}", flush=True)
    if subprocess.run(cmd, cwd=cfg.repo).returncode != 0:
        die(f"{script} failed. Its own output above says why.")


def expect(cfg: Config, path: Path, script: str) -> None:
    """Check a step produced what the configuration says it should have.

    The pipeline scripts resolve their own paths internally. If one of the
    directories above has been changed without changing the script to match,
    the file lands somewhere else and this is where that shows up.
    """
    if path.exists():
        return
    die(f"{script} ran, but {path} is not there.\n"
        f"That usually means one of the relative paths at the top of this file "
        f"no longer matches where {Path(script).name} writes. Check both.")


def api_key(cfg: Config) -> str:
    key = (os.environ.get("DATABENTO_API_KEY") or "").strip()
    if key:
        return key
    if not cfg.env.exists():
        die(f"No key. Create {cfg.env} containing one line:\n"
            f"    DATABENTO_API_KEY=db-...\n"
            f"(.env is gitignored, so it never leaves the machine.)")
    for line in cfg.env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == "DATABENTO_API_KEY" and value.strip():
            return value.strip().strip("'\"")
    die(f"{cfg.env} has no usable DATABENTO_API_KEY line. Paste the key after "
        f"the = , with no quotes or spaces.")
    return ""                                                  # unreachable


def client(cfg: Config):
    import databento as db
    return db.Historical(api_key(cfg))


def quote(c, params: dict) -> float:
    return c.metadata.get_cost(
        dataset=params["dataset"], start=params["start"], end=params["end"],
        schema=params["schema"], symbols=params["symbols"],
        stype_in=params["stype_in"])


def wait_for_job(c, job_id: str, label: str) -> None:
    deadline = time.time() + JOB_WAIT_MINUTES * 60
    last = None
    while time.time() < deadline:
        jobs = {j.get("id", j.get("job_id")): j for j in
                c.batch.list_jobs(states="received,queued,processing,done")}
        state = (jobs.get(job_id) or {}).get("state")
        if state != last:
            say("", f"{label}: {state}")
            last = state
        if state == "done":
            return
        time.sleep(30)
    die(f"{label} has not finished after {JOB_WAIT_MINUTES} minutes. It is still "
        f"running and already paid for; re-run this script later to collect it.")


def fetch_job(cfg: Config, c, job_id: str, label: str) -> None:
    """Download a finished job, leaving a zip where the builders expect one."""
    cfg.databento.mkdir(parents=True, exist_ok=True)
    staging = cfg.databento / f"_{job_id}"
    staging.mkdir(exist_ok=True)
    paths = c.batch.download(job_id=job_id, output_dir=staging)
    zips = [p for p in paths if str(p).endswith(".zip")]
    if zips:
        for z in zips:
            shutil.move(str(z), cfg.databento / Path(z).name)
    else:
        target = cfg.databento / f"{job_id}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as zf:
            for p in sorted(staging.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=p.name)
        say("", f"{label}: packed {target.name}")
    shutil.rmtree(staging, ignore_errors=True)


# --- steps -------------------------------------------------------------------

def step_preflight(cfg: Config, args) -> None:
    say("STEP 0  Preflight")
    print(cfg.describe())

    for marker in ("requirements.txt", "src", TIMING_DIR):
        if not (cfg.repo / marker).exists():
            die(f"{cfg.repo} does not look like the repository: {marker} is "
                f"missing. Set REPO_ROOT at the top of this file.")

    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        die(f"This interpreter is missing {', '.join(missing)}.\n"
            f"    {cfg.python} -m pip install -r "
            f"{cfg.repo / 'requirements.txt'}\n"
            f"If you are in an IDE, check which environment it has selected.")

    version = ".".join(str(v) for v in sys.version_info[:3])
    say("", f"python {version}")
    if sys.version_info[:2] < (3, 12):
        say("", f"WARNING: this project expects 64-bit Python 3.12, found {version}")

    api_key(cfg)
    say("", f"key found in {cfg.env}")
    say("", "preflight passed")


def step_rebuy(cfg: Config, args) -> None:
    say("STEP 1  Source data: the two Databento jobs")
    existing = list(cfg.databento.glob("*.zip"))
    have = {s: any(any(s in n for n in zipfile.ZipFile(z).namelist())
                   for z in existing) for s in ("statistics", "ohlcv")}
    if all(have.values()) and not args.force:
        say("", f"already present in {cfg.databento}, skipping")
        return

    c = client(cfg)
    total = 0.0
    for job in SOURCE_JOBS:
        params = {**SOURCE_JOB_COMMON, **job}
        cost = quote(c, params)
        say("", f"{params['schema']:<12} ${cost:,.2f}")
        total += cost
    say("", f"{'total':<12} ${total:,.2f}")
    if total > PRICE_CEILING_USD:
        die(f"${total:,.2f} exceeds PRICE_CEILING_USD (${PRICE_CEILING_USD:,.2f}). "
            f"Check the dates at the top of this file before raising it.")
    if args.dry_run:
        return
    if not (args.confirm_rebuy or args.confirm_all):
        stop("Not buying the source data. To continue:",
             f'"{cfg.python}" "{Path(__file__).resolve()}" --confirm-rebuy')

    for job in SOURCE_JOBS:
        params = {**SOURCE_JOB_COMMON, **job}
        submitted = c.batch.submit_job(**params)
        job_id = submitted.get("id") or submitted.get("job_id")
        say("", f"submitted {params['schema']}: {job_id}")
        wait_for_job(c, job_id, params["schema"])
        fetch_job(cfg, c, job_id, params["schema"])
    say("", f"source data in {cfg.databento}")


def step_processed(cfg: Config, args) -> None:
    say("STEP 2  Contract panel")
    target = cfg.processed / "comex_contract_daily.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    script = "src/build_efp_from_databento.py"
    run_script(cfg, script, dry=args.dry_run)
    if not args.dry_run:
        expect(cfg, target, script)


def step_premium(cfg: Config, args) -> None:
    say("STEP 3  Premium and carry series")
    target = cfg.series / "premium_carry_daily.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    script = f"{SERIES_DIR}/build_premium_carry.py"
    run_script(cfg, script, dry=args.dry_run)
    if not args.dry_run:
        expect(cfg, target, script)


def step_verify(cfg: Config, args) -> None:
    say("STEP 4  Does this machine reproduce the reference run?")
    if args.dry_run:
        return
    check = cfg.series / "premium_carry_daily.csv"
    if not check.exists():
        say("", "nothing to verify yet")
        return
    import pandas as pd
    d = pd.read_csv(check)
    rows = [("trading days", len(d), REFERENCE["days"]),
            ("premium sd, pp", round(d.premium_pct.std(), 3),
             REFERENCE["premium_sd_pp"]),
            ("carry vs SOFR corr",
             round(d.carry_pct.corr(d.short_rate_pct), 3),
             REFERENCE["carry_sofr_corr"]),
            ("median contracts/day", int(d.n_contracts.median()),
             REFERENCE["median_contracts"])]
    say("", f"{'':<22}{'here':>10}{'reference':>12}")
    for name, got, want in rows:
        say("", f"{name:<22}{got:>10}{want:>12}"
                f"{'' if got == want else '   <- differs'}")
    say("", "Small differences mean the source data has moved on; large ones "
            "mean something did not carry across.")


def step_instants(cfg: Config, args) -> None:
    say("STEP 5  Minute-data specification")
    target = cfg.timing / "timing_instants.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    script = f"{TIMING_DIR}/timing_instants.py"
    run_script(cfg, script, dry=args.dry_run)
    if not args.dry_run:
        expect(cfg, target, script)


def missing_minute_years(cfg: Config) -> list[int]:
    """Years in the specification with no minute file yet.

    The puller resumes a year at a time, so "some files exist" is not the same
    as "the data is here". Treating it as the same silently skipped ten of
    twelve years once, and the correction then ran on the two that happened to
    be present without saying so.
    """
    import pandas as pd
    spec = pd.read_csv(cfg.timing / "timing_instants.csv", parse_dates=["date"])
    want = set(spec.date.dt.year)
    have = {int(p.stem.split("_")[-1]) for p in cfg.minutes.glob("gc_minute_*.csv")}
    return sorted(want - have)


def step_minutes(cfg: Config, args) -> None:
    say("STEP 6  Minute data")
    missing = missing_minute_years(cfg) if cfg.minutes.exists() else None
    if missing == [] and not args.force:
        say("", f"all years present in {cfg.minutes}, skipping")
        return
    if missing:
        say("", f"{len(missing)} of "
                f"{len(missing) + len(list(cfg.minutes.glob('gc_minute_*.csv')))} "
                f"years still to fetch: {missing[0]}-{missing[-1]}")
    if MINUTE_ROUTE not in ("windowed", "batch"):
        die(f'MINUTE_ROUTE must be "windowed" or "batch", not "{MINUTE_ROUTE}"')

    script = f"{TIMING_DIR}/pull_minute_bars.py"
    if args.dry_run:
        run_script(cfg, script, "--quote", dry=True)
        return
    run_script(cfg, script, "--quote")
    if not (args.confirm_minutes or args.confirm_all):
        stop(f"Not buying the minutes. The configured route is {MINUTE_ROUTE}. "
             f"To continue:",
             f'"{cfg.python}" "{Path(__file__).resolve()}" --confirm-minutes')

    if MINUTE_ROUTE == "windowed":
        run_script(cfg, script, "--pull", "--confirm")
    else:
        run_script(cfg, script, "--submit", "--confirm")
        job_id = (cfg.databento / "minute_raw" / "job_id.txt") \
            .read_text(encoding="utf-8").strip()
        wait_for_job(client(cfg), job_id, "minute job")
        run_script(cfg, script, "--download")
        run_script(cfg, script, "--normalize")


def step_apply(cfg: Config, args) -> None:
    say("STEP 7  Apply the timing correction")
    run_script(cfg, f"{TIMING_DIR}/apply_timing_fix.py", dry=args.dry_run)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--confirm-rebuy", action="store_true",
                   help="allow the two source jobs to be bought (about $1.91)")
    p.add_argument("--confirm-minutes", action="store_true",
                   help="allow the minute data to be bought")
    p.add_argument("--confirm-all", action="store_true",
                   help="allow both purchases, so one run does everything")
    p.add_argument("--force", action="store_true",
                   help="redo steps whose outputs already exist")
    p.add_argument("--dry-run", action="store_true",
                   help="print what each step would do and buy nothing")
    args = p.parse_args()

    cfg = Config()
    os.chdir(cfg.repo)        # the pipeline scripts expect the repository root

    step_preflight(cfg, args)
    step_rebuy(cfg, args)
    step_processed(cfg, args)
    step_premium(cfg, args)
    step_verify(cfg, args)
    step_instants(cfg, args)
    step_minutes(cfg, args)
    step_apply(cfg, args)

    say("DONE")
    print(f"   {cfg.series / 'premium_carry_daily.csv'}")
    print(f"   {cfg.timing / 'premium_retimed_daily.csv'}")
    print(f"   {cfg.timing / 'apply_timing_fix_output.txt'}")


if __name__ == "__main__":
    main()
