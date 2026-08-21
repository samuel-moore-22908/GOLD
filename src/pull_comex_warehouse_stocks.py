"""
Reconstruct the COMEX gold warehouse stocks daily series (RESEARCH_DOSSIER.md
§7 open problem #1, "the 15-month COMEX hole") from Wayback Machine
snapshots of CME's own live report.

CME's site blocks direct access outright (403/connection failures on every
path tried), and the report itself has no date picker or historical
archive on cmegroup.com's live site (confirmed by the user). But
`cmegroup.com/delivery_reports/Gold_Stocks.xls` is a *fixed* URL that
always serves "today's" report, and the Internet Archive has crawled it
intermittently since 2012 - so each Wayback snapshot is effectively a
free historical data point, dated by the report's own "Activity Date"
field (not the crawl timestamp, which can be a day or two off, e.g. a
Monday crawl showing Friday's activity).

Output: data/processed/comex_gold_stocks_daily.csv
Also caches every fetched raw .xls under data/raw/comex_wayback/.
"""
import io
import os
import re
import time

import pandas as pd
import requests

CDX_URL = "https://web.archive.org/cdx/search/cdx"
TARGET = "cmegroup.com/delivery_reports/Gold_Stocks.xls"
RAW_DIR = "data/raw/comex_wayback"
OUT = "data/processed/comex_gold_stocks_daily.csv"


def list_snapshots():
    for attempt in range(8):
        try:
            r = requests.get(
                CDX_URL,
                params={"url": TARGET, "output": "json", "limit": 100000, "collapse": "timestamp:8"},
                timeout=60,
            )
            r.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 7:
                raise
            time.sleep(5 * (attempt + 1))
    rows = r.json()[1:]  # drop header row
    return [row[1] for row in rows if row[4] == "200"]  # statuscode == 200


def fetch_snapshot(timestamp, retries=8):
    cache_path = f"{RAW_DIR}/{timestamp}.xls"
    if os.path.exists(cache_path):
        return cache_path
    url = f"https://web.archive.org/web/{timestamp}id_/https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            r.raise_for_status()
            os.makedirs(RAW_DIR, exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(r.content)
            return cache_path
        except requests.exceptions.RequestException as e:
            last_exc = e
            # Connection refusals here look like local/network throttling
            # rather than an archive.org rate-limit response (no HTTP 429
            # seen) - back off and retry rather than giving up immediately.
            time.sleep(5 * (attempt + 1))
    raise last_exc


def parse_report(path, crawl_timestamp):
    d = pd.read_excel(path, header=None)
    header_block = d.iloc[:12, 6].astype(str).str.cat(sep=" | ")
    m_report = re.search(r"Report Date:\s*(\d{1,2}/\d{1,2}/\d{4})", header_block)
    m_activity = re.search(r"Activity Date:\s*(\d{1,2}/\d{1,2}/\d{4})", header_block)
    if not m_activity:
        return None
    activity_date = pd.to_datetime(m_activity.group(1))

    def total_row(label):
        row = d[d[0].astype(str).str.strip() == label]
        if row.empty:
            return None
        return float(row.iloc[0, 7])  # "TOTAL TODAY" column

    return {
        "date": activity_date,
        "report_date": pd.to_datetime(m_report.group(1)) if m_report else None,
        "crawl_timestamp": crawl_timestamp,
        "registered_oz": total_row("TOTAL REGISTERED"),
        "pledged_oz": total_row("TOTAL PLEDGED"),
        "eligible_oz": total_row("TOTAL ELIGIBLE"),
        "combined_total_oz": total_row("COMBINED TOTAL"),
    }


def main():
    print("Listing Wayback snapshots ...")
    timestamps = list_snapshots()
    print(f"  {len(timestamps)} snapshots found")

    rows = []
    for i, ts in enumerate(timestamps):
        try:
            path = fetch_snapshot(ts)
            row = parse_report(path, ts)
            if row:
                rows.append(row)
        except Exception as e:
            print(f"  [{ts}] skipped: {e}")
        if i % 20 == 0:
            print(f"  {i+1}/{len(timestamps)} ...")
        time.sleep(3)  # paced conservatively after hitting connection refusals at 1s

    d = pd.DataFrame(rows).drop_duplicates(subset="date").sort_values("date")
    d["registered_tonnes"] = d["registered_oz"] / 32150.7
    d["eligible_tonnes"] = d["eligible_oz"] / 32150.7
    d["combined_total_tonnes"] = d["combined_total_oz"] / 32150.7
    d["quality"] = "reported"
    d["source"] = "CME Gold_Stocks.xls via Wayback Machine snapshot (cmegroup.com blocks direct access)"
    d["note"] = (
        "date = report's own Activity Date field, not the Wayback crawl "
        "timestamp (can differ by a day or two, e.g. weekend gaps). "
        "Snapshot cadence is irregular (whenever Internet Archive happened "
        "to crawl), not daily - gaps remain between snapshots. Registered "
        "and eligible kept separate per RESEARCH_DOSSIER.md guidance - "
        "reclassification between them is a phantom signal in its own right."
    )
    d.to_csv(OUT, index=False)
    print(f"\nWrote {len(d)} dated observations to {OUT}")
    print(f"Date range: {d.date.min()} to {d.date.max()}")


if __name__ == "__main__":
    main()
