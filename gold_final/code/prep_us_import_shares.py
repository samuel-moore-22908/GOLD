"""One generous US-supplied import share per destination.

WHY A SHARE AT ALL. Comparing US gold exports to a country against that
country's FULL gold demand is apples to oranges: all of these places buy gold
from many suppliers. The benchmark that matters is the part of their demand
the United States could plausibly be serving, so each destination's demand is
scaled by the share of its gold imports the United States supplies.

WHY THE MAXIMUM, NOT THE MEDIAN. The benchmark is demand x share, so a LARGER
share makes the benchmark LARGER and the comparison harder to win. The brief
is to overestimate foreign demand if anything, so this takes, for each
country, the highest share observed across every year, both measurement bases
and every independent source, then rounds up. Applying a single-episode peak
to eleven years of ordinary quarters is itself generous on top of that.

SOURCES, three of them, deliberately overlapping so they can be cross-checked
rather than trusted individually:

  UN COMTRADE   HS 7108 imports, reporter vs world and vs the USA, 2015-2026,
                on BOTH a mass (netWgt) and a value (primaryValue) basis.
                Value has complete coverage where mass does not - many
                reporters file value without net weight, which left
                Switzerland with only two usable years on mass. Where both
                exist they agree to 0.72pp on average, so value is used for
                coverage and mass as the check.

  HMRC          UK Overseas Trade Statistics API. Independent of Comtrade.

  BAZG          Swiss "Foreign trade - Gold imports by country", tariff
                7108.12. Independent of Comtrade.

  METALS FOCUS  India gross bullion imports from the WGC workbook, against
  / WGC         Census partner exports. Independent of Comtrade.

TWO COMTRADE TRAPS, both of which silently corrupt the answer:
  - Switzerland reports as 757 ("Switzerland, Liechtenstein"). Code 756
    returns count:0 with no error at all.
  - Every query returns rows at several aggregation levels, broken out by
    mode of transport and customs procedure as well as the total. Only
    partner2Code=0, motCode=0, customsCode="C00" is the aggregate; summing
    the lot inflates Switzerland roughly fourfold.

Run:  .venv\\Scripts\\python.exe gold_final\\code\\prep_us_import_shares.py
"""

from __future__ import annotations

import io
import json
import math
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
SPACING_S = 2.5

COMTRADE = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
REPORTERS = {"switzerland": 757, "united_kingdom": 826, "hong_kong": 344,
             "singapore": 702, "india": 699}
USA = 842
PERIODS = ",".join(str(y) for y in range(2015, 2027))

HMRC_API = "https://api.uktradeinfo.com/OTS"
HMRC_CODES = [71081100, 71081200, 71081310, 71081380, 71082000,
              71159000, 71159010, 71159090]
BAZG_CSV = ("https://ocean.bazg.admin.ch/open-data-reports/"
            "TN8_controlCode_Gold_IMP_en_v1/TN8_controlCode_Gold_IMP_en_v1.csv")
OZ_PER_T = 32150.7


def key() -> str:
    return next((l.split("=", 1)[1].strip()
                 for l in (ROOT / ".env").read_text().splitlines()
                 if l.startswith("COMTRADE_API_KEY=")), "")


def get(url: str, hdr=None, timeout: int = 180) -> bytes:
    time.sleep(SPACING_S)
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=hdr or UA), timeout=timeout).read()


def comtrade(reporter: int, partner: int, k: str) -> dict[int, dict]:
    p = {"reporterCode": str(reporter), "period": PERIODS, "cmdCode": "7108",
         "flowCode": "M", "partnerCode": str(partner)}
    body = get(COMTRADE + "?" + urllib.parse.urlencode(p),
               {"Ocp-Apim-Subscription-Key": k})
    out = {}
    for r in json.loads(body).get("data", []):
        if (r.get("partner2Code") == 0 and r.get("motCode") == 0
                and str(r.get("customsCode")) == "C00"):
            out[int(r["refYear"])] = {"t": (r.get("netWgt") or 0) / 1000.0,
                                      "usd": r.get("primaryValue") or 0.0}
    return out


def hmrc_max(pd):
    rows = []
    for code in HMRC_CODES:
        for flow in (1, 3):
            f = (f"CommodityId eq {code} and FlowTypeId eq {flow} "
                 f"and MonthId ge 201501 and MonthId le 202612")
            try:
                rows.extend(json.loads(get(
                    f"{HMRC_API}?{urllib.parse.urlencode({'$filter': f})}",
                    timeout=120).decode())["value"])
            except Exception:
                pass
    if not rows:
        return None
    d = pd.DataFrame(rows)
    d["year"] = d.MonthId.astype(str).str[:4].astype(int)
    tot = d.groupby("year").Value.sum()
    us = d[d.CountryId == 400].groupby("year").Value.sum()
    return (us / tot).dropna().max()


def bazg_max(pd):
    raw = get(BAZG_CSV)
    d = pd.read_csv(io.BytesIO(raw), sep=";", low_memory=False)
    if d.shape[1] == 1:
        d = pd.read_csv(io.BytesIO(raw), low_memory=False)
    tot = d.groupby("year").Quantity_kg.sum()
    us = d[d.Country_isoAlpha2 == "US"].groupby("year").Quantity_kg.sum()
    return (us / tot).dropna().max()


def india_max(pd):
    sup = ROOT / OUT_DIR / "wgc_india_supply_annual.csv"
    par = ROOT / OUT_DIR / "us_gold_partner_monthly.csv"
    lbm = ROOT / OUT_DIR / "lbma_pm.csv"
    if not all(f.exists() for f in (sup, par, lbm)):
        return None
    imports = pd.read_csv(sup).set_index("year").gross_bullion_imports_t
    px = (pd.read_csv(lbm, parse_dates=["date"]).set_index("date")
            .lbma_pm_usd.resample("MS").mean())
    p = pd.read_csv(par, parse_dates=["date"], dtype={"cty_code": str})
    e = p[(p.flow == "exports") & (p.cty_code == "5330")].copy()
    e["t"] = e.value_usd / (e.date.map(px) * OZ_PER_T)
    return (e.groupby(e.date.dt.year).t.sum() / imports).dropna().max()


def main() -> None:
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas required")
    k = key()
    if not k:
        sys.exit("COMTRADE_API_KEY not found in .env")

    rows, summary = [], {}
    for name, code in REPORTERS.items():
        world, us = comtrade(code, 0, k), comtrade(code, USA, k)
        sm = sv = None
        for y in sorted(set(world) | set(us)):
            w, u = world.get(y, {}), us.get(y, {})
            a = (u.get("t") / w["t"]) if w.get("t") and u.get("t") else None
            b = (u.get("usd") / w["usd"]) if w.get("usd") and u.get("usd") else None
            rows.append({"country": name, "year": y, "share_mass": a,
                         "share_value": b})
            sm = a if sm is None else (max(sm, a) if a else sm)
            sv = b if sv is None else (max(sv, b) if b else sv)
        summary[name] = {"comtrade_mass_max": sm, "comtrade_value_max": sv}
        print(f"   {name}: comtrade max  mass "
              f"{'n/a' if sm is None else f'{100*sm:.1f}%'}  value "
              f"{'n/a' if sv is None else f'{100*sv:.1f}%'}")

    print("   national cross-checks ...")
    for name, fn in (("united_kingdom", hmrc_max), ("switzerland", bazg_max),
                     ("india", india_max)):
        try:
            v = fn(pd)
        except Exception as e:
            v = None
            print(f"   {name}: national source failed ({type(e).__name__})")
        summary[name]["national_max"] = v
        if v:
            print(f"   {name}: national max {100*v:.1f}%")

    # The generous pick: the highest figure any source reports in any year,
    # rounded UP to the next whole percentage point.
    out = []
    for name, s in summary.items():
        cands = [v for v in s.values() if v]
        pick = math.ceil(100 * max(cands)) / 100 if cands else None
        s["generous_share"] = pick
        out.append({"country": name,
                    "generous_share": pick,
                    "comtrade_value_max": s.get("comtrade_value_max"),
                    "comtrade_mass_max": s.get("comtrade_mass_max"),
                    "national_max": s.get("national_max")})
        print(f"   -> {name}: generous share {100*pick:.0f}%")

    pd.DataFrame(out).to_csv(ROOT / OUT_DIR / "us_import_shares.csv", index=False)
    pd.DataFrame(rows).to_csv(
        ROOT / OUT_DIR / "comtrade_us_import_shares_annual.csv", index=False)
    print(f"   wrote {OUT_DIR}/us_import_shares.csv and the annual series")


if __name__ == "__main__":
    main()
