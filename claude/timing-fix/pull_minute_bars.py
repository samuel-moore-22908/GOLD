"""
Buy the minutes needed for the timing fix -- after pricing them, never before.

The correction needs one liquid contract's price at two instants a day: the
London auction and the COMEX settlement. Because the timing shock is common to
every contract on the curve, one contract is enough to correct the whole
cross-section, so this buys a few hundred minutes a day rather than the whole
tape.

    --quote     price the alternatives through metadata.get_cost, which is free
    --pull      fetch the per-day windows (requires --confirm as well)
    --batch     print the parameters for the same pull through the web UI

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

import pandas as pd

INSTANTS = Path("claude/timing-fix/timing_instants.csv")
OUT = Path("data/databento/minute")

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


def batch_spec() -> None:
    t = instants()
    print("Batch job parameters, to enter in the Databento web UI -- the same")
    print("shape as the two jobs already in data/databento/:\n")
    print(f"   dataset      {DATASET}")
    print(f"   schema       {SCHEMA}")
    print("   symbols      GC.FUT")
    print("   stype_in     parent")
    print(f"   start        {t.window_start_utc.min():%Y-%m-%dT%H:%M}Z")
    print(f"   end          {t.window_end_utc.max():%Y-%m-%dT%H:%M}Z")
    print("   encoding     csv        compression  zstd")
    print("   pretty_px    true       pretty_ts    true")
    print("   map_symbols  true       split_duration  month")
    print("\nThat buys every GC contract's minutes across the whole period, which")
    print("is far more than the correction needs; apply_timing_fix.py will use")
    print("only the lead contract's bars in the two windows. Unzip into")
    print(f"   {OUT}")


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


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quote", action="store_true")
    p.add_argument("--batch", action="store_true")
    p.add_argument("--pull", action="store_true")
    p.add_argument("--confirm", action="store_true",
                   help="required alongside --pull; without it nothing is bought")
    args = p.parse_args()
    if args.batch:
        batch_spec()
    if args.quote:
        quote(args)
    if args.pull:
        pull(args)
    if not (args.batch or args.quote or args.pull):
        p.print_help()


if __name__ == "__main__":
    main()
