"""
Pull India's gold trade with USA, UK, Switzerland and China directly from
the Commerce Ministry's TradeStat FTSPCC tool (tradestat.commerce.gov.in),
"Commodity x Country wise (Monthly)" report — the only one of the site's
four products (EIDB, MEIDB, FTPA, FTSPCC) that supports a monthly date
*range* combined with a specific commodity and a specific country in one
query.

No documented API: this replicates the site's own plain HTML form POST
(confirmed via a live test — despite wire:model attributes suggesting
Livewire, the form actually submits as an ordinary POST to a Laravel
route and returns the results as a server-rendered HTML table).

Scope caveat (confirmed by manually cross-checking two single-month MEIDB
"Country-wise Principal commodity wise all HSCode" pulls against this
series): the "GOLD" principal-commodity bucket (code G6) used here covers
HS 7108.12/7108.13 plus HS 7118.90 (coin) — it does NOT include any HS 7115
codes. Unlike the US/UK/CHE pulls, there is no way to reach 7115 through
this site's commodity classification, so this India series is missing
whatever the 7115.90 equivalent would be. Values only — no quantity field
in this report despite it labelling itself "UNIT: KGS" in the page header.

Output: data/processed/ind_gold_trade_monthly.csv
"""
import re
import time

import pandas as pd
import requests

BASE = "https://tradestat.commerce.gov.in/ftspcc"
COUNTRIES = {423: "United States", 421: "United Kingdom", 389: "Switzerland", 77: "China"}
ISO3 = {"United States": "USA", "United Kingdom": "GBR", "Switzerland": "CHE", "China": "CHN"}
GOLD_CODE = "G6"
FROM_MONTH, FROM_YEAR = 1, 2015
TO_MONTH, TO_YEAR = 6, 2026

OUT = "data/processed/ind_gold_trade_monthly.csv"

FLOWS = {
    "export": {
        "page": f"{BASE}/export_commodity_xcountry_wise_monthly",
        "fields": lambda country: {
            "FmonthCme": FROM_MONTH, "FyearCme": FROM_YEAR,
            "TmonthCme": TO_MONTH, "TyearCme": TO_YEAR,
            "PCommodityCme": GOLD_CODE, "countryCme": country,
        },
    },
    "import": {
        "page": f"{BASE}/import_commodity_xcountry_wise_monthly",
        "fields": lambda country: {
            "frommonth": FROM_MONTH, "fromyear": FROM_YEAR,
            "tomonth": TO_MONTH, "toyear": TO_YEAR,
            "PCommodityCmi": GOLD_CODE, "countryCmi": country,
        },
    },
}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}

ROW_RE = re.compile(
    r'<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d{4})</td>\s*<td[^>]*>(\w+)</td>\s*'
    r'<td[^>]*>([\d,.]+)</td>\s*<td[^>]*>([\d,.]+)</td>',
    re.S,
)


def fetch_flow(session, flow, flow_cfg, country_id):
    # Fresh GET each time to get a CSRF token matched to the current session
    # state — a token from an earlier response gets rejected (HTTP 419) once
    # the session has moved on.
    page = session.get(flow_cfg["page"], timeout=30)
    m = re.search(r'_token"\s*value="([^"]+)"', page.text)
    token = m.group(1)

    data = {"_token": token, **flow_cfg["fields"](country_id)}
    resp = session.post(flow_cfg["page"], data=data, timeout=60, headers={"Referer": flow_cfg["page"]})
    resp.raise_for_status()

    rows = []
    for _, year, mon, rs_crore, usd_million in ROW_RE.findall(resp.text):
        rows.append(
            {
                "date": pd.Timestamp(year=int(year), month=MONTHS[mon], day=1),
                "reporter_iso3": "IND",
                "country": COUNTRIES[country_id],
                "country_iso3": ISO3[COUNTRIES[country_id]],
                "flow": flow,
                "value_usd": float(usd_million.replace(",", "")) * 1_000_000,
                "value_inr_crore": float(rs_crore.replace(",", "")),
            }
        )
    return rows


def main():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    all_rows = []
    for flow, flow_cfg in FLOWS.items():
        for country_id in COUNTRIES:
            print(f"Fetching {flow} for {COUNTRIES[country_id]} ...")
            rows = fetch_flow(session, flow, flow_cfg, country_id)
            print(f"  {len(rows)} months")
            all_rows.extend(rows)
            time.sleep(2)  # pace requests against this small gov't site

    out = pd.DataFrame(all_rows)
    out["hs4_scope"] = "GOLD bucket (~7108.12/13 + 7118.90; excludes 7115 entirely)"
    out["quality"] = "reported"
    out["source"] = "TradeStat FTSPCC (tradestat.commerce.gov.in), Commodity x Country wise (Monthly)"
    out["note"] = (
        "Value only (US$ Million converted here to raw USD, plus native "
        "Rs. Crore) — this report has no quantity/mass field despite "
        "labelling itself 'UNIT: KGS'. The 'GOLD' principal-commodity "
        "bucket does not include HS 7115 (confirmed by cross-checking "
        "against MEIDB's HS-code-level breakdown for a sample month) — "
        "not comparable in scope to the US/UK/CHE pulls, which do include "
        "7115.90."
    )

    out = out.sort_values(["country", "flow", "date"]).reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {len(out)} rows to {OUT}")
    print(out.groupby(["country", "flow"])["value_usd"].agg(["count", "sum"]))


if __name__ == "__main__":
    main()
