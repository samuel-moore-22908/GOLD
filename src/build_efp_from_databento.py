"""
Build a properly roll-controlled COMEX gold futures series and the
EFP (Exchange for Physical) implied-rate dislocation, from Databento's
per-contract GLBX.MDP3 data.

This SUPERSEDES src/pull_build_efp_series.py, which used Yahoo Finance's
opaque GC=F continuous series and an approximated delivery calendar. The
differences that matter:

  1. SETTLEMENT price, not close. CME's official daily settlement (the
     number used for margining, and the number a dealer quotes an EFP
     against) is not the last trade of the session. Databento exposes it
     as stat_type=3 in the `statistics` schema. Enum verified against the
     official `databento_dbn.StatType` (3=SETTLEMENT_PRICE, 9=OPEN_INTEREST,
     6=CLEARED_VOLUME) rather than guessed.
  2. Real per-contract data, so days-to-delivery is computed from the
     ACTUAL contract being priced (GCZ5 -> December 2025) rather than
     assuming the next active month on the calendar.
  3. Open-interest-based roll. The "front month" by calendar is often not
     the liquid contract; practitioners quote the most-active contract.
     Rolling on open interest reproduces that, and the roll date is then
     an output of the data rather than a convention I imposed.

Inputs (manually downloaded, see DATA_SOURCES.md):
  data/databento/GLBX-*-*.zip  (two jobs: ohlcv-1d and statistics, both
                                symbols=GC.FUT, stype_in=parent, 2015-2026)
Also uses: LBMA PM fix (pulled live), FRED SOFR/DFF (pulled live).

Outputs:
  data/processed/comex_contract_daily.csv   per-contract settle/OI/volume
  data/processed/efp_dislocation_v2.csv     the roll-controlled EFP series
"""
import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests
import zstandard

DATABENTO_DIR = Path("data/databento")
OUT_CONTRACTS = "data/processed/comex_contract_daily.csv"
OUT_EFP = "data/processed/efp_dislocation_v2.csv"

STAT_SETTLEMENT = 3
STAT_OPEN_INTEREST = 9

# COMEX gold contract month codes. Gold's "active" months are
# Feb/Apr/Jun/Aug/Oct/Dec, but all twelve are listed and occasionally
# carry open interest, so parse all of them.
MONTH_CODES = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
               "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}

# Outright contracts only: "GC" + month code + 1-2 digit year.
# Excludes spreads like "GCJ5-GCV5" (which carry negative prices).
OUTRIGHT_RE = re.compile(r"^GC([FGHJKMNQUVXZ])(\d{1,2})$")


def parse_symbol(symbol, obs_date):
    """GCZ5 -> (2025, 12). Databento uses 1-digit years for some vintages
    and 2-digit for others; disambiguate the 1-digit case against the
    observation date, since a contract trades at most ~5 years ahead."""
    m = OUTRIGHT_RE.match(symbol)
    if not m:
        return None
    mon = MONTH_CODES[m.group(1)]
    ydigits = m.group(2)
    if len(ydigits) == 2:
        year = 2000 + int(ydigits)
    else:
        # single digit: pick the nearest future year ending in that digit
        d = int(ydigits)
        base = obs_date.year
        candidates = [y for y in range(base - 1, base + 8) if y % 10 == d]
        year = min(candidates, key=lambda y: abs(y - base))
    return year, mon


def delivery_reference(year, month):
    """COMEX gold delivery runs through the contract month; first notice
    day is the last business day of the month PRIOR to the delivery month.
    A position must be closed or rolled before first notice to avoid
    delivery, so first notice - not last trade - is the economically
    relevant horizon for the carry calculation."""
    first_of_month = pd.Timestamp(year=year, month=month, day=1)
    prior_month_end = first_of_month - pd.Timedelta(days=1)
    # step back to a weekday (ignores exchange holidays - documented approximation)
    while prior_month_end.weekday() >= 5:
        prior_month_end -= pd.Timedelta(days=1)
    return prior_month_end


def read_zst_csv(zf, name):
    raw = zf.read(name)
    text = zstandard.ZstdDecompressor().decompress(raw).decode()
    return pd.read_csv(io.StringIO(text))


def load_ohlcv():
    path = next(p for p in DATABENTO_DIR.glob("*.zip")
                if any("ohlcv" in n for n in zipfile.ZipFile(p).namelist()))
    zf = zipfile.ZipFile(path)
    name = next(n for n in zf.namelist() if "ohlcv" in n)
    d = read_zst_csv(zf, name)
    d["date"] = pd.to_datetime(d["ts_event"]).dt.tz_localize(None).dt.normalize()
    return d[["date", "symbol", "open", "high", "low", "close", "volume"]]


def load_statistics():
    path = next(p for p in DATABENTO_DIR.glob("*.zip")
                if any("statistics" in n for n in zipfile.ZipFile(p).namelist()))
    zf = zipfile.ZipFile(path)
    names = sorted(n for n in zf.namelist() if "statistics" in n and n.endswith(".zst"))
    print(f"  {len(names)} daily statistics files")
    frames = []
    for i, name in enumerate(names):
        d = read_zst_csv(zf, name)
        d = d[d["stat_type"].isin([STAT_SETTLEMENT, STAT_OPEN_INTEREST])]
        if len(d):
            frames.append(d[["ts_event", "stat_type", "price", "quantity", "symbol"]])
        if i % 500 == 0:
            print(f"    {i}/{len(names)}")
    s = pd.concat(frames, ignore_index=True)
    s["date"] = pd.to_datetime(s["ts_event"]).dt.tz_localize(None).dt.normalize()
    return s


def main():
    print("Loading Databento OHLCV ...")
    ohlcv = load_ohlcv()
    print(f"  {len(ohlcv)} rows")

    print("Loading Databento statistics (settlement + open interest) ...")
    stats = load_statistics()
    print(f"  {len(stats)} settlement/OI rows")

    settle = (stats[stats.stat_type == STAT_SETTLEMENT]
              .sort_values("ts_event")
              .groupby(["date", "symbol"], as_index=False)["price"].last()
              .rename(columns={"price": "settle"}))
    oi = (stats[stats.stat_type == STAT_OPEN_INTEREST]
          .sort_values("ts_event")
          .groupby(["date", "symbol"], as_index=False)["quantity"].last()
          .rename(columns={"quantity": "open_interest"}))

    c = settle.merge(oi, on=["date", "symbol"], how="outer") \
              .merge(ohlcv[["date", "symbol", "volume", "close"]], on=["date", "symbol"], how="left")

    parsed = c.apply(lambda r: parse_symbol(r["symbol"], r["date"]), axis=1)
    c["contract_year"] = [p[0] if p else None for p in parsed]
    c["contract_month"] = [p[1] if p else None for p in parsed]
    c = c.dropna(subset=["contract_year"])  # drops spreads and any odd symbols
    c["contract_year"] = c["contract_year"].astype(int)
    c["contract_month"] = c["contract_month"].astype(int)
    c["first_notice"] = [delivery_reference(y, m) for y, m in zip(c.contract_year, c.contract_month)]
    c["days_to_first_notice"] = (c["first_notice"] - c["date"]).dt.days
    c.to_csv(OUT_CONTRACTS, index=False)
    print(f"Wrote {len(c)} contract-days to {OUT_CONTRACTS}")

    # ---- most-active contract per day, by open interest ----
    # Only consider contracts still ahead of first notice: once past it,
    # a contract's price reflects the delivery process, not carry.
    live = c[(c.days_to_first_notice > 0) & c.settle.notna()].copy()
    live["oi_rank"] = live.groupby("date")["open_interest"].rank(ascending=False, method="first")
    front = live[live.oi_rank == 1].copy()
    front = front[["date", "symbol", "settle", "open_interest", "volume",
                   "contract_year", "contract_month", "days_to_first_notice"]]
    front = front.rename(columns={"symbol": "active_contract", "settle": "comex_settle"})

    # ---- LBMA PM fix (London spot benchmark) ----
    print("Fetching LBMA PM fix ...")
    r = requests.get("https://prices.lbma.org.uk/json/gold_pm.json",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    lbma = pd.DataFrame(r.json())
    lbma["date"] = pd.to_datetime(lbma["d"])
    lbma["lbma_pm_usd"] = lbma["v"].apply(lambda v: v[0])
    lbma = lbma[["date", "lbma_pm_usd"]]

    # ---- short rate: SOFR from 2018-04, DFF (effective fed funds) before ----
    print("Fetching FRED rates ...")
    def fred(series, start, end):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}&coed={end}"
        d = pd.read_csv(url, na_values=".")
        d["date"] = pd.to_datetime(d["observation_date"])
        return d[["date", series]].dropna().rename(columns={series: "short_rate"})
    rate = pd.concat([fred("DFF", "2015-01-01", "2018-04-02"),
                      fred("SOFR", "2018-04-03", "2026-08-21")]).drop_duplicates("date").sort_values("date")

    d = front.merge(lbma, on="date", how="inner").merge(rate, on="date", how="left")
    d["short_rate"] = d["short_rate"].ffill() / 100.0

    # ---- the EFP calculation ----
    # Raw basis, in dollars, is what a dealer quotes. Converting it to an
    # annualized implied financing rate removes the roll sawtooth (a $ basis
    # mechanically shrinks to zero as delivery approaches, regardless of
    # market stress) and makes 2015's zero-rate regime comparable to 2025's.
    d["basis_usd"] = d["comex_settle"] - d["lbma_pm_usd"]
    d["implied_rate"] = (d["comex_settle"] / d["lbma_pm_usd"] - 1) * 365 / d["days_to_first_notice"]
    STORAGE = 0.0025  # 0.25%/yr assumed all-in vault storage+insurance; no free public series exists
    d["carry_rate"] = d["short_rate"] + STORAGE
    d["dislocation"] = d["implied_rate"] - d["carry_rate"]
    # Dollar-equivalent dislocation: what the basis would have to be, at this
    # horizon, to represent pure carry - and how far it actually sits from that.
    d["carry_implied_basis_usd"] = d["lbma_pm_usd"] * d["carry_rate"] * d["days_to_first_notice"] / 365
    d["excess_basis_usd"] = d["basis_usd"] - d["carry_implied_basis_usd"]

    d["storage_rate_assumed"] = STORAGE
    d["source"] = "Databento GLBX.MDP3 (settlement+OI) + LBMA PM + FRED SOFR/DFF"
    d = d.sort_values("date").reset_index(drop=True)
    d.to_csv(OUT_EFP, index=False)
    print(f"Wrote {len(d)} rows to {OUT_EFP}")
    print(f"Date range {d.date.min().date()} to {d.date.max().date()}")
    print("\nTariff-episode window:")
    w = d[(d.date >= "2024-11-01") & (d.date <= "2025-09-01")]
    print(w.set_index("date").resample("ME").agg(
        contract=("active_contract", "last"),
        settle=("comex_settle", "mean"),
        lbma=("lbma_pm_usd", "mean"),
        basis=("basis_usd", "mean"),
        excess_basis=("excess_basis_usd", "mean"),
        dislocation=("dislocation", "mean")).round(3).to_string())


if __name__ == "__main__":
    main()
