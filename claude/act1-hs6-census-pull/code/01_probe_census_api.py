"""
Act I, step 1. Probe the Census API before writing the bulk loop.

The bulk pull in step 2 is roughly ten thousand requests. Every hour spent here
saves several there, and there are exactly three things that cannot be settled
from documentation:

  1. HOW TO CHUNK. The pull has to be split into pieces small enough to return
     reliably. Splitting by month alone may or may not work depending on the
     response size limit, and splitting by chapter requires knowing whether the
     commodity predicate accepts a prefix, a comma-separated list, or only an
     exact code. This script tries all four candidate strategies and reports
     which return usable data.

  2. HOW BIG A CHUNK IS. Row counts and payload sizes per (month, chapter)
     determine the total runtime and whether the whole thing fits on disk.

  3. WHAT THE VALUE CONCEPTS ACTUALLY DO. Imports come in two flavours --
     general (GEN_*, everything arriving including into bonded warehouses and
     foreign trade zones) and consumption (CON_*, goods entering the economy).
     For gold that distinction is potentially load-bearing, because metal held
     in a bonded warehouse is exactly the phenomenon under study. The probe
     reports both for chapter 71 so the choice is made on evidence.

FIELD NAMES BELOW ARE NOT GUESSES. They were read from the endpoints' own
variables.json on 27 Aug 2026 (both are public and need no key):

    https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.json
    https://api.census.gov/data/timeseries/intltrade/exports/hs/variables.json

Two asymmetries between the endpoints are easy to get wrong and are handled
explicitly: imports call the quantity field GEN_QY1_MO while exports call it
QTY_1_MO, and only imports carry charges and duty.

Usage:
    set CENSUS_API_KEY=...      (or export, on a POSIX shell)
    python 01_probe_census_api.py

Writes output/probe_report.json and prints a summary.
"""
import itertools
import json
import os
import time

import requests

OUT = "claude/act1-hs6-census-pull/output"
API = "https://api.census.gov/data/timeseries/intltrade/{flow}/hs"
KEY = os.environ.get("CENSUS_API_KEY", "")
PAUSE = 1.5          # deliberate pacing; the probe is small, do not rush it
TIMEOUT = 120

# A month inside the treatment window and one well before it, so the probe
# exercises both the busy and the quiet end of the sample.
PROBE_MONTHS = ["2025-01", "2022-06"]
PROBE_CHAPTERS = ["71", "30", "84"]   # gold; pharma (an Annex II chapter); machinery

# ---------------------------------------------------------------- field sets
# Lean set for the ~5,400-code universe pull. Country names and long
# descriptions are deliberately excluded -- they repeat on every row and are
# cheaper to join afterwards from the concordance file.
UNIVERSE_IMPORT = ["I_COMMODITY", "CTY_CODE", "GEN_VAL_MO", "CON_VAL_MO",
                   "GEN_QY1_MO", "UNIT_QY1"]
UNIVERSE_EXPORT = ["E_COMMODITY", "CTY_CODE", "ALL_VAL_MO", "QTY_1_MO",
                   "UNIT_QY1", "DF"]

# Rich set, used only for chapter 71. Four HS6 codes, so the extra width costs
# almost nothing and buys two things the cost ledger currently has to assume:
#   AIR_CHA_MO / AIR_WGT_MO -> freight and insurance charges per kilogram, on
#       the leg that actually matters, since bullion moves by air
#   CAL_DUT_MO              -> duty actually calculated, which is how you show
#       from the primary source that nothing was collected on gold
GOLD_IMPORT = UNIVERSE_IMPORT + [
    "GEN_CIF_MO", "GEN_CHA_MO", "CON_CHA_MO", "CON_CIF_MO",
    "AIR_VAL_MO", "AIR_WGT_MO", "AIR_CHA_MO",
    "VES_VAL_MO", "VES_WGT_MO", "VES_CHA_MO",
    "CAL_DUT_MO", "DUT_VAL_MO", "GEN_QY1_MO_FLAG",
]
GOLD_EXPORT = UNIVERSE_EXPORT + [
    "AIR_VAL_MO", "AIR_WGT_MO", "VES_VAL_MO", "VES_WGT_MO", "QTY_1_MO_FLAG",
]


def call(flow, params):
    """One API call. Returns (status, rows, bytes, error_text)."""
    p = dict(params)
    p["key"] = KEY
    try:
        r = requests.get(API.format(flow=flow), params=p, timeout=TIMEOUT)
    except Exception as exc:                       # noqa: BLE001 - probe only
        return None, None, 0, "{}: {}".format(type(exc).__name__, exc)
    time.sleep(PAUSE)
    size = len(r.content)
    if r.status_code != 200:
        return r.status_code, None, size, r.text[:300]
    ctype = r.headers.get("content-type", "")
    if "json" not in ctype:
        # The API answers unkeyed requests with an HTML "Missing Key" page and
        # a 200, so content-type is the only reliable tell.
        return r.status_code, None, size, "non-JSON response: " + r.text[:200]
    try:
        data = r.json()
    except ValueError as exc:
        return r.status_code, None, size, "unparseable JSON: {}".format(exc)
    return r.status_code, data, size, None


def base_params(flow, month, fields, comm_lvl="HS6"):
    """`time` is the required date predicate on these endpoints -- YEAR and
    MONTH exist only as output columns. SUMMARY_LVL=DET drops the country
    grouping rows, which is what stops region aggregates being double-counted
    alongside individual countries."""
    return {
        "get": ",".join(fields),
        "time": month,
        "COMM_LVL": comm_lvl,
        "SUMMARY_LVL": "DET",
    }


# ---------------------------------------------------------------- strategies
def strategy_params(flow, month, fields, mode, chapter=None, codes=None):
    p = base_params(flow, month, fields)
    var = "I_COMMODITY" if flow == "imports" else "E_COMMODITY"
    if mode == "month_only":
        return p
    if mode == "prefix_wildcard":
        p[var] = chapter + "*"
    elif mode == "prefix_bare":
        p[var] = chapter
    elif mode == "explicit_list":
        p[var] = ",".join(codes)
    return p


def probe_chunking(flow, month, chapter, codes):
    fields = UNIVERSE_IMPORT if flow == "imports" else UNIVERSE_EXPORT
    results = {}
    for mode in ("month_only", "prefix_wildcard", "prefix_bare", "explicit_list"):
        if mode == "explicit_list" and not codes:
            continue
        params = strategy_params(flow, month, fields, mode, chapter, codes)
        status, data, size, err = call(flow, params)
        rec = {"status": status, "bytes": size, "error": err}
        if data:
            header, rows = data[0], data[1:]
            rec["n_rows"] = len(rows)
            rec["header"] = header
            var = "I_COMMODITY" if flow == "imports" else "E_COMMODITY"
            if var in header:
                idx = header.index(var)
                got = {r[idx] for r in rows[:5000]}
                rec["distinct_codes_sample"] = len(got)
                rec["all_six_digit"] = all(len(c) == 6 for c in got)
                rec["in_chapter"] = (all(c.startswith(chapter) for c in got)
                                     if mode != "month_only" else None)
                rec["example_codes"] = sorted(got)[:6]
        results[mode] = rec
    return results


def hs6_codes_for_chapter(chapter):
    """Derive the valid HS6 universe offline from the Census concordance files
    rather than discovering it by trial and error against the API. Falls back
    to an empty list if the files are not present, in which case the
    explicit_list strategy is simply skipped."""
    import pandas as pd
    out = set()
    for name in ("impconcord26.xlsx", "expconcord26.xlsx"):
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            continue
        d = pd.read_excel(path, dtype={"commodity": str})
        c = d["commodity"].astype(str).str.strip().str.zfill(10)
        out |= set(c[c.str.startswith(chapter)].str[:6])
    return sorted(out)


def main():
    if not KEY:
        raise SystemExit(
            "No CENSUS_API_KEY in the environment. api.census.gov rejects unkeyed "
            "requests with an HTML page and a 200 status, which is worse than a "
            "clean failure. Register at api.census.gov/data/key_signup.html.")

    report = {
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "field_sets": {"universe_import": UNIVERSE_IMPORT,
                       "universe_export": UNIVERSE_EXPORT,
                       "gold_import": GOLD_IMPORT, "gold_export": GOLD_EXPORT},
        "chunking": {}, "sizing": {}, "value_concepts": {},
    }

    # ---- 1. which chunking strategy works
    for flow, chapter in itertools.product(("imports", "exports"), PROBE_CHAPTERS[:1]):
        codes = hs6_codes_for_chapter(chapter)
        key = "{}/ch{}".format(flow, chapter)
        report["chunking"][key] = probe_chunking(flow, PROBE_MONTHS[0], chapter, codes)
        print("chunking probed:", key)

    # ---- 2. how big a chunk is, across a busy and a quiet chapter
    for flow, month, chapter in itertools.product(("imports", "exports"),
                                                  PROBE_MONTHS, PROBE_CHAPTERS):
        fields = UNIVERSE_IMPORT if flow == "imports" else UNIVERSE_EXPORT
        codes = hs6_codes_for_chapter(chapter)
        params = strategy_params(flow, month, fields, "explicit_list",
                                 chapter, codes) if codes else \
            strategy_params(flow, month, fields, "prefix_wildcard", chapter)
        status, data, size, err = call(flow, params)
        report["sizing"]["{}/{}/ch{}".format(flow, month, chapter)] = {
            "status": status, "bytes": size,
            "n_rows": (len(data) - 1) if data else None, "error": err}
        print("sized:", flow, month, chapter, size, "bytes")

    # ---- 3. general vs consumption imports, and the gold-only rich fields
    status, data, size, err = call(
        "imports", strategy_params("imports", PROBE_MONTHS[0], GOLD_IMPORT,
                                   "explicit_list", "71", hs6_codes_for_chapter("71"))
        if hs6_codes_for_chapter("71") else
        strategy_params("imports", PROBE_MONTHS[0], GOLD_IMPORT,
                        "prefix_wildcard", "71"))
    vc = {"status": status, "error": err}
    if data:
        header, rows = data[0], data[1:]
        vc["header"] = header
        vc["n_rows"] = len(rows)

        def col(name):
            if name not in header:
                return None
            i = header.index(name)
            tot = 0.0
            for r in rows:
                try:
                    tot += float(r[i])
                except (TypeError, ValueError):
                    pass
            return tot

        vc["chapter71_totals"] = {n: col(n) for n in
                                  ("GEN_VAL_MO", "CON_VAL_MO", "GEN_CIF_MO",
                                   "GEN_CHA_MO", "AIR_CHA_MO", "AIR_WGT_MO",
                                   "CAL_DUT_MO", "DUT_VAL_MO")}
        g, c = vc["chapter71_totals"]["GEN_VAL_MO"], vc["chapter71_totals"]["CON_VAL_MO"]
        vc["general_vs_consumption_gap_pct"] = (100 * (g - c) / g) if g else None
        w, ch = vc["chapter71_totals"]["AIR_WGT_MO"], vc["chapter71_totals"]["AIR_CHA_MO"]
        vc["implied_air_charge_per_kg_usd"] = (ch / w) if (w and ch) else None
    report["value_concepts"] = vc

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "probe_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 78)
    print("CHUNKING -- which strategies returned usable HS6 rows")
    for key, modes in report["chunking"].items():
        print(" ", key)
        for mode, rec in modes.items():
            ok = rec.get("n_rows") is not None
            print("    {:<17} {:<4} rows={:<8} 6-digit={} {}".format(
                mode, str(rec["status"]), str(rec.get("n_rows")),
                rec.get("all_six_digit"),
                "" if ok else "ERR " + str(rec.get("error"))[:60]))

    print("\nSIZING -- extrapolate the bulk run from these")
    rows = [(k, v) for k, v in report["sizing"].items() if v.get("n_rows")]
    if rows:
        avg = sum(v["n_rows"] for _, v in rows) / len(rows)
        avgb = sum(v["bytes"] for _, v in rows) / len(rows)
        print("  mean rows/chunk {:.0f}, mean bytes/chunk {:.0f}".format(avg, avgb))
        print("  53 months x 99 chapters x 2 flows = {:,} chunks".format(53 * 99 * 2))
        print("  implies ~{:,.0f} rows and ~{:.1f} GB of JSON in flight".format(
            avg * 53 * 99 * 2, avgb * 53 * 99 * 2 / 1e9))

    print("\nVALUE CONCEPTS -- chapter 71, {}".format(PROBE_MONTHS[0]))
    if vc.get("chapter71_totals"):
        for k, v in vc["chapter71_totals"].items():
            print("  {:<14} {:>18,.0f}".format(k, v if v is not None else float("nan")))
        print("  general exceeds consumption by {:.2f}% "
              "(if this is material for gold, it is a finding, not a nuisance)"
              .format(vc["general_vs_consumption_gap_pct"] or 0.0))
        if vc.get("implied_air_charge_per_kg_usd"):
            print("  implied air charge {:.2f} USD/kg -- this is the freight number "
                  "the cost ledger currently assumes"
                  .format(vc["implied_air_charge_per_kg_usd"]))

    print("\nwrote", os.path.join(OUT, "probe_report.json"))


if __name__ == "__main__":
    main()
