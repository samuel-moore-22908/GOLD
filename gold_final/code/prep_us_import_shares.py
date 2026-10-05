"""The share of each destination's gold imports that comes from the United States.

WHY THIS EXISTS. Comparing US gold exports to a country against that country's
FULL gold demand is apples to oranges: every one of these places buys gold from
many suppliers. The benchmark that matters is the part of their demand the
United States could plausibly be serving, so each destination's demand is
scaled by the share of its gold imports the United States supplies.

WHAT IT CAN SOURCE, AND WHAT IT CANNOT. Three of the five destinations have a
usable public source. Two do not, and this script says so rather than guessing:

  INDIA        Metals Focus / World Gold Council publish India's GROSS BULLION
               IMPORTS annually in the Gold Demand Trends workbook; the Census
               partner series gives US exports to India. Share = the ratio.
               Covers 2015-2025. Median 4.2%.

  UNITED       HMRC's Overseas Trade Statistics API (api.uktradeinfo.com, free,
  KINGDOM      no key) gives monthly imports by commodity and partner. Summing
               HS 7108 and 7115.90 over all partners gives the denominator and
               CountryId 400 the numerator. Covers 2015-2026. Median 15.8%.
               NOTE both EU (FlowTypeId 1) and non-EU (3) import flows must be
               summed; querying one alone understates the total badly.

  SWITZERLAND  BAZG publish a gold-specific open dataset, "Foreign trade - Gold
               imports by country", with country detail and quantity in kg.
               Covers 2021-2026 and tariff 7108.12 only - unwrought
               non-monetary gold, which is the bullion line that matters.
               Median 13.3%. Years before 2021 take the median.

  HONG KONG    No source found. The Census and Statistics Department API needs
  SINGAPORE    a table ID this script does not have, and SingStat's Table
               Builder returns 403 without credentials. Both are left at 100%,
               which is the CONSERVATIVE choice: scaling a demand benchmark
               down can only raise the ratio of flow to demand, so an unscaled
               destination understates the mismatch rather than overstating it.
               Their combined demand is about 11 tonnes a quarter against the
               five's 37, so the aggregate moves little either way.

Run:  .venv\\Scripts\\python.exe gold_final\\code\\prep_us_import_shares.py
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ============================ EDIT THIS IF YOU MOVE THE PROJECT ==============
REPO_ROOT = r"C:\Users\smoor\GitHub\GOLD"
OUT_DIR = r"gold_final/data/raw"
# ============================================================================

ROOT = Path(REPO_ROOT).expanduser().resolve()
UA = {"User-Agent": "GOLD-research/1.0 (samuel.moore.econresearch@gmail.com)"}
SPACING_S = 2.0            # deliberate pacing, not maximal

HMRC_API = "https://api.uktradeinfo.com/OTS"
HMRC_CODES = [71081100, 71081200, 71081310, 71081380, 71082000,
              71159000, 71159010, 71159090]
HMRC_US = 400              # HMRC CountryId for the United States
BAZG_CSV = ("https://ocean.bazg.admin.ch/open-data-reports/"
            "TN8_controlCode_Gold_IMP_en_v1/TN8_controlCode_Gold_IMP_en_v1.csv")
OZ_PER_T = 32150.7


def get(url: str, timeout: int = 180) -> bytes:
    time.sleep(SPACING_S)
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def uk_share(pd):
    """UK: HMRC OTS, all partners vs the United States. Both flow types."""
    rows = []
    for code in HMRC_CODES:
        for flow in (1, 3):                 # EU import, non-EU import
            filt = (f"CommodityId eq {code} and FlowTypeId eq {flow} "
                    f"and MonthId ge 201501 and MonthId le 202612")
            url = f"{HMRC_API}?{urllib.parse.urlencode({'$filter': filt})}"
            try:
                rows.extend(json.loads(get(url, 120).decode())["value"])
            except Exception as e:
                print(f"   UK: {code}/{flow} failed ({type(e).__name__})")
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d["year"] = d.MonthId.astype(str).str[:4].astype(int)
    tot = d.groupby("year").Value.sum()
    us = d[d.CountryId == HMRC_US].groupby("year").Value.sum()
    return (us / tot).dropna().rename("share")


def che_share(pd):
    """Switzerland: BAZG gold imports by country, quantity in kg."""
    raw = get(BAZG_CSV)
    d = pd.read_csv(io.BytesIO(raw), sep=";", low_memory=False)
    if d.shape[1] == 1:
        d = pd.read_csv(io.BytesIO(raw), low_memory=False)
    tot = d.groupby("year").Quantity_kg.sum()
    us = d[d.Country_isoAlpha2 == "US"].groupby("year").Quantity_kg.sum()
    return (us / tot).dropna().rename("share")


def ind_share(pd):
    """India: WGC/Metals Focus gross bullion imports vs US exports to India."""
    sup = ROOT / OUT_DIR / "wgc_india_supply_annual.csv"
    par = ROOT / OUT_DIR / "us_gold_partner_monthly.csv"
    lbm = ROOT / OUT_DIR / "lbma_pm.csv"
    for f in (sup, par, lbm):
        if not f.exists():
            print(f"   India: {f.name} missing - run prep_wgc_demand.py and "
                  "pull_us_customs.py first")
            return None
    imports = pd.read_csv(sup).set_index("year").gross_bullion_imports_t
    px = (pd.read_csv(lbm, parse_dates=["date"]).set_index("date")
            .lbma_pm_usd.resample("MS").mean())
    p = pd.read_csv(par, parse_dates=["date"], dtype={"cty_code": str})
    e = p[(p.flow == "exports") & (p.cty_code == "5330")].copy()
    e["t"] = e.value_usd / (e.date.map(px) * OZ_PER_T)
    us = e.groupby(e.date.dt.year).t.sum()
    return (us / imports).dropna().rename("share")


def main() -> None:
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas required: .venv/Scripts/python.exe -m pip install pandas")

    sources = {
        "india": ("Metals Focus / World Gold Council gross bullion imports; "
                  "US Census partner exports", ind_share),
        "united_kingdom": ("HMRC Overseas Trade Statistics API "
                           "(api.uktradeinfo.com)", uk_share),
        "switzerland": ("BAZG open data, Foreign trade - Gold imports by "
                        "country (tariff 7108.12)", che_share),
    }
    frames = []
    for slug, (src, fn) in sources.items():
        print(f"   {slug} ...")
        s = fn(pd)
        if s is None or s.empty:
            print(f"   {slug}: no share computed")
            continue
        print(f"   {slug}: median {100 * s.median():.1f}%  "
              f"({int(s.index.min())}-{int(s.index.max())}, "
              f"min {100 * s.min():.1f}%, max {100 * s.max():.1f}%)")
        for y, v in s.items():
            frames.append({"country": slug, "year": int(y),
                           "us_import_share": float(v), "source": src})

    # Destinations with no public source stay unscaled, recorded explicitly so
    # the figure can show that the choice was made rather than overlooked.
    for slug in ("hong_kong", "singapore"):
        frames.append({"country": slug, "year": -1, "us_import_share": "",
                       "source": "NOT SOURCED - left unscaled, which is "
                                 "conservative (scaling down raises the ratio)"})

    out = ROOT / OUT_DIR / "us_import_shares.csv"
    pd.DataFrame(frames).to_csv(out, index=False)
    print(f"   wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
