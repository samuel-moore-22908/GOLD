"""
Pull primary-source event documents for RESEARCH_DOSSIER.md's event-dummy
table (DATA_SOURCES.md §F): the reciprocal tariff EO and the CBP gold-bar
classification ruling history.

Federal Register (federalregister.gov/developers, free, no key):
Generic term searches for "gold"/"gold bullion"/"non-monetary gold"/the
literal HTS code all returned zero or noise - the actual gold carve-out
lives in an EO's Annex II product-exclusion table, which isn't part of
the full-text-indexed document body. What worked: searching "reciprocal
tariffs" as a phrase and picking out the master EO by date. So this
script fetches full metadata for the specific document numbers identified
by hand (see EVENT_DOCS below) rather than re-deriving them by search,
since the search itself isn't reliable for this purpose.

CBP CROSS (rulings.cbp.gov/api/search, free, no key, real JSON API):
Search for "gold bar" surfaces the full classification history, including
the exact ruling the dossier's event table already cites (31 Jul 2025) -
and incidentally confirms *why* so much investment-grade bar-form gold
shows up under HS 7108.13 rather than 7108.12: Chapter 71 Additional
U.S. Note 1(a) excludes cast bars that have been stamped/lasered with
identifying marks (logo, serial number, QR code - i.e. essentially all
branded COMEX/LBMA bars) from the "unwrought" 7108.12 classification.

Output: data/processed/federal_register_events.csv
        data/processed/cbp_gold_bar_rulings.csv
"""
import pandas as pd
import requests

FR_API = "https://www.federalregister.gov/api/v1/documents"
CBP_API = "https://rulings.cbp.gov/api/search"

# Identified by hand via the "reciprocal tariffs" search - see docstring.
EVENT_DOCS = {
    "2025-06063": "Reciprocal tariff EO (14257) - establishes the tariff regime whose Annex II exempted gold",
    "2025-06378": "Amendment to reciprocal tariffs - low-value China imports",
    "2025-06462": "Modifying reciprocal tariff rates - retaliation/alignment",
    "2025-09297": "Modifying reciprocal tariff rates - China discussions",
}


def pull_federal_register():
    rows = []
    for doc_number, note in EVENT_DOCS.items():
        r = requests.get(
            f"{FR_API}/{doc_number}.json",
            params={"fields[]": ["title", "publication_date", "html_url", "pdf_url", "executive_order_number", "type"]},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=20,
        )
        r.raise_for_status()
        d = r.json()
        d["note"] = note
        rows.append(d)
    return pd.DataFrame(rows)


def pull_cbp_rulings():
    r = requests.get(CBP_API, params={"term": "gold bar", "pageSize": 50}, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    rulings = r.json()["rulings"]
    d = pd.DataFrame(rulings)
    d = d.sort_values("rulingDate")
    d["note"] = ""
    d.loc[d.rulingNumber == "N351466", "note"] = (
        "The 31 Jul 2025 ruling in DATA_SOURCES.md §F - PAMP Gold Kilo Bar and "
        "100 Oz Bar (the standard COMEX-delivery bars) ruled INTO 7108.13.5500 "
        "(semi-manufactured) rather than 7108.12.10 (unwrought) because casting "
        "plus stamping/lasering identifying marks counts as 'further processing' "
        "under Ch.71 Add'l U.S. Note 1(a)."
    )
    d.loc[d.rulingNumber == "H266605", "note"] = (
        "2018 revocation of an earlier gold-rounds ruling, reclassified 7114.19 "
        "- CBP's bar/round classification has been actively revised over time, "
        "not a single fixed rule."
    )
    return d


def main():
    fr = pull_federal_register()
    fr.to_csv("data/processed/federal_register_events.csv", index=False)
    print(f"Wrote {len(fr)} rows to data/processed/federal_register_events.csv")

    cbp = pull_cbp_rulings()
    cbp.to_csv("data/processed/cbp_gold_bar_rulings.csv", index=False)
    print(f"Wrote {len(cbp)} rows to data/processed/cbp_gold_bar_rulings.csv")
    print(cbp[["rulingNumber", "rulingDate", "subject", "tariffs"]].to_string())


if __name__ == "__main__":
    main()
