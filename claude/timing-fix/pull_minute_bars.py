"""
Buy the minutes needed for the timing fix -- after pricing them, never before.

The correction needs one liquid contract's price at two instants a day: the
London auction and the COMEX settlement. Because the timing shock is common to
every contract on the curve, one contract is enough to correct the whole
cross-section, so this buys a few hundred minutes a day rather than the whole
tape.

Two ways to buy it.

    --quote       price both, through metadata.get_cost, which is free
    --pull        the windowed route: one request per day, lead contract only,
                  buying only the minutes needed (needs --confirm)

or the whole tape in one asynchronous job, which costs more but arrives as a
single download and leaves room to re-time at some other instant later:

    --batch       print the job parameters without submitting
    --submit      quote it, then submit it (needs --confirm)
    --status      state and progress of the submitted job
    --download    fetch the finished job's files
    --normalize   reduce those files to the bars the correction reads

Costing calls are free; nothing is downloaded without --confirm. The API
signatures here were checked against the installed databento client (0.86.0).

The key is read from DATABENTO_API_KEY in the environment, or from a line
reading DATABENTO_API_KEY=db-... in a .env at the repo root, which is
gitignored. Keeping it in .env means it never has to be typed into a shell
that records history, set machine-wide, or pasted into a conversation.

Reads   claude/timing-fix/timing_instants.csv
        .env                                         (the key, never printed)
Writes  data/databento/minute/gc_minute_<year>.csv   (gitignored, like all data)

Run from the repo root:
    .venv/Scripts/python.exe claude/timing-fix/pull_minute_bars.py --quote
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

INSTANTS = Path("claude/timing-fix/timing_instants.csv")
OUT = Path("data/databento/minute")
# Where a batch job's files land before they are reduced to the bars the
# correction reads. Large, and gitignored with everything else under data/.
RAW = Path("data/databento/minute_raw")
JOB_FILE = RAW / "job_id.txt"

DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
# Spacing between requests. The per-day strategy makes thousands of them, so it
# is paced deliberately rather than run flat out.
REQUEST_SPACING_S = 0.4
QUOTE_SAMPLE_DAYS = 12          # days sampled to extrapolate the windowed cost


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def api_key() -> tuple[str | None, str]:
    """The key, and a sentence about where it did or did not come from.

    Read from DATABENTO_API_KEY in the environment, else from the gitignored
    .env at the repo root. The .env route exists so the key never has to be
    typed into a shell that records history, set as a machine-wide variable, or
    pasted into a conversation. It is read here and never printed.
    """
    key = (os.environ.get("DATABENTO_API_KEY") or "").strip()
    if key:
        return key, "using DATABENTO_API_KEY from the environment"

    if not ENV_FILE.exists():
        return None, (f"No key found. Create {ENV_FILE} containing a line\n"
                      f"    DATABENTO_API_KEY=db-...\n"
                      f"(.env is gitignored.)")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() != "DATABENTO_API_KEY":
            continue
        value = value.strip().strip("'\"")
        if value:
            return value, f"using the key in {ENV_FILE}"
        return None, (f"{ENV_FILE} has a DATABENTO_API_KEY line but it is empty."
                      f"\nPaste the key after the = , with no quotes or spaces, "
                      f"and run this again.")

    return None, (f"{ENV_FILE} exists but has no DATABENTO_API_KEY line. Add\n"
                  f"    DATABENTO_API_KEY=db-...")


def client():
    key, note = api_key()
    if not key:
        sys.exit(note + "\nCosting calls need the key too, and they are free.")
    print(f"({note})\n")
    try:
        import databento as db
    except ImportError:
        sys.exit("pip install databento (into .venv) first.")
    return db.Historical(key)


def instants() -> pd.DataFrame:
    t = pd.read_csv(INSTANTS, parse_dates=["auction_utc", "settle_utc",
                                           "window_start_utc", "window_end_utc",
                                           "date"])
    return t.dropna(subset=["lead_symbol"])


def quote(args) -> None:
    c = client()
    t = instants()
    lo, hi = t.window_start_utc.min(), t.window_end_utc.max()
    symbols = sorted(t.lead_symbol.dropna().unique())

    print("Costing three ways of buying the same correction.\n")

    print("1. Everything: every GC contract, every minute, whole sample.")
    full = c.metadata.get_cost(dataset=DATASET, start=lo, end=hi, schema=SCHEMA,
                               symbols="GC.FUT", stype_in="parent")
    size = c.metadata.get_billable_size(dataset=DATASET, start=lo, end=hi,
                                        schema=SCHEMA, symbols="GC.FUT",
                                        stype_in="parent")
    print(f"   ${full:,.2f}   ({size/1e9:.2f} GB billable)\n")

    time.sleep(REQUEST_SPACING_S)
    print(f"2. Lead contracts only ({len(symbols)} symbols), whole days.")
    lead = c.metadata.get_cost(dataset=DATASET, start=lo, end=hi, schema=SCHEMA,
                               symbols=symbols, stype_in="raw_symbol")
    print(f"   ${lead:,.2f}\n")

    print(f"3. Lead contracts, only the minutes needed "
          f"({int(t.window_minutes.sum()):,} contract-minutes).")
    sample = t.iloc[:: max(1, len(t) // QUOTE_SAMPLE_DAYS)].head(QUOTE_SAMPLE_DAYS)
    total = 0.0
    for _, r in sample.iterrows():
        time.sleep(REQUEST_SPACING_S)
        total += c.metadata.get_cost(
            dataset=DATASET, start=r.window_start_utc, end=r.window_end_utc,
            schema=SCHEMA, symbols=[r.lead_symbol], stype_in="raw_symbol")
    per_day = total / len(sample)
    print(f"   ${per_day * len(t):,.2f} estimated, from {len(sample)} sampled days "
          f"at ${per_day:.4f} a day")
    print("   (an estimate: per-request minimums, if any, make the true figure")
    print("    the larger of this and the floor times "
          f"{len(t):,} requests)\n")
    print("Pick on these numbers. Option 3 buys the least data but makes the most")
    print("requests; option 1 is one job and the same shape as the pulls already")
    print("in data/databento/.")


def batch_params() -> dict:
    """The one job that buys every GC contract's minutes across the sample."""
    t = instants()
    return {
        "dataset": DATASET,
        "symbols": "GC.FUT",
        "stype_in": "parent",
        "schema": SCHEMA,
        "start": t.window_start_utc.min().floor("D"),
        "end": t.window_end_utc.max().ceil("D"),
        "encoding": "csv",
        "compression": "zstd",
        "pretty_px": True,
        "pretty_ts": True,
        "map_symbols": True,
        "split_duration": "month",
    }


def batch_spec() -> None:
    p = batch_params()
    print("Batch job parameters -- the same shape as the two jobs already in")
    print("data/databento/. --submit sends exactly these; they are printed here")
    print("so they can be entered in the web UI instead.\n")
    for k, v in p.items():
        v = f"{v:%Y-%m-%dT%H:%M}Z" if isinstance(v, pd.Timestamp) else v
        print(f"   {k:<16}{v}")
    print("\nThat buys every GC contract's minutes across the whole period, which")
    print("is far more than the correction needs. --normalize afterwards keeps")
    print("only the lead contract's bars inside each day's windows and writes")
    print(f"   {OUT}/gc_minute_<year>.csv")


def batch_submit(args) -> None:
    """Quote the job, then submit it -- but only with --confirm."""
    c = client()
    p = batch_params()
    cost = c.metadata.get_cost(dataset=p["dataset"], start=p["start"], end=p["end"],
                               schema=p["schema"], symbols=p["symbols"],
                               stype_in=p["stype_in"])
    size = c.metadata.get_billable_size(dataset=p["dataset"], start=p["start"],
                                        end=p["end"], schema=p["schema"],
                                        symbols=p["symbols"], stype_in=p["stype_in"])
    print(f"This job costs ${cost:,.2f} ({size/1e9:.2f} GB billable):")
    print(f"   {p['symbols']} ({p['stype_in']}), {p['schema']}, "
          f"{p['start']:%Y-%m-%d} to {p['end']:%Y-%m-%d}\n")
    if not args.confirm:
        sys.exit("Not submitting. Re-run with --confirm to spend that amount.")

    job = c.batch.submit_job(**p)
    job_id = job.get("id") or job.get("job_id")
    RAW.mkdir(parents=True, exist_ok=True)
    JOB_FILE.write_text(str(job_id) + "\n", encoding="utf-8")
    print(f"submitted: {job_id}")
    print(f"state {job.get('state')}, recorded in {JOB_FILE}")
    print("\nJobs are processed asynchronously. Check with --status; download with")
    print("--download once the state is 'done'.")


def saved_job_id() -> str:
    if not JOB_FILE.exists():
        sys.exit(f"No job recorded in {JOB_FILE}. Submit one with --submit, or "
                 f"write an existing job id into that file.")
    return JOB_FILE.read_text(encoding="utf-8").strip()


def batch_status() -> None:
    c = client()
    job_id = saved_job_id()
    jobs = {j.get("id", j.get("job_id")): j
            for j in c.batch.list_jobs(states="received,queued,processing,done,expired")}
    j = jobs.get(job_id)
    if j is None:
        sys.exit(f"{job_id} is not in the job list. It may have expired.")
    print(f"{job_id}: state {j.get('state')}")
    for k in ("progress", "record_count", "billed_size", "actual_size", "ts_expiration"):
        if j.get(k) is not None:
            print(f"   {k:<14}{j[k]}")
    if j.get("state") == "done":
        files = c.batch.list_files(job_id)
        total = sum(f.get("size", 0) for f in files)
        print(f"   {len(files)} files, {total/1e9:.2f} GB -- ready for --download")


def batch_download() -> None:
    c = client()
    job_id = saved_job_id()
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"downloading {job_id} into {RAW} ...")
    paths = c.batch.download(job_id=job_id, output_dir=RAW)
    print(f"{len(paths)} files written")
    print("Now run --normalize, which reduces them to the minutes the correction")
    print("needs. The raw files are large; keep them until the fix is validated.")


def normalize() -> None:
    """Reduce the batch output to the bars the correction actually reads.

    The job delivers every GC contract at every minute. This keeps only the rows
    that fall inside a day's window and belong to that day's lead or backup
    contract, streaming file by file so the whole tape is never held in memory.
    """
    files = sorted(RAW.rglob("*.csv.zst")) + sorted(RAW.rglob("*.csv"))
    if not files:
        sys.exit(f"No downloaded files under {RAW}. Run --download first.")

    t = instants()
    t = t.sort_values("window_start_utc").reset_index(drop=True)
    starts = (t.window_start_utc
              - pd.to_timedelta(t.lookback_minutes, unit="m")).to_numpy()
    ends = t.window_end_utc.to_numpy()

    kept: list[pd.DataFrame] = []
    for f in files:
        df = pd.read_csv(f, compression="zstd" if f.suffix == ".zst" else None,
                         usecols=lambda c: c in {"ts_event", "symbol", "close",
                                                 "open", "high", "low", "volume"})
        if df.empty or "ts_event" not in df.columns:
            continue
        df["ts"] = pd.to_datetime(df["ts_event"], utc=True, format="mixed")
        # Assign each bar to the window it could belong to, then test that it
        # really is inside that window and is the contract we want.
        idx = np.searchsorted(starts, df.ts.to_numpy(), side="right") - 1
        ok = idx >= 0
        df, idx = df[ok], idx[ok]
        if df.empty:
            continue
        w = t.iloc[idx]
        inside = (df.ts.to_numpy() <= ends[idx])
        wanted = (df.symbol.to_numpy() == w.lead_symbol.to_numpy()) | \
                 (df.symbol.to_numpy() == w.backup_symbol.to_numpy())
        take = inside & wanted
        if not take.any():
            continue
        out = df[take].copy()
        out["trade_date"] = w.date.to_numpy()[take]
        out["requested_symbol"] = w.lead_symbol.to_numpy()[take]
        kept.append(out[["ts", "symbol", "close", "trade_date", "requested_symbol"]])
        print(f"   {f.name}: kept {take.sum():,} of {len(df):,} bars")

    if not kept:
        sys.exit("Nothing matched. Check that the job covered the right period.")
    m = pd.concat(kept, ignore_index=True).sort_values("ts")
    OUT.mkdir(parents=True, exist_ok=True)
    for year, g in m.groupby(pd.to_datetime(m.trade_date).dt.year):
        path = OUT / f"gc_minute_{year}.csv"
        g.to_csv(path, index=False)
        print(f"{year}: {len(g):,} bars -> {path}")
    days = m.trade_date.nunique()
    print(f"\n{len(m):,} bars across {days:,} of {len(t):,} trading days "
          f"({100*days/len(t):.1f}%). Now run apply_timing_fix.py.")


def pull(args) -> None:
    if not args.confirm:
        sys.exit("Refusing to spend money without --confirm. Run --quote first.")
    c = client()
    t = instants()
    OUT.mkdir(parents=True, exist_ok=True)

    for year, g in t.groupby(t.date.dt.year):
        path = OUT / f"gc_minute_{year}.csv"
        if path.exists():
            print(f"{year}: already present, skipping")
            continue
        frames = []
        for i, (_, r) in enumerate(g.iterrows(), 1):
            time.sleep(REQUEST_SPACING_S)
            start = r.window_start_utc - pd.Timedelta(minutes=int(r.lookback_minutes))
            try:
                data = c.timeseries.get_range(
                    dataset=DATASET, start=start, end=r.window_end_utc,
                    schema=SCHEMA, symbols=[r.lead_symbol], stype_in="raw_symbol")
                df = data.to_df()
            except Exception as exc:                       # noqa: BLE001
                print(f"   {r.date:%Y-%m-%d} {r.lead_symbol}: {exc}")
                continue
            if df.empty:
                continue
            df["trade_date"] = r.date
            df["requested_symbol"] = r.lead_symbol
            frames.append(df.reset_index())
            if i % 25 == 0:
                print(f"   {year}: {i}/{len(g)} days")
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(path, index=False)
            print(f"{year}: wrote {path}")


def selftest() -> None:
    """Check --normalize keeps exactly the right bars, on fabricated files.

    The window assignment is the one piece of arithmetic here that could be
    quietly wrong on real data, so it is exercised against rows whose expected
    fate is known: inside the window and the lead contract (keep), inside the
    window but another contract (drop), and the right contract an hour early
    (drop).
    """
    global RAW, OUT
    import tempfile

    t = instants().head(3)
    rows = []
    for _, r in t.iterrows():
        rows += [
            {"ts_event": r.auction_utc, "symbol": r.lead_symbol, "close": 1200.0},
            {"ts_event": r.settle_utc, "symbol": r.lead_symbol, "close": 1201.0},
            {"ts_event": r.auction_utc, "symbol": "GCZ9_OTHER", "close": 9999.0},
            {"ts_event": r.auction_utc - pd.Timedelta(hours=1),
             "symbol": r.lead_symbol, "close": 8888.0},
        ]
    expected = 2 * len(t)

    with tempfile.TemporaryDirectory() as tmp:
        RAW, OUT = Path(tmp) / "raw", Path(tmp) / "out"
        RAW.mkdir(parents=True)
        pd.DataFrame(rows).to_csv(RAW / "fake-20150102.csv.zst",
                                  index=False, compression="zstd")
        normalize()
        got = pd.concat([pd.read_csv(f) for f in OUT.glob("*.csv")], ignore_index=True)

    assert len(got) == expected, f"kept {len(got)}, expected {expected}"
    assert set(got.close) == {1200.0, 1201.0}, f"kept the wrong rows: {set(got.close)}"
    print(f"selftest: kept {len(got)} of {len(rows)} fabricated bars, "
          f"dropped the other contract and the early print -- PASS")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selftest", action="store_true",
                   help="check the normalisation arithmetic on fabricated files")
    p.add_argument("--quote", action="store_true",
                   help="price the three ways of buying the correction (free)")
    p.add_argument("--batch", "--batch-spec", dest="batch", action="store_true",
                   help="print the batch job parameters without submitting")
    p.add_argument("--submit", action="store_true",
                   help="quote and submit the whole-tape batch job (needs --confirm)")
    p.add_argument("--status", action="store_true",
                   help="state and progress of the submitted job")
    p.add_argument("--download", action="store_true",
                   help="download a finished job into data/databento/minute_raw")
    p.add_argument("--normalize", action="store_true",
                   help="reduce downloaded files to the bars the correction needs")
    p.add_argument("--pull", action="store_true",
                   help="the windowed alternative: per-day requests (needs --confirm)")
    p.add_argument("--confirm", action="store_true",
                   help="required alongside --submit or --pull; nothing is bought "
                        "without it")
    args = p.parse_args()

    actions = [(args.selftest, selftest),
               (args.batch, batch_spec), (args.quote, lambda: quote(args)),
               (args.submit, lambda: batch_submit(args)), (args.status, batch_status),
               (args.download, batch_download), (args.normalize, normalize),
               (args.pull, lambda: pull(args))]
    ran = False
    for flag, fn in actions:
        if flag:
            fn()
            ran = True
    if not ran:
        p.print_help()


if __name__ == "__main__":
    main()
