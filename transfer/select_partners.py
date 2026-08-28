# -*- coding: utf-8 -*-
"""
Author: Sam Moore
Purpose: Choose the partner list for the HS6 pull, defensibly
Date: 8/28/2026

Census publishes a "Top Trading Partners" page but it ranks only the top 15 in
each category, so the list has to be derived. It is derived here from the
country trade-balance pages -- the same published aggregate that the HS6 pull
reconciles against exactly (Switzerland 2025: $106.21bn both ways).

SELECTION RULE, fixed before looking at any output:

  A. Rank partners by TOTAL goods trade (exports + imports), POOLED over
     2022-2026. Pooled, not a single year, so the list does not hinge on which
     year happens to be picked -- and 2025 in particular is distorted for
     exactly the corridor this project studies.
  B. Take the top 50.
  C. UNION with the top 25 partners by chapter-71 trade, pooled, both
     directions. A partner can be trivial in total trade and central here:
     bullion refining and vaulting concentrate in places that are otherwise
     small. Dropping them to save requests would be choosing the sample on the
     dependent variable.
  D. Report coverage of both total goods trade and chapter-71 trade, so the
     cost of the cut is stated rather than assumed.

Outputs:
    partners_ranked.csv    every partner with both rankings and shares
    partners_selected.csv  the final list, with why each one is in it
"""

import os
import re
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
BALANCE = "https://www.census.gov/foreign-trade/balance/c{code}.html"
UA = {"User-Agent": "gold-flow research"}

YEARS = range(2022, 2027)
TOP_TOTAL = 50
TOP_GOLD = 25
PAUSE = 1.2

MONTHS = ("January February March April May June July August September "
          "October November December").split()
ROW = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{4})\s+"
                 r"(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\b")


def country_totals(code, name):
    """Total goods exports and imports with one partner, USD millions, by month.
    Returns None where Census publishes no page for that code."""
    r = requests.get(BALANCE.format(code=code), headers=UA, timeout=90)
    time.sleep(PAUSE)
    if r.status_code != 200:
        return None
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    rows = [{"year": int(y), "exports": float(e.replace(",", "")),
             "imports": float(i.replace(",", ""))}
            for mo, y, e, i, b in ROW.findall(text)]
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d = d[d.year.isin(YEARS)]
    if d.empty:
        return None
    return {"cty_code": code, "cty_name": name,
            "exports": d.exports.sum(), "imports": d.imports.sum()}


def gold_totals():
    """Chapter 71 trade by partner, pooled, from the gold-tier pull already on
    disk. Both directions, since a vaulting hub shows up on one side only."""
    frames = []
    for f in os.listdir(RAW):
        if f.startswith(("imports_71_", "exports_71_")) and f.endswith(".parquet"):
            frames.append(pd.read_parquet(os.path.join(RAW, f)))
    if not frames:
        raise SystemExit("No gold-tier files in %s. Run the gold pull first." % RAW)
    d = pd.concat(frames, ignore_index=True)
    val = d["GEN_VAL_MO"].fillna(0) + d["ALL_VAL_MO"].fillna(0) \
        if "ALL_VAL_MO" in d.columns else d["GEN_VAL_MO"].fillna(0)
    d = d.assign(v=val)
    return (d.groupby("CTY_CODE", as_index=False)["v"].sum()
             .rename(columns={"CTY_CODE": "cty_code", "v": "ch71_usd"}))


def main():
    from pull_demo import fetch_countries
    countries = fetch_countries()
    print("fetching totals for %d partners ..." % len(countries))

    recs = []
    for n, c in enumerate(countries, 1):
        got = country_totals(c["cty_code"], c["cty_name"])
        if got:
            recs.append(got)
        if n % 40 == 0:
            print("  %d/%d" % (n, len(countries)))

    d = pd.DataFrame(recs)
    d["total"] = d.exports + d.imports
    d = d.sort_values("total", ascending=False).reset_index(drop=True)
    d["rank_total"] = d.index + 1
    d["share_total"] = 100 * d.total / d.total.sum()

    g = gold_totals()
    d = d.merge(g, on="cty_code", how="left")
    d["ch71_usd"] = d.ch71_usd.fillna(0)
    d["rank_ch71"] = d.ch71_usd.rank(ascending=False, method="min").astype(int)
    d["share_ch71"] = 100 * d.ch71_usd / d.ch71_usd.sum()

    by_total = d.rank_total <= TOP_TOTAL
    by_gold = d.rank_ch71 <= TOP_GOLD
    d["selected"] = by_total | by_gold
    d["why"] = ["both" if a and b else "total trade" if a else "chapter 71" if b else ""
                for a, b in zip(by_total, by_gold)]

    d.to_csv(os.path.join(RAW, "partners_ranked.csv"), index=False)
    sel = d[d.selected].sort_values("rank_total")
    sel.to_csv(os.path.join(RAW, "partners_selected.csv"), index=False)

    print("\nSELECTED %d partners" % len(sel))
    print("  by total trade only : %d" % ((by_total & ~by_gold).sum()))
    print("  by chapter 71 only  : %d" % ((by_gold & ~by_total).sum()))
    print("  by both             : %d" % ((by_total & by_gold).sum()))
    print("\nCOVERAGE")
    print("  total goods trade   : %.2f%%" % sel.share_total.sum())
    print("  chapter 71 trade    : %.2f%%" % sel.share_ch71.sum())
    print("\nIn only because of chapter 71 -- the ones a total-trade cut would lose:")
    print(d[by_gold & ~by_total][["cty_code", "cty_name", "rank_total",
                                  "rank_ch71", "share_ch71"]]
          .sort_values("rank_ch71").to_string(index=False))
    print("\nTop 15 by total trade:")
    print(d.head(15)[["rank_total", "cty_name", "total", "share_total",
                      "rank_ch71"]].to_string(index=False))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, HERE)
    main()
