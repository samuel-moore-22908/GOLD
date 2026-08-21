"""
Pull the pieces needed for the EFP (Exchange for Physical) proxy described
in RESEARCH_DOSSIER.md §5 and compute the implied-rate dislocation series.

Sources (all free, no key, confirmed live):
- LBMA Gold Price PM fix (USD) — prices.lbma.org.uk/json/gold_pm.json.
  Stands in for "XAU Curncy" (the London spot benchmark).
- COMEX gold *continuous front-month* future — Yahoo Finance chart API,
  symbol GC=F. Stands in for "GC1 Comdty". This is Yahoo's own continuous
  series, not built from individual contract months — CME's own site
  403s every request tried against it (Akamai-style bot wall, not just a
  UA check like BAZG's CloudFront), and Yahoo does not retain price
  history for *expired* individual contract months (confirmed: GCZ23,
  GCZ24, GCZ15 all 404 "may be delisted"), only whichever contracts are
  still listed today. So there is no way to reconstruct a truly
  roll-controlled series from free sources — see the days-to-delivery
  approximation below and the caveats in the note column.
- SOFR (FRED, from 2018-04-03 — SOFR did not exist before then) plus DFF,
  the effective fed funds rate (FRED, full 2015+ coverage), spliced in for
  the pre-SOFR period as the carry rate's short-rate component.

NOT pulled here — needs manual/paid access:
- The true dealer EFP (Bloomberg contributed pages, entitlement-gated —
  see DATA_SOURCES.md §D2). What's built here is the dossier's own stated
  free substitute (a synthetic GC1-XAU basis), not the real thing.
- CME's own official settlement history, if a source more authoritative
  than Yahoo's continuous series is wanted for GC1 — CME's site blocks
  all direct access from here.
- A real gold lease-rate series (GOFO discontinued 2015; implied lease
  is derivable from this script's output, but the dealer-quoted lease
  rate the dossier discusses as a cross-check is not free/pullable).

Output: data/processed/efp_dislocation_daily.csv
"""
import datetime as dt

import pandas as pd
import requests

OUT = "data/processed/efp_dislocation_daily.csv"
START, END = "2015-01-01", "2026-08-21"

# COMEX gold active contract months: Feb, Apr, Jun, Aug, Oct, Dec.
ACTIVE_MONTHS = [2, 4, 6, 8, 10, 12]
STORAGE_RATE = 0.0025  # 0.25%/yr — a commonly-cited typical vault storage
                        # cost; not a pulled series (none is free/public),
                        # documented assumption, easy to override.


def fetch_lbma_pm():
    r = requests.get("https://prices.lbma.org.uk/json/gold_pm.json", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    d = pd.DataFrame(r.json())
    d["date"] = pd.to_datetime(d["d"])
    d["xau_usd"] = d["v"].apply(lambda v: v[0])
    return d[["date", "xau_usd"]]


def fetch_gc1(start, end):
    p1 = int(dt.datetime.strptime(start, "%Y-%m-%d").timestamp())
    p2 = int(dt.datetime.strptime(end, "%Y-%m-%d").timestamp())
    r = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
        params={"period1": p1, "period2": p2, "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    ts = result["timestamp"]
    close = result["indicators"]["quote"][0]["close"]
    d = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").normalize(), "gc1_usd": close})
    return d.dropna(subset=["gc1_usd"])


def fetch_fred(series_id, start, end):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}&coed={end}"
    d = pd.read_csv(url, na_values=".")
    d["date"] = pd.to_datetime(d["observation_date"])
    return d[["date", series_id]].dropna()


def days_to_delivery(date):
    """Approximate days from `date` to the next COMEX active-month
    delivery date, treating the 1st of the next active month (at least 5
    days out) as the delivery reference point. This is a documented
    APPROXIMATION, not a true roll-controlled calendar — see module
    docstring for why a real one isn't buildable from free sources."""
    y, m = date.year, date.month
    for _ in range(14):
        if m in ACTIVE_MONTHS:
            candidate = pd.Timestamp(year=y, month=m, day=1)
            if (candidate - date).days >= 5:
                return (candidate - date).days
        m += 1
        if m > 12:
            m = 1
            y += 1
    raise RuntimeError("no active month found within lookahead window")


def main():
    print("Fetching LBMA PM fix (XAU proxy) ...")
    xau = fetch_lbma_pm()
    xau = xau[(xau.date >= START) & (xau.date <= END)]
    print(f"  {len(xau)} rows")

    print("Fetching COMEX GC=F continuous front-month (GC1 proxy) ...")
    gc1 = fetch_gc1(START, END)
    print(f"  {len(gc1)} rows")

    print("Fetching SOFR (2018-04+) and DFF (pre-2018 fallback) ...")
    sofr = fetch_fred("SOFR", "2018-04-01", END)
    dff = fetch_fred("DFF", START, "2018-04-30")
    rate = pd.concat(
        [dff.rename(columns={"DFF": "short_rate"}), sofr.rename(columns={"SOFR": "short_rate"})]
    ).drop_duplicates(subset="date").sort_values("date")
    print(f"  {len(rate)} rate observations")

    d = gc1.merge(xau, on="date", how="inner").merge(rate, on="date", how="left")
    d["short_rate"] = d["short_rate"].ffill() / 100.0  # FRED reports percent
    d["days_to_delivery"] = d["date"].apply(days_to_delivery)

    # implied_rate = (GC1/XAU - 1) * 365 / days_to_delivery  (RESEARCH_DOSSIER.md §5)
    d["implied_rate"] = (d["gc1_usd"] / d["xau_usd"] - 1) * 365 / d["days_to_delivery"]
    d["carry_rate"] = d["short_rate"] + STORAGE_RATE
    d["dislocation"] = d["implied_rate"] - d["carry_rate"]

    d["storage_rate_assumed"] = STORAGE_RATE
    d["source"] = "LBMA (XAU) + Yahoo Finance GC=F (GC1 proxy) + FRED (SOFR/DFF)"
    d["note"] = (
        "gc1_usd is Yahoo's continuous front-month series, not a roll-"
        "controlled series built from individual contracts (none available "
        "free — see script docstring). days_to_delivery is an approximation "
        "(next active-month 1st, >=5 days out), not the true delivery "
        "calendar. storage_rate is an assumed constant (0.25%/yr), not a "
        "pulled series. Treat dislocation as directionally indicative, not "
        "precise enough for the kink estimate without a real GC1 series."
    )

    d = d.sort_values("date").reset_index(drop=True)
    d.to_csv(OUT, index=False)
    print(f"\nWrote {len(d)} rows to {OUT}")
    print(d[["date", "gc1_usd", "xau_usd", "days_to_delivery", "implied_rate", "dislocation"]].tail(10).to_string())


if __name__ == "__main__":
    main()
