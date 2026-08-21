"""
Extend the Minerals Yearbook world-production-by-country series (2002-2022,
see pull_usgs_historical.py) forward to ~2025 using Mineral Commodity
Summaries (MCS), and cross-check the US figure against the Monthly Mineral
Industry Surveys (MIS) actual monthly data already pulled.

Why MIS alone can't do this: MIS (pull_usgs_gold_series.py) only reports US
production by *state*, not other countries - it has no world/country
breakdown at all. MCS is the USGS product that actually carries a
world-by-country table with much less publication lag than the Minerals
Yearbook (Feb-2026-dated MCS already has 2025-estimated figures).

Limitation this doesn't get around: MCS's world table only names the ~13
largest producers each year (varies slightly by edition) plus an "Other
countries" catch-all. China and the United States are named in every
edition checked; India, the UK and Switzerland are not (all three are far
too small to be broken out - UK and Switzerland aren't real gold-mining
countries at all, per the Minerals Yearbook data already pulled). So this
extends the CHN and USA series to ~2025; it cannot do the same for IND,
GBR or CHE - those stay capped at the Minerals Yearbook's 2022.

Output: data/processed/usgs_production_by_country_extended.csv
        (Minerals Yearbook 2002-2022 + MCS-derived 2023-2025 for the
        countries MCS names; US row also cross-checked against MIS)
"""
import re

import pandas as pd
import requests

MYB_PATH = "data/processed/usgs_myb_world_production_by_country.csv"
MIS_PATH = "data/processed/usgs_gold_monthly.csv"
OUT = "data/processed/usgs_production_by_country_extended.csv"

MCS_YEARS = [2023, 2024, 2025, 2026]  # each covers (edition_year - 2) final + (edition_year - 1) estimated
MCS_URL = "https://pubs.usgs.gov/periodicals/mcs{y}/mcs{y}-gold.pdf"

ROW_RE = re.compile(r"^([A-Za-z][A-Za-z .'\-]+?)\s+e?([\d,]+)\s+([\d,]+)\s")


def pull_mcs_table(edition_year):
    import pypdf

    r = requests.get(MCS_URL.format(y=edition_year), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    path = f"data/raw/usgs_historical/mcs{edition_year}-gold.pdf"
    open(path, "wb").write(r.content)

    reader = pypdf.PdfReader(path)
    text = reader.pages[1].extract_text()
    start = text.find("World Mine Production")
    end = text.find("World Resources")
    block = text[start:end]

    # Header line gives the two years this edition's table covers, e.g.
    # "2023 2024e" - first is final, second is the edition's own estimate.
    m = re.search(r"(\d{4})\s+(\d{4})e", block)
    if not m:
        return []
    year_final, year_est = int(m.group(1)), int(m.group(2))

    rows = []
    for line in block.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        country = m.group(1).strip()
        if country in ("Mine production", "World total (rounded)", "Other countries"):
            continue
        try:
            v_final = float(m.group(2).replace(",", ""))
            v_est = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        rows.append({"year": year_final, "country": country, "mine_production_t_mcs": v_final, "mcs_edition": edition_year, "mcs_status": "final_or_revised"})
        rows.append({"year": year_est, "country": country, "mine_production_t_mcs": v_est, "mcs_edition": edition_year, "mcs_status": "estimated"})
    return rows


def main():
    myb = pd.read_csv(MYB_PATH)
    myb = myb.rename(columns={"mine_production_kg": "mine_production_t"})
    myb["mine_production_t"] = myb["mine_production_t"] / 1000  # kg -> t, to match MCS units
    myb["source"] = "USGS Minerals Yearbook Table 8"

    print("Pulling MCS editions for country production ...")
    mcs_rows = []
    for y in MCS_YEARS:
        try:
            rows = pull_mcs_table(y)
            mcs_rows.extend(rows)
            print(f"  {y}: {len(rows)} rows")
        except Exception as e:
            print(f"  {y}: failed ({e})")

    mcs = pd.DataFrame(mcs_rows)
    # Prefer the later edition's figure for a given year - "final_or_revised"
    # from a later edition beats an earlier edition's "estimated" guess.
    mcs = mcs.sort_values(["mcs_edition", "mcs_status"]).drop_duplicates(subset=["year", "country"], keep="last")
    mcs = mcs.rename(columns={"mine_production_t_mcs": "mine_production_t"})
    mcs["source"] = "USGS Mineral Commodity Summaries"

    # Only extend years beyond what Minerals Yearbook already covers.
    extension = mcs[mcs.year > myb.year.max()]
    combined = pd.concat(
        [myb[["year", "country", "mine_production_t", "source"]],
         extension[["year", "country", "mine_production_t", "source"]]],
        ignore_index=True,
    ).sort_values(["country", "year"])
    combined.to_csv(OUT, index=False)
    print(f"\nWrote {len(combined)} rows to {OUT}")

    print("\nUnited States and China, extended through MCS:")
    print(combined[combined.country.isin(["United States", "China"])].tail(16).to_string())

    print("\nCross-check: MIS actual monthly US production, summed to annual, vs MCS estimate:")
    mis = pd.read_csv(MIS_PATH, parse_dates=["date"])
    mis["year"] = mis.date.dt.year
    mis_annual = mis.groupby("year")["total_production_kg"].sum() / 1000  # kg -> t
    mcs_us = combined[(combined.country == "United States") & (combined.year >= mis_annual.index.min())]
    print(pd.DataFrame({"mis_annual_t": mis_annual}).join(mcs_us.set_index("year")["mine_production_t"].rename("mcs_t")))


if __name__ == "__main__":
    main()
