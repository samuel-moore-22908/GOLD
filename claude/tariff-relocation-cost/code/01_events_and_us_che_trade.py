"""
Step 1. Pin the tariff-episode event chronology to primary documents, and pull
total US-Switzerland goods trade.

Two outputs:

  output/events.csv                     the datable policy events, with document ids
  output/us_che_goods_trade_monthly.csv  total US<->CHE goods trade, monthly, USD mn

The event work extends what src/pull_event_dates.py already did. That script
pinned EO 14257 (7 Apr 2025) and CBP ruling N351466 (31 Jul 2025) but recorded
the August/September 2025 resolution as "not pinned to a document". It is
pinnable: EO 14346 of 5 September 2025 (FR doc 2025-17507, 90 FR 43743) carries
a replacement Annex II to EO 14257 in which every HTSUS gold line is marked
"Addition" -- except 7108.12.10, which was already there. This script downloads
the Federal Register PDF and verifies that pattern rather than asserting it,
because the annexes are appendices that the Federal Register's full-text search
does not index (searching the API for "7108" over Aug 2025 - Mar 2026 returns
nothing relevant).

The Census leg uses the country trade-balance page rather than the timeseries
API, because api.census.gov now rejects unkeyed requests. The balance page is
the same published aggregate, needs no key, and is what we want: TOTAL goods
trade with Switzerland, not just chapter 71.
"""
import io
import json
import re
import time

import pandas as pd
import requests
from pypdf import PdfReader

OUT = "claude/tariff-relocation-cost/output"
UA = {"User-Agent": "gold-flow-deconvolution research (samuel.moore.econresearch@gmail.com)"}
PAUSE = 2.0  # deliberate pacing between third-party API calls

GOLD_LINE = re.compile(r"\b(710[68]\.\d{2}\.\d{2})\b")


def fr_document(doc_number):
    r = requests.get(
        "https://www.federalregister.gov/api/v1/documents/{}.json".format(doc_number),
        params={"fields[]": ["title", "publication_date", "signing_date",
                             "document_number", "executive_order_number",
                             "html_url", "pdf_url"]},
        headers=UA, timeout=60,
    )
    r.raise_for_status()
    time.sleep(PAUSE)
    return r.json()


def parse_eo14346_gold_annex(pdf_url):
    """Return the gold/silver HTSUS lines in EO 14346's Annex II and whether each
    is flagged 'Addition' (newly excluded) or was already on the exclusion list."""
    r = requests.get(pdf_url, headers=UA, timeout=180)
    r.raise_for_status()
    time.sleep(PAUSE)
    reader = PdfReader(io.BytesIO(r.content))
    pages = [(i, p.extract_text() or "") for i, p in enumerate(reader.pages)]

    annex2_start = next(i for i, t in pages
                        if "ANNEX II" in t and "not covered by the duties" in t)
    annex2 = "\n".join(t for i, t in pages if i >= annex2_start)

    # Each entry is "<code> <description> [Addition]", but the PDF extractor
    # interleaves description and code, so match on the code and inspect the
    # ~90 characters that follow for the Notes-column flag.
    flags = {}
    for m in GOLD_LINE.finditer(annex2):
        code = m.group(1)
        tail = annex2[m.end():m.end() + 90]
        is_add = re.match(r"[^\d]{0,60}Addition", tail) is not None
        flags[code] = flags.get(code, False) or is_add

    # Annex I inserts the same lines into ch.99 U.S. note 2(v)(iii) -- the list
    # of provisions carved out of the reciprocal-duty mechanism itself.
    annex1_page = next(t for i, t in pages
                       if "ANNEX I" in t and "subchapter III of chapter 99" in t)
    annex1_codes = sorted(set(GOLD_LINE.findall(annex1_page)))

    annex2_df = pd.DataFrame(sorted(flags.items()), columns=["htsus", "newly_excluded"])
    return annex2_df, annex1_codes


def census_country_trade(cty_code=4419, country="Switzerland"):
    """Monthly total goods exports/imports/balance with one partner, USD millions."""
    url = "https://www.census.gov/foreign-trade/balance/c{}.html".format(cty_code)
    r = requests.get(url, headers=UA, timeout=90)
    r.raise_for_status()
    time.sleep(PAUSE)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))

    months = ("January February March April May June July August September "
              "October November December").split()
    # Rows render as "<Month> <Year> <exports> <imports> <balance>" once tags
    # are stripped. The annual "TOTAL <Year> ..." rows do not match, which is
    # what we want -- they would double-count.
    pat = re.compile(
        r"\b(" + "|".join(months) + r")\s+(\d{4})\s+"
        r"(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\b")

    rows = []
    for m in pat.finditer(text):
        mon, yr, exp, imp, bal = m.groups()
        rows.append({
            "date": pd.Timestamp(int(yr), months.index(mon) + 1, 1),
            "partner": country,
            "us_exports_usdmn": float(exp.replace(",", "")),
            "us_imports_usdmn": float(imp.replace(",", "")),
            "us_balance_usdmn": float(bal.replace(",", "")),
        })
    d = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
    d["source"] = "US Census Bureau, Trade in Goods with {} (c{})".format(country, cty_code)
    return d


def main():
    events = []

    eo14257 = fr_document("2025-06063")
    events.append({
        "date": eo14257["publication_date"],
        "signing_date": eo14257.get("signing_date"),
        "label": "EO 14257 reciprocal tariff; Annex II excludes 7108.12.10 only",
        "tariff_risk_on_gold": "off (unwrought only)",
        "document": "EO {} / FR {}".format(eo14257["executive_order_number"],
                                           eo14257["document_number"]),
        "url": eo14257["html_url"],
    })

    eo14346 = fr_document("2025-17507")
    annex2, annex1_codes = parse_eo14346_gold_annex(eo14346["pdf_url"])
    events.append({
        "date": eo14346["publication_date"],
        "signing_date": eo14346.get("signing_date"),
        "label": "EO 14346 replaces Annex II; adds the 7108.13 bar lines to the exclusion list",
        "tariff_risk_on_gold": "off (all forms)",
        "document": "EO {} / FR {}".format(eo14346["executive_order_number"],
                                           eo14346["document_number"]),
        "url": eo14346["html_url"],
    })

    # CBP N351466 was already pulled by src/pull_event_dates.py into
    # data/processed/cbp_gold_bar_rulings.csv -- re-read rather than re-query.
    cbp = pd.read_csv("data/processed/cbp_gold_bar_rulings.csv")
    hit = cbp[cbp["rulingNumber"].astype(str).str.contains("351466")]
    ruling_date = hit["rulingDate"].iloc[0][:10] if len(hit) else "2025-07-31"
    events.append({
        "date": ruling_date,
        "signing_date": ruling_date,
        "label": "CBP N351466: cast/stamped bars are 7108.13.5500, not unwrought; adds 9903.01.25",
        "tariff_risk_on_gold": "ON",
        "document": "CBP CROSS ruling N351466",
        "url": "https://rulings.cbp.gov/ruling/N351466",
    })

    events.append({
        "date": "2024-11-05", "signing_date": "2024-11-05",
        "label": "US presidential election", "tariff_risk_on_gold": "rises",
        "document": "(not a document)", "url": "",
    })

    ev = pd.DataFrame(events).sort_values("date").reset_index(drop=True)
    # EO 14346 sec. 2(a): the replacement Annex II binds on entries made on or
    # after 12:01 a.m. EDT three days after the order's date.
    ev["market_effective"] = ev["signing_date"]
    ev.loc[ev["document"].str.startswith("EO 14346"), "market_effective"] = "2025-09-08"

    ev.to_csv(OUT + "/events.csv", index=False)
    annex2.to_csv(OUT + "/eo14346_annex2_gold_lines.csv", index=False)

    che = census_country_trade()
    che.to_csv(OUT + "/us_che_goods_trade_monthly.csv", index=False)

    meta = {
        "eo14346_annex1_ch99_carveout_codes": annex1_codes,
        "eo14346_annex2_gold_lines": annex2.to_dict("records"),
        "eo14346_effective": ("12:01 a.m. EDT 8 Sep 2025 "
                              "(sec. 2(a): three days after the 5 Sep order)"),
        "census_coverage": [str(che["date"].min().date()), str(che["date"].max().date())],
        "note": (
            "The classification hole is visible in the annex itself. 7108.12.10 "
            "(unwrought bullion and dore) carries no 'Addition' flag because EO "
            "14257's original Annex II already excluded it. Every other gold line "
            "-- including 7108.13.55, the line CBP N351466 put COMEX-deliverable "
            "cast bars into -- is flagged 'Addition', i.e. it was NOT excluded "
            "between 7 Apr and 8 Sep 2025."
        ),
    }
    with open(OUT + "/events_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(ev.to_string(index=False))
    print()
    print(annex2.to_string(index=False))
    print()
    print("Census US-CHE:", che["date"].min().date(), "->", che["date"].max().date(),
          "({} months)".format(len(che)))


if __name__ == "__main__":
    main()
