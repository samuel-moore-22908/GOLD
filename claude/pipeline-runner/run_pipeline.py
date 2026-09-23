#!/usr/bin/env python3
"""
Take a bare clone of this repository to a re-timed New York premium, on any
machine, with one command per purchase.

The repository does not commit data, so a fresh clone has working code and no
inputs. This rebuilds the whole chain: re-buy the two expired Databento jobs,
derive the contract panel, build the premium and carry series, write the
minute-data specification, buy the minutes, and apply the timing correction.

It spends money at two points and stops at each one. Nothing is bought until
you re-run with the matching flag, and every purchase is quoted first through
Databento's free costing endpoint.

    python run_pipeline.py                      # check everything, quote, stop
    python run_pipeline.py --confirm-rebuy      # + buy the two source jobs
    python run_pipeline.py --confirm-minutes    # + buy the minute data
    python run_pipeline.py --confirm-rebuy --confirm-minutes    # the lot

    --bootstrap-venv   create .venv and install requirements first
    --force            redo steps whose outputs already exist
    --dry-run          print what each step would do, touch nothing

Everything machine-specific is in the EDIT THIS BLOCK section below. Nothing
else in this file needs changing to move it to another computer, and no path
depends on the directory you happen to launch it from.
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
# EDIT THIS BLOCK
# ============================================================================

# The clone. Leave blank to infer it from this file's own location, which is
# right whenever this script still sits inside the repository.
REPO_ROOT = ""

# The interpreter that runs the pipeline scripts. Leave blank to use the
# repository's virtual environment if there is one (.venv/Scripts/python.exe on
# Windows, .venv/bin/python elsewhere), and the interpreter running this file
# if there is not.
PYTHON = ""

# Where data lives. Leave blank for <REPO_ROOT>/data. Point it at another disk
# if the clone is on a small drive: the minute pull can run to a few hundred
# megabytes, and the whole-tape route to a few gigabytes once unpacked.
DATA_ROOT = ""

# The file holding DATABENTO_API_KEY=db-... Leave blank for <REPO_ROOT>/.env.
ENV_FILE = ""

# Which minute pull to make: "windowed" buys only the minutes the correction
# needs (about $2.24, thousands of small requests, 30-60 minutes unattended);
# "batch" buys every contract's minutes as one job (about $43.09, one download,
# leaves room to re-time at another instant later).
MINUTE_ROUTE = "windowed"

# A backstop, not a budget. Any single quote above this aborts the run, so a
# mistyped date range cannot turn into a large bill. Raise it deliberately if
# you choose the whole-tape route.
PRICE_CEILING_USD = 5.00

# How long to wait for an asynchronous Databento job before giving up. Jobs of
# this size have taken 2-16 minutes in practice.
JOB_WAIT_MINUTES = 90

# ============================================================================
# Nothing below here is machine-specific.
# ============================================================================

# What the two expired source jobs were, so they can be bought again. Taken
# from the metadata of the original deliveries.
SOURCE_JOBS = [
    {"schema": "statistics", "split_duration": "day"},
    {"schema": "ohlcv-1d", "split_duration": "none"},
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

# What this machine produced, to check the rebuild against. Small differences
# are expected if the source data has been revised or extended; large ones mean
# something did not carry across.
REFERENCE = {
    "days": 2857,
    "premium_sd_pp": 0.499,
    "carry_sofr_corr": 0.952,
    "median_contracts": 6,
}


class Config:
    def __init__(self) -> None:
        self.repo = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
            else Path(__file__).resolve().parents[2]
        self.data = Path(DATA_ROOT).expanduser().resolve() if DATA_ROOT \
            else self.repo / "data"
        self.env = Path(ENV_FILE).expanduser().resolve() if ENV_FILE \
            else self.repo / ".env"
        self.python = Path(PYTHON).expanduser().resolve() if PYTHON \
            else self._find_python()

    def _find_python(self) -> Path:
        candidates = [self.repo / ".venv" / "Scripts" / "python.exe",
                      self.repo / ".venv" / "bin" / "python"]
        for c in candidates:
            if c.exists():
                return c
        return Path(sys.executable)

    @property
    def databento_dir(self) -> Path:
        return self.data / "databento"

    @property
    def minute_dir(self) -> Path:
        return self.data / "databento" / "minute"

    def describe(self) -> str:
        return (f"   repository  {self.repo}\n"
                f"   data        {self.data}\n"
                f"   interpreter {self.python}\n"
                f"   key file    {self.env}\n"
                f"   route       {MINUTE_ROUTE}")


# --- small helpers -----------------------------------------------------------

def say(step: str, text: str = "") -> None:
    line = f"\n{'=' * 78}\n{step}\n{'=' * 78}" if not text else f"   {text}"
    print(line, flush=True)


def stop(message: str, command: str = "") -> None:
    """A designed stop, not a failure: print how to continue and exit cleanly."""
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
    result = subprocess.run(cmd, cwd=cfg.repo)
    if result.returncode != 0:
        die(f"{script} exited with code {result.returncode}")


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
    return ""                                              # unreachable


def client(cfg: Config):
    try:
        import databento as db
    except ImportError:
        die(f"The databento package is missing from {cfg.python}. "
            f"Install requirements, or re-run with --bootstrap-venv.")
    return db.Historical(api_key(cfg))


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
    die(f"{label} did not finish within {JOB_WAIT_MINUTES} minutes. It is still "
        f"running; re-run this script later and it will pick up from here.")


def fetch_job(cfg: Config, c, job_id: str, label: str) -> None:
    """Download a finished job and leave a zip where the builders expect one."""
    dest = cfg.databento_dir
    dest.mkdir(parents=True, exist_ok=True)
    staging = dest / f"_{job_id}"
    staging.mkdir(exist_ok=True)
    paths = c.batch.download(job_id=job_id, output_dir=staging)
    zips = [p for p in paths if str(p).endswith(".zip")]
    if zips:
        for z in zips:
            shutil.move(str(z), dest / Path(z).name)
    else:
        target = dest / f"{job_id}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as zf:
            for p in sorted(staging.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=p.name)
        say("", f"{label}: packed {target.name}")
    shutil.rmtree(staging, ignore_errors=True)


# --- the steps ---------------------------------------------------------------

def step_preflight(cfg: Config, args) -> None:
    say("STEP 0  Preflight")
    print(cfg.describe())

    for marker in ("requirements.txt", "src", "claude/timing-fix"):
        if not (cfg.repo / marker).exists():
            die(f"{cfg.repo} does not look like the repository: {marker} is "
                f"missing. Set REPO_ROOT at the top of this file.")

    if args.bootstrap_venv:
        venv = cfg.repo / ".venv"
        if not venv.exists():
            say("", f"creating {venv}")
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        cfg.python = cfg._find_python()
        say("", "installing requirements")
        subprocess.run([str(cfg.python), "-m", "pip", "install", "-q", "-r",
                        str(cfg.repo / "requirements.txt")], check=True)

    probe = subprocess.run(
        [str(cfg.python), "-c",
         "import sys, pandas, numpy, requests, zstandard, databento;"
         "print(sys.version.split()[0], pandas.__version__)"],
        capture_output=True, text=True)
    if probe.returncode != 0:
        die(f"{cfg.python} cannot import what the pipeline needs.\n"
            f"{probe.stderr.strip()}\n"
            f"Install with:  {cfg.python} -m pip install -r requirements.txt\n"
            f"or re-run this script with --bootstrap-venv.")
    version, pandas_version = probe.stdout.split()
    say("", f"python {version}, pandas {pandas_version}")
    if tuple(int(x) for x in version.split(".")[:2]) < (3, 12):
        say("", f"WARNING: this project expects 64-bit Python 3.12; found {version}")

    api_key(cfg)                                    # dies with instructions
    say("", f"key found in {cfg.env}")
    cfg.data.mkdir(parents=True, exist_ok=True)
    say("", "preflight passed")


def step_rebuy(cfg: Config, args) -> None:
    say("STEP 1  Source data: the two Databento jobs")
    existing = list(cfg.databento_dir.glob("*.zip"))
    have = {s: any(any(s in n for n in zipfile.ZipFile(z).namelist())
                   for z in existing) for s in ("statistics", "ohlcv")}
    if all(have.values()) and not args.force:
        say("", f"already present in {cfg.databento_dir}, skipping")
        return

    c = client(cfg)
    quotes, total = [], 0.0
    for job in SOURCE_JOBS:
        p = {**SOURCE_JOB_COMMON, **job}
        cost = c.metadata.get_cost(dataset=p["dataset"], start=p["start"],
                                   end=p["end"], schema=p["schema"],
                                   symbols=p["symbols"], stype_in=p["stype_in"])
        quotes.append((p["schema"], cost))
        total += cost
    for schema, cost in quotes:
        say("", f"{schema:<12} ${cost:,.2f}")
    say("", f"{'total':<12} ${total:,.2f}")
    if total > PRICE_CEILING_USD:
        die(f"${total:,.2f} exceeds PRICE_CEILING_USD (${PRICE_CEILING_USD:,.2f}). "
            f"Check the dates at the top of this file before raising it.")
    if args.dry_run:
        return
    if not args.confirm_rebuy:
        stop("Not buying. To continue from here:",
             f"{sys.executable} {Path(__file__).resolve()} --confirm-rebuy")

    for job in SOURCE_JOBS:
        p = {**SOURCE_JOB_COMMON, **job}
        if p["split_duration"] == "none":
            p.pop("split_duration")
        submitted = c.batch.submit_job(**p)
        job_id = submitted.get("id") or submitted.get("job_id")
        say("", f"submitted {p['schema']}: {job_id}")
        wait_for_job(c, job_id, p["schema"])
        fetch_job(cfg, c, job_id, p["schema"])
    say("", f"source data in {cfg.databento_dir}")


def step_processed(cfg: Config, args) -> None:
    say("STEP 2  Contract panel")
    target = cfg.data / "processed" / "comex_contract_daily.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    run_script(cfg, "src/build_efp_from_databento.py", dry=args.dry_run)


def step_premium(cfg: Config, args) -> None:
    say("STEP 3  Premium and carry series")
    target = cfg.repo / "claude/premium-carry-series/premium_carry_daily.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    run_script(cfg, "claude/premium-carry-series/build_premium_carry.py",
               dry=args.dry_run)


def step_verify(cfg: Config, args) -> None:
    say("STEP 4  Does this machine reproduce the reference run?")
    if args.dry_run:
        return
    check = cfg.repo / "claude/premium-carry-series/premium_carry_daily.csv"
    if not check.exists():
        say("", "nothing to verify yet")
        return
    probe = subprocess.run(
        [str(cfg.python), "-c",
         "import pandas as pd,sys;"
         f"d=pd.read_csv(r'{check}');"
         "print(len(d), round(d.premium_pct.std(),3),"
         "round(d.carry_pct.corr(d.short_rate_pct),3),"
         "int(d.n_contracts.median()))"],
        capture_output=True, text=True, cwd=cfg.repo)
    if probe.returncode != 0:
        say("", f"could not verify: {probe.stderr.strip()[:200]}")
        return
    days, sd, corr, contracts = probe.stdout.split()
    rows = [("trading days", days, REFERENCE["days"]),
            ("premium sd, pp", sd, REFERENCE["premium_sd_pp"]),
            ("carry vs SOFR corr", corr, REFERENCE["carry_sofr_corr"]),
            ("median contracts/day", contracts, REFERENCE["median_contracts"])]
    say("", f"{'':<22}{'here':>10}{'reference':>12}")
    for name, got, want in rows:
        flag = "" if str(got) == str(want) else "   <- differs"
        say("", f"{name:<22}{got:>10}{want:>12}{flag}")
    say("", "Small differences mean the source data has moved on; large ones "
            "mean something did not carry across.")


def step_instants(cfg: Config, args) -> None:
    say("STEP 5  Minute-data specification")
    target = cfg.repo / "claude/timing-fix/timing_instants.csv"
    if target.exists() and not args.force:
        say("", f"{target.name} already built, skipping")
        return
    run_script(cfg, "claude/timing-fix/timing_instants.py", dry=args.dry_run)


def step_minutes(cfg: Config, args) -> None:
    say("STEP 6  Minute data")
    if cfg.minute_dir.exists() and list(cfg.minute_dir.glob("*.csv")) \
            and not args.force:
        say("", f"minutes already in {cfg.minute_dir}, skipping")
        return
    if MINUTE_ROUTE not in ("windowed", "batch"):
        die(f'MINUTE_ROUTE must be "windowed" or "batch", not "{MINUTE_ROUTE}"')

    script = "claude/timing-fix/pull_minute_bars.py"
    if args.dry_run:
        run_script(cfg, script, "--quote", dry=True)
        return
    run_script(cfg, script, "--quote")
    if not args.confirm_minutes:
        stop(f"Not buying the minutes. The {MINUTE_ROUTE} route is the one "
             f"configured at the top of this file. To continue:",
             f"{sys.executable} {Path(__file__).resolve()} --confirm-minutes")

    if MINUTE_ROUTE == "windowed":
        run_script(cfg, script, "--pull", "--confirm")
    else:
        run_script(cfg, script, "--submit", "--confirm")
        job_id = (cfg.databento_dir / "minute_raw" / "job_id.txt") \
            .read_text(encoding="utf-8").strip()
        wait_for_job(client(cfg), job_id, "minute job")
        run_script(cfg, script, "--download")
        run_script(cfg, script, "--normalize")


def step_apply(cfg: Config, args) -> None:
    say("STEP 7  Apply the timing correction")
    run_script(cfg, "claude/timing-fix/apply_timing_fix.py", dry=args.dry_run)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--confirm-rebuy", action="store_true",
                   help="allow the two source jobs to be bought")
    p.add_argument("--confirm-minutes", action="store_true",
                   help="allow the minute data to be bought")
    p.add_argument("--bootstrap-venv", action="store_true",
                   help="create .venv and install requirements before starting")
    p.add_argument("--force", action="store_true",
                   help="redo steps whose outputs already exist")
    p.add_argument("--dry-run", action="store_true",
                   help="print what each step would do and buy nothing")
    args = p.parse_args()

    cfg = Config()
    os.chdir(cfg.repo)          # every script here expects the repository root

    step_preflight(cfg, args)
    step_rebuy(cfg, args)
    step_processed(cfg, args)
    step_premium(cfg, args)
    step_verify(cfg, args)
    step_instants(cfg, args)
    step_minutes(cfg, args)
    step_apply(cfg, args)

    say("DONE")
    print("   claude/premium-carry-series/premium_carry_daily.csv   the two series")
    print("   claude/timing-fix/premium_retimed_daily.csv           re-timed premium")
    print("   claude/timing-fix/apply_timing_fix_output.txt         the five checks")


if __name__ == "__main__":
    main()
