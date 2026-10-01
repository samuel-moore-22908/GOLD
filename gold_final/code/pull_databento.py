#!/usr/bin/env python3
"""
Everything the spread needs: COMEX futures from Databento, plus the two free
series the spread is measured against.

The timing calculation and the data purchase are one job, so they are one
script. You cannot buy the minute bars without first knowing which minutes to
buy, and which minutes those are depends on the date: the LBMA auction is
struck at 15:00 London and the COMEX settlement over 13:29:30-13:30:00 New
York, and the gap between those two is not a fixed offset because the UK and
the US change their clocks on different weekends. Computing it is a
prerequisite of the purchase, not a cleaning step.

Five outputs into gold_final/data/raw:

  comex_contract_daily.csv   per-contract settlement and open interest, with
                             days to first notice. The curve the daily fit runs
                             on.
  timing_instants.csv        the two instants per trading day in UTC, and the
                             lead contract, with the gap in hours.
  gc_minute_windows.csv      minute bars inside a few minutes of each instant,
                             for the lead contract. Reduced from ~630k rows to
                             the ~22 a day that matter.
  lbma_pm.csv                the London PM benchmark, the spot leg.
  short_rates.csv            SOFR and the 3-month bill, for the carry check.

COST CONTROL. Databento charges for data. This script never buys anything it
already has: it reads the archives in ARCHIVE_DIR and the minute files in
MINUTE_DIR, and only calls the API for months genuinely absent. When some are,
it lists them and then ASKS, defaulting to no; --buy answers yes in advance for
an unattended run. With no stdin attached it refuses rather than hanging or
failing. The archives currently in the repo cover 2015 to the present, so a
normal rerun costs nothing and asks nothing.

Needs DATABENTO_API_KEY in the repo .env only if something must be bought.

Run from anywhere:
    python gold_final/code/pull_databento.py            # rebuild from archives
    python gold_final/code/pull_databento.py --buy      # allow purchases
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS BLOCK IF YOU MOVE THE PROJECT
# ============================================================================
REPO_ROOT = ""                          # blank = infer from this file's location
ENV_FILE = ".env"                       # relative to the repo root
ARCHIVE_DIR = "data/databento"          # the purchased Databento zips
MINUTE_DIR = "data/databento/minute"    # the purchased minute bars
OUT_DIR = "gold_final/data/raw"         # where this script writes
# prices.lbma.org.uk sits behind Cloudflare and now refuses non-browser
# clients, so this copy is the working source rather than a fallback. It is
# therefore COMMITTED, unlike everything else the pulls read: a file that can no
# longer be fetched by a script is an input, not a cache, and losing it would
# make the spread unreproducible on a new machine. Refresh it by opening the URL
# in a browser - Cloudflare passes those - and saving the JSON over this one.
LBMA_CACHE = "gold_final/reference/lbma_gold_pm.json"
# ============================================================================

DATASET = "GLBX.MDP3"
PARENT = "GC.FUT"
START = "2015-01-01"

# The LBMA Gold Price PM auction starts at 15:00 London. COMEX gold settles on
# the 13:29:30-13:30:00 New York window.
AUCTION_HOUR, AUCTION_MINUTE = 15, 0
SETTLE_HOUR, SETTLE_MINUTE = 13, 30
PAD_MINUTES = 5              # either side of each instant

STAT_SETTLEMENT, STAT_OPEN_INTEREST = 3, 9
MONTH_CODES = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
               "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}
MIN_OI = 100                 # ignore contracts with almost no open interest
REQUEST_SPACING_S = 2.0

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import zstandard

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
ARCH = ROOT / ARCHIVE_DIR
MINUTE = ROOT / MINUTE_DIR
OUT = ROOT / OUT_DIR
LONDON, NEW_YORK, UTC = ZoneInfo("Europe/London"), ZoneInfo("America/New_York"), ZoneInfo("UTC")
OUTRIGHT = re.compile(r"^GC([FGHJKMNQUVXZ])(\d{1,2})$")


def say(text: str = "") -> None:
    print(text, flush=True)


def head(text: str) -> None:
    say("")
    say("=" * 74)
    say(text)
    say("=" * 74)


def api_key() -> str:
    env = ROOT / ENV_FILE
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABENTO_API_KEY=") and len(line) > 18:
                return line.split("=", 1)[1].strip()
    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    if key:
        return key
    raise SystemExit(f"no DATABENTO_API_KEY found; add it to {env}")


# ---------------------------------------------------------------------------
# 1. The curve
# ---------------------------------------------------------------------------
def _zst(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    raw = zstandard.ZstdDecompressor().decompress(zf.read(name))
    return pd.read_csv(io.StringIO(raw.decode()))


def _archive(kind: str) -> zipfile.ZipFile:
    for p in sorted(ARCH.glob("*.zip")):
        zf = zipfile.ZipFile(p)
        if any(kind in n for n in zf.namelist()):
            return zf
    raise SystemExit(
        f"no Databento archive containing '{kind}' under {ARCH}.\n"
        f"  These are batch downloads and are not in git. Re-request them from\n"
        f"  Databento: dataset {DATASET}, symbols {PARENT}, stype_in=parent,\n"
        f"  schema '{kind}', from {START}.")


def resolve_years(symbols: pd.Series, obs_years: pd.Series) -> pd.Series:
    """Contract year for each ROW, not for each symbol.

    Databento writes some vintages with a one-digit year, so "GCZ5" is December
    2015 in 2015 and December 2025 in 2025. Resolving the year once per symbol
    therefore dates every recent observation of a reused code to the decade it
    first appeared, which puts first notice a decade in the past and silently
    drops the whole modern sample. It has to be done against each observation's
    own date.
    """
    dig = symbols.str.extract(OUTRIGHT)[1]
    two = dig.str.len() == 2
    year = pd.Series(index=symbols.index, dtype="float64")
    year[two] = 2000 + pd.to_numeric(dig[two], errors="coerce")
    # One digit: the nearest year ending in that digit, searching from the year
    # before the observation. A contract trades at most about five years out.
    d1 = pd.to_numeric(dig[~two], errors="coerce")
    base = obs_years[~two] - 1
    year[~two] = base + ((d1 - base) % 10)
    return year


def first_notice(year: int, month: int) -> pd.Timestamp:
    """Last business day of the month before delivery. A position has to be
    closed or rolled before this to avoid delivery, so it - not last trade - is
    the horizon the carry is earned over. Exchange holidays are ignored, which
    is a documented approximation worth at most one day."""
    d = pd.Timestamp(year=year, month=month, day=1) - pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d


def build_contracts() -> pd.DataFrame:
    head("STAGE 1  The futures curve, from the statistics archive")
    zf = _archive("statistics")
    names = sorted(n for n in zf.namelist()
                   if "statistics" in n and n.endswith(".zst"))
    say(f"   {len(names)} daily statistics files")
    frames = []
    for i, name in enumerate(names):
        d = _zst(zf, name)
        d = d[d.stat_type.isin([STAT_SETTLEMENT, STAT_OPEN_INTEREST])]
        if len(d):
            frames.append(d[["ts_event", "stat_type", "price", "quantity", "symbol"]])
        if i and i % 1000 == 0:
            say(f"      {i}/{len(names)}")
    s = pd.concat(frames, ignore_index=True)
    s["date"] = pd.to_datetime(s.ts_event, format="mixed", utc=True) \
        .dt.tz_convert(None).dt.normalize()

    settle = (s[s.stat_type == STAT_SETTLEMENT].sort_values("ts_event")
              .groupby(["date", "symbol"], as_index=False).price.last()
              .rename(columns={"price": "settle"}))
    oi = (s[s.stat_type == STAT_OPEN_INTEREST].sort_values("ts_event")
          .groupby(["date", "symbol"], as_index=False).quantity.last()
          .rename(columns={"quantity": "open_interest"}))
    d = settle.merge(oi, on=["date", "symbol"], how="outer")

    say("   attaching the delivery calendar")
    parts = d.symbol.str.extract(OUTRIGHT)
    d = d[parts[0].notna()].copy()          # drops spreads and non-outrights
    d["contract_month"] = parts.loc[d.index, 0].map(MONTH_CODES).astype(int)
    d["contract_year"] = resolve_years(d.symbol, d.date.dt.year).astype(int)
    pairs = d[["contract_year", "contract_month"]].drop_duplicates()
    pairs["first_notice"] = [first_notice(y, m) for y, m
                             in zip(pairs.contract_year, pairs.contract_month)]
    d = d.merge(pairs, on=["contract_year", "contract_month"], how="left")
    d["days_to_first_notice"] = (d.first_notice - d.date).dt.days
    d = d.sort_values(["date", "symbol"])
    say(f"   {len(d):,} contract-days, "
        f"{d.date.min():%Y-%m-%d} to {d.date.max():%Y-%m-%d}")
    return d


# ---------------------------------------------------------------------------
# 2. The two instants
# ---------------------------------------------------------------------------
def build_instants(contracts: pd.DataFrame) -> pd.DataFrame:
    head("STAGE 2  The two instants, day by day")
    say("   The auction is 15:00 London; the settlement window ends 13:30 New")
    say("   York. Both are converted to UTC on each date, so the gap follows the")
    say("   two countries' clock changes instead of being assumed constant.")

    live = contracts[(contracts.days_to_first_notice > 0)
                     & (contracts.open_interest.fillna(0) >= MIN_OI)
                     & contracts.settle.notna()]
    lead = (live.sort_values(["date", "open_interest"])
            .groupby("date", as_index=False).last()[["date", "symbol",
                                                     "days_to_first_notice"]]
            .rename(columns={"symbol": "lead_contract"}))

    rows = []
    for _, r in lead.iterrows():
        day = r.date.date()
        auc = datetime(day.year, day.month, day.day, AUCTION_HOUR,
                       AUCTION_MINUTE, tzinfo=LONDON).astimezone(UTC)
        stl = datetime(day.year, day.month, day.day, SETTLE_HOUR,
                       SETTLE_MINUTE, tzinfo=NEW_YORK).astimezone(UTC)
        rows.append({"date": r.date, "lead_contract": r.lead_contract,
                     "days_to_first_notice": r.days_to_first_notice,
                     "auction_utc": auc.replace(tzinfo=None),
                     "settle_utc": stl.replace(tzinfo=None),
                     "gap_hours": (stl - auc).total_seconds() / 3600.0})
    d = pd.DataFrame(rows)
    counts = d.gap_hours.value_counts()
    say("")
    say(f"   {len(d):,} trading days, {d.date.min():%Y-%m-%d} to {d.date.max():%Y-%m-%d}")
    for gap, n in counts.items():
        say(f"      gap of {gap:.1f}h on {n:,} days")
    say("   The two gaps are the three weeks a year when one country has changed")
    say("   its clocks and the other has not. Assuming a constant offset would")
    say("   mis-time the New York leg by an hour on those days.")
    return d


# ---------------------------------------------------------------------------
# 3. The minute bars
# ---------------------------------------------------------------------------
def minute_files() -> dict[str, Path]:
    """Existing minute files, keyed by the period they cover. Early years were
    bought whole; later ones month by month after a run was interrupted and the
    year-level checkpoint lost a paid request."""
    out = {}
    for p in sorted(MINUTE.glob("gc_minute_*.csv")):
        stem = p.stem.replace("gc_minute_", "")
        out[stem] = p
    return out


def wanted_periods(instants: pd.DataFrame) -> list[str]:
    have = set(minute_files())
    want = []
    for ts in pd.period_range(instants.date.min(), instants.date.max(), freq="M"):
        if f"{ts.year}" in have:            # a whole-year file covers it
            continue
        key = f"{ts.year}{ts.month:02d}"
        if key not in have:
            want.append(key)
    return want


def buy_minutes(periods: list[str], instants: pd.DataFrame) -> None:
    import databento as db
    client = db.Historical(api_key())
    for key in periods:
        y, m = int(key[:4]), int(key[4:])
        lo = pd.Timestamp(year=y, month=m, day=1)
        hi = lo + pd.offsets.MonthEnd(1)
        sub = instants[(instants.date >= lo) & (instants.date <= hi)]
        if sub.empty:
            continue
        syms = sorted(sub.lead_contract.unique())
        start = (sub.auction_utc.min() - timedelta(minutes=PAD_MINUTES * 2))
        end = (sub.settle_utc.max() + timedelta(minutes=PAD_MINUTES * 2))
        say(f"   buying {key}: {len(syms)} contracts, {start:%Y-%m-%d} .. {end:%Y-%m-%d}")
        time.sleep(REQUEST_SPACING_S)
        data = client.timeseries.get_range(
            dataset=DATASET, schema="ohlcv-1m", symbols=syms,
            start=start.isoformat(), end=end.isoformat())
        df = data.to_df()
        df.to_csv(MINUTE / f"gc_minute_{key}.csv")
        say(f"      {len(df):,} bars")


def build_minute_windows(instants: pd.DataFrame, allow_buy: bool) -> pd.DataFrame:
    head("STAGE 3  Minute bars around each instant")
    missing = wanted_periods(instants)
    if missing:
        say(f"   {len(missing)} month(s) not on disk: {', '.join(missing[:8])}"
            + (" ..." if len(missing) > 8 else ""))
        # Ask here rather than at launch. This is the only point that knows
        # whether anything actually needs buying, and the list above has just
        # been printed, so the question is answerable. A flag set before the run
        # is a decision made before its cost is visible.
        if not allow_buy:
            try:
                allow_buy = input(f"   Buy these {len(missing)} month(s) from "
                                  f"Databento? This costs money. [y/N] "
                                  ).strip().lower() in ("y", "yes")
            except EOFError:
                # No attached stdin - piped, scheduled, or under a harness.
                # Refuse, rather than dying on a traceback: the safe direction
                # for a branch that spends money is always "no".
                allow_buy = False
        if not allow_buy:
            raise SystemExit(
                "   Nothing bought. Everything through the months already on\n"
                "   disk still builds.")
        buy_minutes(missing, instants)
    else:
        say(f"   every month already on disk under {MINUTE.relative_to(ROOT)} "
            f"- nothing to buy")

    files = sorted(minute_files().values())
    say(f"   reading {len(files)} files")
    frames = []
    inst = instants.set_index("date")
    for p in files:
        d = pd.read_csv(p, usecols=lambda c: c in
                        ("ts_event", "symbol", "close", "volume"))
        d["ts_event"] = pd.to_datetime(d.ts_event, format="mixed", utc=True) \
            .dt.tz_convert(None)
        d["date"] = d.ts_event.dt.normalize()
        d = d.join(inst, on="date", how="inner")
        d = d[d.symbol == d.lead_contract]
        # Keep only the bars within PAD_MINUTES of either instant. Everything
        # between them was bought as one contiguous block because that is
        # cheaper than two ranges, but nothing in the middle is used.
        da = (d.ts_event - d.auction_utc).dt.total_seconds() / 60.0
        ds = (d.ts_event - d.settle_utc).dt.total_seconds() / 60.0
        a = d[da.abs() <= PAD_MINUTES].assign(instant="auction",
                                              minutes_from=da[da.abs() <= PAD_MINUTES])
        s = d[ds.abs() <= PAD_MINUTES].assign(instant="settle",
                                              minutes_from=ds[ds.abs() <= PAD_MINUTES])
        frames.append(pd.concat([a, s], ignore_index=True))
    d = pd.concat(frames, ignore_index=True)
    d = d[["date", "ts_event", "symbol", "instant", "minutes_from", "close",
           "volume"]].sort_values(["date", "instant", "minutes_from"])
    say(f"   {len(d):,} bars kept, on {d.date.nunique():,} days "
        f"({len(d) / max(d.date.nunique(), 1):.0f} a day)")
    both = d.groupby("date").instant.nunique()
    say(f"   {int((both == 2).sum()):,} days have both instants, "
        f"{int((both == 1).sum()):,} have only one")
    return d


# ---------------------------------------------------------------------------
# 4. The free series
# ---------------------------------------------------------------------------
def _fetch(url: str) -> bytes:
    time.sleep(REQUEST_SPACING_S)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read()
    except Exception:
        # Both endpoints stall under urllib on this machine from time to time
        # while curl fetches them without trouble.
        return subprocess.run(["curl", "-sS", "-m", "120", "-A",
                               "GOLD-research/1.0", url],
                              check=True, capture_output=True).stdout


def build_lbma() -> pd.DataFrame:
    head("STAGE 4  The London benchmark and the short rates")
    # prices.lbma.org.uk began returning 403 from behind Cloudflare to
    # non-browser clients. Try it anyway - it may come back - and fall back to
    # the cached copy, saying which one was used rather than failing or, worse,
    # silently serving stale data as though it were fresh.
    raw = None
    try:
        body = _fetch("https://prices.lbma.org.uk/json/gold_pm.json")
        if body.lstrip()[:1] in (b"[", b"{"):
            raw = json.loads(body)
            say("   LBMA: fetched live")
        else:
            say("   LBMA: live endpoint returned HTML (Cloudflare 403)")
    except Exception as e:
        say(f"   LBMA: live fetch failed ({type(e).__name__})")
    if raw is None:
        cache = ROOT / LBMA_CACHE
        if not cache.exists():
            raise SystemExit(
                f"   and no cached copy at {cache}.\n"
                f"   Download gold_pm.json by hand from prices.lbma.org.uk in a\n"
                f"   browser and save it there, or point LBMA_CACHE elsewhere.")
        raw = json.loads(cache.read_text(encoding="utf-8"))
        say(f"   LBMA: using the cached copy at {cache.relative_to(ROOT)}")
    d = pd.DataFrame({"date": [r["d"] for r in raw],
                      "lbma_pm_usd": [r["v"][0] if r.get("v") else None
                                      for r in raw]})
    d["date"] = pd.to_datetime(d.date)
    d = d.dropna(subset=["lbma_pm_usd"]).sort_values("date")
    d = d[d.date >= START]
    say(f"   LBMA PM: {len(d):,} days, {d.date.min():%Y-%m-%d} to {d.date.max():%Y-%m-%d}")
    return d


def build_rates() -> pd.DataFrame:
    out = None
    for sid in ("SOFR", "DTB3"):
        raw = _fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
        d = pd.read_csv(io.BytesIO(raw))
        d.columns = ["date", sid.lower()]
        d["date"] = pd.to_datetime(d.date)
        d[sid.lower()] = pd.to_numeric(d[sid.lower()], errors="coerce")
        d = d.dropna()
        out = d if out is None else out.merge(d, on="date", how="outer")
        say(f"   {sid}: {len(d):,} days")
    return out.sort_values("date")


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buy", action="store_true",
                    help="allow Databento purchases without being asked; "
                         "without it you are prompted once, if anything is "
                         "missing")
    args = ap.parse_args()
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)

    head("DATABENTO AND THE SPREAD'S OTHER INPUTS")
    say(f"   archives  {ARCH.relative_to(ROOT)}")
    say(f"   minutes   {MINUTE.relative_to(ROOT)}")
    say(f"   writing   {OUT.relative_to(ROOT)}")

    contracts = build_contracts()
    contracts.to_csv(OUT / "comex_contract_daily.csv", index=False)

    instants = build_instants(contracts)
    instants.to_csv(OUT / "timing_instants.csv", index=False)

    windows = build_minute_windows(instants, args.buy)
    windows.to_csv(OUT / "gc_minute_windows.csv", index=False)

    build_lbma().to_csv(OUT / "lbma_pm.csv", index=False)
    build_rates().to_csv(OUT / "short_rates.csv", index=False)

    head("DONE")
    for name in ("comex_contract_daily.csv", "timing_instants.csv",
                 "gc_minute_windows.csv", "lbma_pm.csv", "short_rates.csv"):
        p = OUT / name
        say(f"   {name:28s} {p.stat().st_size / 1e6:7.1f} MB")
    say("")
    say("   Nothing here is committed: the repo gitignores *.csv and these")
    say("   rebuild from the archives without spending anything.")


if __name__ == "__main__":
    main()
