"""
Act I, step 1b. Build the iteration plan the bulk pull consumes.

Three lists are needed, and one of them is a trap.

  VARIABLES are fixed per (endpoint, tier). They are validated here against the
  endpoints' own variables.json, so a mistyped field name fails at build time
  instead of on request four thousand. Hand-typed field names are the single
  most common cause of a 400 on this API, and the two endpoints differ in ways
  that are easy to miss: imports call the quantity field GEN_QY1_MO, exports
  call it QTY_1_MO, and only imports carry charges and duty.

  COMMODITIES are the chunk key. The valid HS6 universe is derived offline from
  the Census concordance files, so codes are never discovered by trial and error
  against the API.

  COUNTRIES ARE NOT AN ITERATION DIMENSION. This is the trap. SUMMARY_LVL=DET
  returns every partner in one response, so looping over countries would
  multiply the call count by roughly 230 and return exactly the same data. The
  country list is built anyway, but only for two jobs afterwards: validating
  that nothing but individual countries came back, and joining names on without
  carrying CTY_NAME through sixteen million rows.

The chunk key is therefore (flow, month, chapter) and nothing else.

Outputs, all into output/:
    ref_variables.json      validated field sets per flow and tier
    ref_hs6.csv             HS6 universe with its chapter
    ref_countries.csv       Schedule C individual-country list
    worklist_{tier}.csv     the exact iteration plan, one row per request

Usage:
    python 01b_build_worklist.py
    python 01b_build_worklist.py --probe-chunk-mode     (needs CENSUS_API_KEY)
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path("claude/act1-hs6-census-pull/output")
API = "https://api.census.gov/data/timeseries/intltrade/{flow}/hs"
VARS_URL = API + "/variables.json"
SCHEDULE_C = "https://www.census.gov/foreign-trade/schedules/c/country.txt"
UA = {"User-Agent": "gold-flow-deconvolution research"}

START, END = "2022-01", "2026-05"

FIELDS = {
    ("imports", "universe"): ["I_COMMODITY", "CTY_CODE", "GEN_VAL_MO", "CON_VAL_MO",
                              "GEN_QY1_MO", "UNIT_QY1"],
    ("exports", "universe"): ["E_COMMODITY", "CTY_CODE", "ALL_VAL_MO", "QTY_1_MO",
                              "UNIT_QY1", "DF"],
    ("imports", "gold"): ["I_COMMODITY", "CTY_CODE", "GEN_VAL_MO", "CON_VAL_MO",
                          "GEN_QY1_MO", "UNIT_QY1", "GEN_CIF_MO", "GEN_CHA_MO",
                          "CON_CIF_MO", "CON_CHA_MO", "AIR_VAL_MO", "AIR_WGT_MO",
                          "AIR_CHA_MO", "VES_VAL_MO", "VES_WGT_MO", "VES_CHA_MO",
                          "CAL_DUT_MO", "DUT_VAL_MO", "GEN_QY1_MO_FLAG"],
    ("exports", "gold"): ["E_COMMODITY", "CTY_CODE", "ALL_VAL_MO", "QTY_1_MO",
                          "UNIT_QY1", "DF", "AIR_VAL_MO", "AIR_WGT_MO",
                          "VES_VAL_MO", "VES_WGT_MO", "QTY_1_MO_FLAG"],
}

GOLD_CHAPTER = "71"
CODE_VAR = {"imports": "I_COMMODITY", "exports": "E_COMMODITY"}


# --------------------------------------------------------------- 1. variables
def variable_catalogue(flow):
    """The endpoint's own list of valid field names. Public, no key needed."""
    r = requests.get(VARS_URL.format(flow=flow), headers=UA, timeout=60)
    r.raise_for_status()
    return set(r.json()["variables"])


def validate_fields():
    catalogues = {f: variable_catalogue(f) for f in ("imports", "exports")}
    validated, problems = {}, []
    for (flow, tier), fields in FIELDS.items():
        unknown = [f for f in fields if f not in catalogues[flow]]
        if unknown:
            problems.append("{}/{}: {}".format(flow, tier, ", ".join(unknown)))
        # Guard against a duplicate slipping into a hand-edited list; the API
        # tolerates it but the returned column would be ambiguous.
        dupes = {f for f in fields if fields.count(f) > 1}
        if dupes:
            problems.append("{}/{}: duplicated {}".format(flow, tier, dupes))
        validated["{}/{}".format(flow, tier)] = fields
    if problems:
        raise SystemExit("Field validation failed:\n  " + "\n  ".join(problems))
    return validated, catalogues


# ------------------------------------------------------------- 2. commodities
def hs6_by_chapter():
    """HS6 universe from the Census concordance files. Both sides are unioned:
    a subheading traded in only one direction still needs a chunk, or the
    corridor silently gets a one-sided zero instead of a genuine absence."""
    codes = {}
    missing = []
    for name in ("impconcord26.xlsx", "expconcord26.xlsx"):
        path = OUT / name
        if not path.exists():
            missing.append(name)
            continue
        d = pd.read_excel(path, dtype={"commodity": str})
        hs6 = (d["commodity"].astype(str).str.strip().str.zfill(10).str[:6]).unique()
        for c in hs6:
            if c.isdigit():
                codes.setdefault(c[:2], set()).add(c)
    if missing:
        raise SystemExit(
            "Missing {} in {}.\nDownload both from\n  https://www.census.gov/"
            "foreign-trade/reference/codes/concordance/".format(", ".join(missing), OUT))
    return {ch: sorted(v) for ch, v in sorted(codes.items())}


# ---------------------------------------------------------------- 3. countries
def schedule_c_countries():
    """Individual-country codes. Used to VALIDATE the pull, not to iterate it.

    Any CTY_CODE returned that is not in this list is either a country grouping
    that leaked past SUMMARY_LVL=DET -- which would double-count everything --
    or a code created since the file was published. Treat a non-match as
    'investigate', never as 'drop'."""
    r = requests.get(SCHEDULE_C, headers=UA, timeout=60)
    r.raise_for_status()
    rows = []
    for line in r.text.splitlines():
        m = re.match(r"^\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*([A-Z-]{0,2})\s*$", line)
        if m:
            rows.append({"cty_code": m.group(1), "cty_name": m.group(2),
                         "iso2": m.group(3) or None})
    d = pd.DataFrame(rows).drop_duplicates("cty_code")
    if len(d) < 200:
        raise SystemExit("Parsed only {} countries from Schedule C -- the file "
                         "layout has probably changed.".format(len(d)))
    return d


# ----------------------------------------------------------------- 4. worklist
# Chapters are uneven: 84 carries 538 HS6 codes and 29 carries 411, which put
# roughly 3.8 KB of comma-separated codes into the query string. That is under
# the usual 8 KB server limit but not comfortably, and a truncated URL fails in
# a way that looks like missing data rather than an error. Long chapters are
# split into batches so no request is anywhere near the ceiling.
MAX_CODES_PER_REQUEST = 150


def build_worklist(tier, hs6, max_codes=MAX_CODES_PER_REQUEST):
    months = [str(p) for p in pd.period_range(START, END, freq="M")]
    chapters = [GOLD_CHAPTER] if tier == "gold" else sorted(hs6)
    rows = []
    for flow in ("imports", "exports"):
        for month in months:
            for ch in chapters:
                if ch not in hs6:
                    continue
                codes = hs6[ch]
                batches = [codes[i:i + max_codes]
                           for i in range(0, len(codes), max_codes)] or [[]]
                for b, batch in enumerate(batches):
                    suffix = "" if len(batches) == 1 else "|b{}".format(b)
                    rows.append({
                        "chunk_id": "{}|{}|{}|{}{}".format(tier, flow, month, ch, suffix),
                        "tier": tier, "flow": flow, "month": month, "chapter": ch,
                        "batch": b, "n_codes": len(batch),
                        "codes": ",".join(batch),
                    })
    return pd.DataFrame(rows)


# ------------------------------------------------- 5. how to slice the request
def probe_chunk_mode(key, month="2025-01", chapter="71", hs6=None):
    """Determine what the commodity predicate actually accepts. A single code
    is already known to work; the question is whether a whole chapter can go in
    one request, and in what form."""
    codes = hs6[chapter]
    trials = {
        "explicit_list": ",".join(codes),
        "prefix_wildcard": chapter + "*",
        "prefix_bare": chapter,
        "month_only": None,
    }
    results = {}
    for mode, pred in trials.items():
        params = {"get": ",".join(FIELDS[("imports", "universe")]), "time": month,
                  "COMM_LVL": "HS6", "SUMMARY_LVL": "DET", "key": key}
        if pred is not None:
            params[CODE_VAR["imports"]] = pred
        try:
            r = requests.get(API.format(flow="imports"), params=params, timeout=180)
        except Exception as exc:                      # noqa: BLE001
            results[mode] = {"ok": False, "note": type(exc).__name__}
            continue
        time.sleep(1.5)
        ct = r.headers.get("content-type", "")
        if r.status_code == 404:
            results[mode] = {"ok": False, "note": "404 (no records match)"}
        elif r.status_code == 200 and "json" in ct:
            data = r.json()
            got = {row[data[0].index("I_COMMODITY")] for row in data[1:]}
            results[mode] = {
                "ok": True, "rows": len(data) - 1, "bytes": len(r.content),
                "distinct_codes": len(got),
                "all_six_digit": all(len(c) == 6 for c in got),
                "in_chapter": all(c.startswith(chapter) for c in got),
            }
        elif r.status_code == 200:
            results[mode] = {"ok": False, "note": "non-JSON 200 -- key problem"}
        else:
            results[mode] = {"ok": False,
                             "note": "http {} {}".format(r.status_code, r.text[:120])}
    return results


def main(do_probe):
    OUT.mkdir(parents=True, exist_ok=True)

    validated, catalogues = validate_fields()
    (OUT / "ref_variables.json").write_text(json.dumps(
        {"field_sets": validated,
         "n_valid_names": {f: len(v) for f, v in catalogues.items()},
         "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2))
    print("variables validated against the live catalogues:")
    for k, v in validated.items():
        print("  {:<20} {} fields".format(k, len(v)))

    hs6 = hs6_by_chapter()
    flat = pd.DataFrame([{"chapter": ch, "hs6": c} for ch, cs in hs6.items() for c in cs])
    flat.to_csv(OUT / "ref_hs6.csv", index=False)
    print("\nHS6 universe: {:,} codes across {} chapters".format(len(flat), len(hs6)))
    print("  chapter 71 ({} codes): {}".format(len(hs6["71"]), ", ".join(hs6["71"])))

    cty = schedule_c_countries()
    cty.to_csv(OUT / "ref_countries.csv", index=False)
    print("\ncountries: {} individual codes (for validation and joins, NOT iteration)"
          .format(len(cty)))

    for tier in ("gold", "universe"):
        wl = build_worklist(tier, hs6)
        wl.to_csv(OUT / "worklist_{}.csv".format(tier), index=False)
        print("worklist_{:<9} {:>7,} requests   median {:>4.0f} codes/request"
              .format(tier + ".csv", len(wl), wl.n_codes.median()))

    if do_probe:
        key = os.environ.get("CENSUS_API_KEY", "").strip()
        if not key:
            raise SystemExit("--probe-chunk-mode needs CENSUS_API_KEY.")
        print("\nprobing how the commodity predicate can be sliced ...")
        res = probe_chunk_mode(key, hs6=hs6)
        (OUT / "ref_chunk_mode.json").write_text(json.dumps(res, indent=2))
        for mode, r in res.items():
            print("  {:<17} {}".format(mode, json.dumps(r)))
        winners = [m for m, r in res.items()
                   if r.get("ok") and r.get("all_six_digit")
                   and (m == "month_only" or r.get("in_chapter"))]
        print("\n  usable: {}".format(", ".join(winners) or "NONE"))
        print("  set CHUNK_MODE in 02_pull_hs6_panel.py to the first of these that "
              "returned a sane row count.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-chunk-mode", action="store_true")
    main(ap.parse_args().probe_chunk_mode)
