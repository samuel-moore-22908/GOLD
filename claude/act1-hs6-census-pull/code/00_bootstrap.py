"""
Act I, step 0. Rebuild every reference list from scratch on a machine that has
nothing but Python and a network route to census.gov.

STANDARD LIBRARY ONLY. No pandas, no requests, no openpyxl, no repository. If
you can run `python 00_bootstrap.py` you can reproduce all four reference files,
and nothing needs transcribing by hand -- which matters, because the commodity
universe is 5,630 codes.

Four public URLs, none of which needs an API key:

  1. variables.json on each endpoint   -> the valid field names
  2. imp-code.txt / exp-code.txt       -> the HS6 commodity universe
  3. country.txt                       -> Schedule C individual countries

The commodity files are the fixed-width plain-text editions of HTSUS (imports)
and Schedule B (exports). They are used in preference to the Census concordance
spreadsheets purely because they need no Excel reader; the two agree exactly at
HS6 -- both give 5,630 codes across 98 chapters. Chapter 77 is unused in the
Harmonized System, which is why it is 98 and not 99.

That the two files disagree at TEN digits is not a defect to fix. Imports carry
20,393 lines and exports 9,779, because HTSUS subdivides wherever a duty rate
differs and the United States constitutionally cannot tax exports. This is why
bilateral Grubel-Lloyd has to be computed at HS6: it is the finest level at
which the two systems describe the same thing.

Outputs, into ../output/:
    ref_variables.json     valid field names per endpoint, plus the chosen sets
    ref_hs6.csv            chapter,hs6
    ref_countries.csv      cty_code,cty_name,iso2
    worklist_gold.csv      106 requests
    worklist_universe.csv  ~11,342 requests

Usage:
    python 00_bootstrap.py
"""
import csv
import json
import os
import re
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
UA = {"User-Agent": "gold-flow-deconvolution research"}

VARS = "https://api.census.gov/data/timeseries/intltrade/{}/hs/variables.json"
CODES = "https://www.census.gov/foreign-trade/schedules/b/2026/{}-code.txt"
COUNTRIES = "https://www.census.gov/foreign-trade/schedules/c/country.txt"

START, END = "2022-01", "2026-05"
MAX_CODES = 150          # keeps the longest query predicate near 1 KB
GOLD_CHAPTER = "71"

# The field sets. Imports and exports differ in three ways that are easy to get
# wrong by hand: the commodity variable (I_ vs E_), the quantity variable
# (GEN_QY1_MO vs QTY_1_MO), and the fact that only imports carry charges and
# duty. Every name here is checked against the live catalogue below, so a typo
# stops the script instead of failing on request four thousand.
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


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", "replace")


def months(start, end):
    out = []
    y, m = int(start[:4]), int(start[5:7])
    while "{:04d}-{:02d}".format(y, m) <= end:
        out.append("{:04d}-{:02d}".format(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- 1. variables, validated against the live catalogues
    catalogue = {f: set(json.loads(get(VARS.format(f)))["variables"])
                 for f in ("imports", "exports")}
    bad = []
    for (flow, tier), fields in FIELDS.items():
        bad += ["{}/{}: {}".format(flow, tier, n)
                for n in fields if n not in catalogue[flow]]
    if bad:
        raise SystemExit("Unknown field names:\n  " + "\n  ".join(bad))
    with open(os.path.join(OUT, "ref_variables.json"), "w", encoding="utf-8") as f:
        json.dump({"valid_names": {k: sorted(v) for k, v in catalogue.items()},
                   "field_sets": {"{}/{}".format(a, b): v
                                  for (a, b), v in FIELDS.items()}}, f, indent=2)
    print("variables  {} valid on imports, {} on exports; all {} chosen fields resolve"
          .format(len(catalogue["imports"]), len(catalogue["exports"]),
                  sum(len(v) for v in FIELDS.values())))

    # ---- 2. the HS6 commodity universe
    hs6 = set()
    for side in ("imp", "exp"):
        text = get(CODES.format(side))
        found = {m.group(1)[:6] for m in re.finditer(r"^(\d{10})\s", text, re.M)}
        print("  {}-code.txt  {:>6} HS6".format(side, len(found)))
        hs6 |= found
    by_chapter = {}
    for c in sorted(hs6):
        by_chapter.setdefault(c[:2], []).append(c)
    write_csv("ref_hs6.csv", ["chapter", "hs6"],
              [(ch, c) for ch, cs in sorted(by_chapter.items()) for c in cs])
    print("commodities  {:,} HS6 across {} chapters (77 is unused in the HS)"
          .format(len(hs6), len(by_chapter)))

    # ---- 3. countries. NOT an iteration dimension -- SUMMARY_LVL=DET returns
    # every partner in one response. This list exists to validate what comes
    # back and to join names on afterwards.
    rows = re.findall(r"^\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*([A-Z-]{0,2})\s*$",
                      get(COUNTRIES), re.M)
    if len(rows) < 200:
        raise SystemExit("Parsed only {} countries -- layout changed.".format(len(rows)))
    write_csv("ref_countries.csv", ["cty_code", "cty_name", "iso2"], rows)
    print("countries    {} individual codes (validation and joins only)".format(len(rows)))

    # ---- 4. the worklist. Chunk key is (flow, month, chapter, batch).
    mons = months(START, END)
    for tier in ("gold", "universe"):
        chapters = [GOLD_CHAPTER] if tier == "gold" else sorted(by_chapter)
        out = []
        for flow in ("imports", "exports"):
            for mo in mons:
                for ch in chapters:
                    codes = by_chapter[ch]
                    batches = [codes[i:i + MAX_CODES]
                               for i in range(0, len(codes), MAX_CODES)]
                    for b, batch in enumerate(batches):
                        suffix = "" if len(batches) == 1 else "|b{}".format(b)
                        out.append(("{}|{}|{}|{}{}".format(tier, flow, mo, ch, suffix),
                                    tier, flow, mo, ch, b, len(batch), ",".join(batch)))
        write_csv("worklist_{}.csv".format(tier),
                  ["chunk_id", "tier", "flow", "month", "chapter", "batch",
                   "n_codes", "codes"], out)
        longest = max(len(r[-1]) for r in out)
        print("worklist_{:<9} {:>7,} requests, longest predicate {:,} chars"
              .format(tier + ".csv", len(out), longest))

    print("\nwrote into", os.path.normpath(OUT))
    print("expected: 5,630 HS6 / 98 chapters / 241 countries. "
          "If yours differ, a source layout changed -- stop and look.")


if __name__ == "__main__":
    main()
