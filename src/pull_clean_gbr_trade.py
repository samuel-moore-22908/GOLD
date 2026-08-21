"""
Pull UK gold trade with USA, Switzerland, India and China directly from
HMRC's uktradeinfo OTS API (free, no key, OData v4:
https://api.uktradeinfo.com) and clean it into the same tidy HS4 monthly
panel format as src/clean_us_trade_data.py.

Covers HS 7108 (non-monetary gold) and HS 7115.90 (other articles of
precious metal, n.e.s.) — 7115.90 is included on the same logic as the US
pull: it isn't gold-specific by description (could include silver/platinum
articles), but excluding it would have missed most of the US tariff-episode
flow, so the same trade-off is taken here rather than risk under-counting.
7115.10 (platinum catalysts) is excluded — not gold-relevant at all.

Output: data/processed/gbr_gold_trade_hs4_monthly.csv
Also caches the raw API pull at data/raw/hmrc/ots_gbr_partners.json for
provenance/debugging.
"""
import json
import time
import urllib.parse
import urllib.request

import pandas as pd

API = "https://api.uktradeinfo.com/OTS"
RAW_CACHE = "data/raw/hmrc/ots_gbr_partners.json"
OUT = "data/processed/gbr_gold_trade_hs4_monthly.csv"

COUNTRIES = {39: "Switzerland", 400: "United States", 664: "India", 720: "China"}
ISO3 = {"Switzerland": "CHE", "United States": "USA", "India": "IND", "China": "CHN"}
FLOW = {3: "import", 4: "export"}  # non-EU import/export; all 4 partners are non-EU

# HS 7108 (all subheadings) + HS 7115.90 only (7115.10 platinum catalysts excluded).
COMMODITIES = [
    71081100, 71081200, 71081310, 71081380, 71082000,  # 7108.xx
    71159000, 71159010, 71159090,                        # 7115.90.xx
]

START_MONTH, END_MONTH = 201501, 202612


def fetch_commodity(commodity_id):
    country_clause = " or ".join(f"CountryId eq {c}" for c in COUNTRIES)
    filt = (
        f"CommodityId eq {commodity_id} and ({country_clause}) "
        f"and MonthId ge {START_MONTH} and MonthId le {END_MONTH}"
    )
    url = f"{API}?{urllib.parse.urlencode({'$filter': filt})}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)["value"]


def main():
    rows = []
    for commodity_id in COMMODITIES:
        rows.extend(fetch_commodity(commodity_id))
        time.sleep(2)  # be polite; a burst of requests got rate-limited earlier

    import os
    os.makedirs("data/raw/hmrc", exist_ok=True)
    with open(RAW_CACHE, "w") as f:
        json.dump(rows, f)

    d = pd.DataFrame(rows)
    d = d[d["FlowTypeId"].isin(FLOW)].copy()

    d["date"] = pd.to_datetime(d["MonthId"].astype(str), format="%Y%m")
    d["reporter_iso3"] = "GBR"
    d["country"] = d["CountryId"].map(COUNTRIES)
    d["country_iso3"] = d["country"].map(ISO3)
    d["flow"] = d["FlowTypeId"].map(FLOW)
    d["hs4"] = d["CommodityId"].astype(str).str[:4].astype(int)
    d["value_usd"] = pd.NA  # HMRC values are GBP, not USD — see note
    d["value_gbp"] = d["Value"].astype(float)
    d["net_mass_kg"] = d["NetMass"].astype(float)

    out = (
        d.groupby(["date", "reporter_iso3", "country", "country_iso3", "flow", "hs4"], as_index=False)
        [["value_gbp", "net_mass_kg"]].sum()
    )
    out["quality"] = "reported"
    out["source"] = "HMRC uktradeinfo OTS API (api.uktradeinfo.com)"
    out["note"] = (
        "Value in GBP, not USD (unlike the US file) — convert before combining. "
        "net_mass_kg is a genuine quantity field, unlike the US pull which was "
        "value-only. hs4=7115 covers only the 7115.90 subheading (articles of "
        "precious metal, n.e.s.) — not gold-specific by description; included "
        "anyway since the equivalent US code carried most of the tariff-episode "
        "flow. This pull has no domestic-export/re-export split like the US "
        "Census data does — HMRC's OTS dataset reports UK imports/exports "
        "undifferentiated by that dimension."
    )

    out = out.sort_values(["country", "flow", "date"]).reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")
    print(out.groupby(["country", "flow"])[["value_gbp", "net_mass_kg"]].agg(["count", "sum"]))


if __name__ == "__main__":
    main()
