#!/usr/bin/env python3
"""
US gold trade by partner at HS10, with the reported quantities, Jan 2015 on.

The point is QUANTITY: tonnes of gold as Census reports them, not tonnes
backed out of dollars. One data file, plus two checks against the HS4 pull:

  us_gold_hs10_partner_monthly.csv   every HS10 line under 7108 and 7115, every
                                     partner (and Census's partner groupings),
                                     monthly, imports and exports, with value
                                     AND the reported quantity fields.
  us_gold_hs10_reconcile.csv         one row per (date, partner, flow, HS4)
                                     cell where the HS10 lines do not sum to
                                     the value in the HS4 files written by
                                     pull_us_customs.py. Empty means they agree.
                                     Value is the only field both pulls share,
                                     so this is what proves the HS10 pull is
                                     complete.
  us_gold_hs10_qty_compare.csv       per (date, partner, flow): reported gold
                                     tonnes from HS10 against the tonnage the
                                     figures currently DERIVE - HS4 7108+7115
                                     value / monthly-mean LBMA PM / 32,150.7 -
                                     with the gap split into its sources.

WHY HS10. Census leaves the quantity fields blank at HS4: a heading mixes lines
reported in different units, so there is nothing to add up. At HS10 every line
carries a unit, and for gold the unit is mass. That turns tonnage from a
derived number (value / LBMA price) into a reported one. The HS4 pull says the
opposite in its docstring; that statement was wrong and this script is the
correction.

WHAT COUNTS AS GOLD. Every 7108 line is gold. Heading 7115 is not: it also
holds silver bars (7115900560), platinum-group and other bars (7115900590),
platinum catalyst gauze (7115100000) and silver/platinum articles. Dividing
all of 7115 by the gold price, as the HS4 route has to, books that silver as
gold. Here each line is classified from its Census description, the class is
written to the file, and the full line list is printed so a new or renamed
line cannot slip through unnoticed.

One line is neither: EXPORT 7115900000, "other precious-metal articles,
NESOI", which until Schedule B split gold out as 7115900010 in January 2026
held gold, silver and platinum articles together. Its unit value runs at a
quarter to two-thirds of the gold price in most years and 0.82 in 2025, when
about $21bn of tariff-episode bars left under it. It is classed "mixed": its
gross mass is kept and reported separately, never added to gold_t. Booking it
as non-gold would lose ~200 t of 2025 exports; booking it as gold would count
silver as gold. US gold EXPORT tonnage before 2026 is therefore a lower bound
(gold lines) with the mixed line as the ceiling on what it is missing.

UNITS. The quantity unit is per line and the mass is not always the same mass:
  CGM  grams of gold CONTENT - bullion, dore, other unwrought. Fine gold.
  GM   gross grams - powder, semimanufactures, 7115 bars. For the 7115 bars
       the line is restricted to >= 99.5% purity, so gross ~ fine. For
       "articles of gold incl. metal clad with gold" it is not.
  CM2  square centimetres - gold leaf. Its second quantity claims to be CGM
       but is not usable: May 2015 reports 668 kg of "content" for $430k,
       about $20/oz, so it is weighing the booklets. Gold leaf gets no
       mass; its value (~$0.1bn over the window) shows up as gold_noqty.
gold_t is tonnes of whichever mass the line reports, and gold_basis says
which. Provenance is "reported" for every non-missing gold_t: nothing here is
divided by a price.

UNIT-VALUE CHECK. implied_usd_oz = value / (grams / 31.1034768), and
uv_ratio = implied_usd_oz / the month's average LBMA PM, when lbma_pm.csv is on
disk. Fine-gold lines sit near 1; a cell far from 1 has a quantity problem
(keying error, mixed metal, dore content misreported) and should be looked at
before it is used.

PARTNER ROWS. Census returns country groupings (EU, OPEC, "1XXX" North
America, ...) and a "-" all-countries total alongside the countries. They are
kept, as in the HS4 file, and is_country marks the real partners. Never sum
over all rows.

Idempotent: an existing output is left alone unless --force is passed, and the
reconciliation reruns either way. Requests are spaced deliberately.

Needs CENSUS_API_KEY, in the repo .env or the environment.

Run from anywhere:
    python gold_final/code/pull_us_customs_hs10.py
    python gold_final/code/pull_us_customs_hs10.py --force
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS BLOCK IF YOU MOVE THE PROJECT
# ============================================================================
REPO_ROOT = ""                      # blank = infer from this file's location
ENV_FILE = ".env"                   # relative to the root, or an absolute path
OUT_DIR = "gold_final/data/raw"     # relative to the root, or an absolute path
# ============================================================================

HS_GOLD = ("7108", "7115")
FROM, TO = "2015-01", None          # None = as recent as Census has

CHUNK_MONTHS = 12
REQUEST_SPACING_S = 2.0             # deliberate, not maximal
TIMEOUT_S = 180
RETRIES = 3

# Reconciliation tolerance, dollars. Census values are integers, so the sum of
# HS10 lines should match the HS4 cell exactly; anything above this is real.
TOL_USD = 1

OUT_NAME = "us_gold_hs10_partner_monthly.csv"
RECON_NAME = "us_gold_hs10_reconcile.csv"
QTY_NAME = "us_gold_hs10_qty_compare.csv"
HS4_PARTNER = "us_gold_partner_monthly.csv"     # from pull_us_customs.py
HS4_TOTAL = "us_gold_monthly.csv"               # from pull_us_customs.py
LBMA = "lbma_pm.csv"                            # daily, date,lbma_pm_usd

G_PER_OZ = 31.1034768
OZ_PER_T = 32150.7                  # project convention

# Lines whose metal Census does not identify. Matched by code, because the
# description is word-for-word the one the post-2026 non-gold remainder
# (7115900090) carries.
MIXED_LINES = {("exports", "7115900000")}

import argparse
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]


def _at(value: str) -> Path:
    """Absolute paths win, ~ expands, anything else is relative to the root.
    Matches pull_us_customs.py."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p


OUT = _at(OUT_DIR)
BASE = "https://api.census.gov/data/timeseries/intltrade"
UA = {"User-Agent": "academic research (gold trade deconvolution)"}

# Imports are general imports at customs value; exports are FAS value including
# re-exports. Same value fields as the HS4 pull, so the two reconcile.
FLOWS = {
    "imports": {"code": "I_COMMODITY", "desc": "I_COMMODITY_SDESC",
                "value": "GEN_VAL_MO", "q1": "GEN_QY1_MO", "q2": "GEN_QY2_MO"},
    "exports": {"code": "E_COMMODITY", "desc": "E_COMMODITY_SDESC",
                "value": "ALL_VAL_MO", "q1": "QTY_1_MO", "q2": "QTY_2_MO"},
}

# Grams per reported unit, for the mass units Census uses on these lines.
MASS_G = {"GM": 1.0, "CGM": 1.0, "KG": 1000.0, "CKG": 1000.0}
CONTENT_UNITS = {"CGM", "CKG"}


def api_key() -> str:
    env = _at(ENV_FILE)
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CENSUS_API_KEY=") and len(line) > 15:
                return line.split("=", 1)[1].strip()
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if key:
        return key
    raise SystemExit(
        f"no CENSUS_API_KEY found.\n"
        f"  add a line   CENSUS_API_KEY=<your key>   to {env}\n"
        f"  or export it in the environment\n"
        f"  free signup: https://api.census.gov/data/key_signup.html")


def months(a: str, b: str) -> list[str]:
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    out = []
    while (ya, ma) <= (yb, mb):
        out.append(f"{ya}-{ma:02d}")
        ma += 1
        if ma == 13:
            ya, ma = ya + 1, 1
    return out


def chunks(lo: str, hi: str, n: int) -> list[tuple[str, str]]:
    ms = months(lo, hi)
    return [(ms[i], ms[min(i + n, len(ms)) - 1]) for i in range(0, len(ms), n)]


def get(flow: str, fields: list[str], lo: str, hi: str, key: str,
        commodity: str, level: str = "HS10") -> list[list[str]]:
    """One Census call over a month range. Returns rows including the header.
    A range with no data comes back as HTTP 204 and an empty body; that is
    returned as a header-only result rather than treated as an error."""
    params = {
        "get": ",".join(fields),
        "COMM_LVL": level,
        FLOWS[flow]["code"]: commodity,
        "time": f"from {lo} to {hi}",
        "key": key,
    }
    url = f"{BASE}/{flow}/hs?" + urllib.parse.urlencode(params)
    for attempt in range(1, RETRIES + 1):
        time.sleep(REQUEST_SPACING_S)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read()
            if not body.strip():
                return [fields + ["time"]]
            if not body.lstrip().startswith(b"["):
                raise RuntimeError("not JSON - the key was probably rejected")
            return json.loads(body)
        except Exception as e:
            if attempt == RETRIES:
                raise RuntimeError(f"{flow} {commodity} {lo}..{hi}: {e}") from e
            wait = 5 * attempt
            print(f"      retry {attempt}/{RETRIES - 1} in {wait}s ({e})",
                  flush=True)
            time.sleep(wait)
    return []


def latest_month(key: str) -> str:
    rows = get("imports", ["I_COMMODITY", "GEN_VAL_MO"], "2025-01", "2027-12",
               key, commodity="7108", level="HS4")
    t = rows[0].index("time")
    return max(r[t] for r in rows[1:])


def num(s: str | None) -> float:
    try:
        return float(s) if s not in (None, "", "-") else 0.0
    except ValueError:
        return 0.0


# ------------------------------------------------------------ classification
# From the Census short description, which abbreviates freely ("GLD", "ARTCLS",
# "PRE MET"). Everything under 7108 is gold by definition of the heading.
_SILVER_PLAT = re.compile(r"\b(SILVER|SLVR|PLAT\w*|PALLAD\w*|RHOD\w*|"
                          r"CATLYST\w*|CATALYST\w*)\b")
_GOLD = re.compile(r"\b(GOLD|GLD)\b")


def gold_class(flow: str, hs10: str, desc: str) -> str:
    """'gold', 'mixed' (metal not identified) or 'other'."""
    if (flow, hs10) in MIXED_LINES:
        return "mixed"
    return "gold" if is_gold_line(hs10, desc) else "other"


def is_gold_line(hs10: str, desc: str) -> bool:
    if hs10.startswith("7108"):
        return True
    d = desc.upper()
    # "ARTCLS NESOI OF GLD INCL MTL CLD W GOLD" is gold; "...OF SILVER" and
    # "...OTHER" bar lines are not. A description naming silver or platinum
    # metals wins over a stray mention of gold.
    if _SILVER_PLAT.search(d):
        return False
    return bool(_GOLD.search(d))


def gold_mass(hs10: str, desc: str, q1: float, u1: str, q2: float, u2: str
              ) -> tuple[float | None, str]:
    """Grams of gold the line reports, and the basis: content or gross.
    First quantity only - the one line where it is not a mass is gold leaf,
    whose second quantity is not credible (see the docstring)."""
    if not is_gold_line(hs10, desc) or u1 not in MASS_G:
        return None, ""
    return q1 * MASS_G[u1], ("content" if u1 in CONTENT_UNITS else "gross")


def lbma_monthly() -> dict[str, float]:
    """Month-start date -> average LBMA PM over the month, if the daily file
    is on disk. Missing file means no unit-value ratio, not an error."""
    path = OUT / LBMA
    if not path.exists():
        return {}
    acc: dict[str, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = num(r.get("lbma_pm_usd"))
            if v > 0:
                acc[r["date"][:7] + "-01"].append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def is_country(code: str) -> bool:
    """Real partner, not a grouping. Countries are four digits from 1000 up;
    groupings are 00xx or carry an X ("1XXX"); the total is "-"."""
    return code.isdigit() and len(code) == 4 and int(code) >= 1000


# ---------------------------------------------------------------------- pull
def pull(key: str, lo: str, hi: str) -> list[dict]:
    px = lbma_monthly()
    out = []
    for flow, s in FLOWS.items():
        fields = ["CTY_CODE", "CTY_NAME", s["code"], s["desc"], s["value"],
                  s["q1"], "UNIT_QY1", s["q2"], "UNIT_QY2"]
        for hs in HS_GOLD:
            for a, b in chunks(lo, hi, CHUNK_MONTHS):
                print(f"   hs10  {flow:7s} {hs}*  {a}..{b}", flush=True)
                rows = get(flow, fields, a, b, key, commodity=f"{hs}*")
                h = rows[0]
                ix = {f: h.index(f) for f in fields + ["time"]}
                for r in rows[1:]:
                    hs10, desc = r[ix[s["code"]]], r[ix[s["desc"]]]
                    val = num(r[ix[s["value"]]])
                    q1, u1 = num(r[ix[s["q1"]]]), r[ix["UNIT_QY1"]]
                    q2, u2 = num(r[ix[s["q2"]]]), r[ix["UNIT_QY2"]]
                    date = f"{r[ix['time']]}-01"
                    cls = gold_class(flow, hs10, desc)
                    grams, basis = (gold_mass(hs10, desc, q1, u1, q2, u2)
                                    if cls == "gold" else (None, ""))
                    implied = val / (grams / G_PER_OZ) if grams else None
                    ref = px.get(date)
                    out.append({
                        "date": date,
                        "cty_code": r[ix["CTY_CODE"]],
                        "cty_name": r[ix["CTY_NAME"]],
                        "is_country": int(is_country(r[ix["CTY_CODE"]])),
                        "flow": flow,
                        "hs4": hs10[:4],
                        "hs10": hs10,
                        "hs10_desc": desc,
                        "value_usd": int(val),
                        "qty1": q1, "unit1": u1,
                        "qty2": q2, "unit2": u2,
                        "gold_class": cls,
                        "gold_basis": basis,
                        "gold_t": "" if grams is None else grams / 1e6,
                        "gold_t_provenance": "" if grams is None else "reported",
                        "implied_usd_oz": "" if implied is None
                                          else round(implied, 2),
                        "uv_ratio": "" if implied is None or not ref
                                    else round(implied / ref, 4),
                    })
    return out


def write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"   wrote {path.relative_to(ROOT)}  ({len(rows):,} rows)", flush=True)


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------- reconciliation
def line_list(rows: list[dict]) -> None:
    """Every HS10 line seen, with its unit, class and the months it appears.
    Printed so a misclassified or newly created line is visible on every run."""
    seen: dict[tuple, dict] = {}
    for r in rows:
        k = (r["flow"], r["hs10"])
        e = seen.setdefault(k, {"desc": r["hs10_desc"], "units": set(),
                                "cls": r["gold_class"], "basis": r["gold_basis"],
                                "lo": r["date"], "hi": r["date"], "usd": 0.0})
        e["units"].add(r["unit1"] + ("/" + r["unit2"] if r["unit2"] not in
                                     ("", "-") else ""))
        e["lo"], e["hi"] = min(e["lo"], r["date"]), max(e["hi"], r["date"])
        if r["cty_code"] == "-":
            e["usd"] += float(r["value_usd"])
    print()
    print("   HS10 lines (value = all-countries total over the window)")
    print(f"   {'flow':7s} {'hs10':10s} class basis    units      "
          f"{'first':7s} {'last':7s} {'$bn':>8s}  description")
    for (flow, hs10), e in sorted(seen.items()):
        print(f"   {flow:7s} {hs10:10s} {e['cls']:5s} "
              f"{e['basis']:8s} {','.join(sorted(e['units'])):10s} "
              f"{e['lo'][:7]} {e['hi'][:7]} {e['usd'] / 1e9:8.2f}  {e['desc']}")


def reconcile(rows: list[dict]) -> list[dict]:
    """Sum HS10 value to (date, partner, flow, HS4) and compare with the HS4
    files over the months both cover. Reports every disagreement, and every
    cell present in one source but not the other with a non-zero value."""
    hs10 = defaultdict(float)
    for r in rows:
        hs10[(r["date"], r["cty_code"], r["flow"], r["hs4"])] += \
            float(r["value_usd"])

    bad = []
    for name, has_partner in ((HS4_PARTNER, True), (HS4_TOTAL, False)):
        path = OUT / name
        if not path.exists():
            print(f"   {name} not on disk - run pull_us_customs.py to "
                  f"reconcile against it")
            continue
        ref = {}
        for r in read(path):
            cty = r["cty_code"] if has_partner else "-"
            ref[(r["date"], cty, r["flow"], r["hs4"])] = float(r["value_usd"])
        # Compare only the months both files cover: a month one pull has and
        # the other does not yet is a timing difference, not a disagreement.
        common = {k[0] for k in ref} & {k[0] for k in hs10}
        ref = {k: v for k, v in ref.items() if k[0] in common}
        mine = {k: v for k, v in hs10.items()
                if k[0] in common and (has_partner or k[1] == "-")}
        both = ref.keys() & mine.keys()
        only_ref = {k for k in ref.keys() - mine.keys() if ref[k] != 0}
        only_mine = {k for k in mine.keys() - ref.keys() if mine[k] != 0}
        diff = {k for k in both if abs(ref[k] - mine[k]) > TOL_USD}
        span = (f"{min(common)[:7]} .. {max(common)[:7]}" if common
                else "no common months")
        tot_ref = sum(ref[k] for k in both)
        tot_mine = sum(mine[k] for k in both)
        print()
        print(f"   vs {name}  ({span})")
        print(f"      cells in both            {len(both):>8,}")
        print(f"      values differ > ${TOL_USD}      {len(diff):>8,}")
        print(f"      non-zero, HS4 file only  {len(only_ref):>8,}")
        print(f"      non-zero, HS10 only      {len(only_mine):>8,}")
        print(f"      total $bn, HS4 / HS10    {tot_ref / 1e9:>10.3f} / "
              f"{tot_mine / 1e9:.3f}")
        for k in sorted(diff | only_ref | only_mine):
            bad.append({"source": name, "date": k[0], "cty_code": k[1],
                        "flow": k[2], "hs4": k[3],
                        "hs4_value_usd": ref.get(k, ""),
                        "hs10_sum_usd": mine.get(k, ""),
                        "diff_usd": mine.get(k, 0) - ref.get(k, 0)})
    return bad


def qty_compare(rows: list[dict]) -> list[dict]:
    """Reported tonnes against the derived tonnes the figures use, per
    (date, partner, flow). The derived figure is rebuilt here from the HS10
    value of both headings, which the reconciliation shows equals the HS4
    value, so the comparison does not depend on the HS4 files being on disk.

    The gap between the two decomposes into:
      nongold_usd     7115 lines that are not gold (silver bars, PGM bars,
                      catalysts) - priced as gold by the derived route
      mixed_usd       the export line whose metal is not identified; its
                      gross mass is reported alongside as mixed_t_gross
      gold_noqty_usd  gold lines with value but no mass reported
      the remainder   unit value of the gold lines away from the LBMA
                      average: timing within the month, dore and
                      semimanufactures valued off-benchmark, keying errors
    """
    px = lbma_monthly()
    if not px:
        print(f"   {LBMA} not on disk - no quantity comparison")
        return []
    acc: dict[tuple, dict] = {}
    for r in rows:
        k = (r["date"], r["cty_code"], r["flow"])
        a = acc.setdefault(k, {"cty_name": r["cty_name"],
                               "is_country": r["is_country"],
                               "value_usd": 0.0, "nongold_usd": 0.0,
                               "mixed_usd": 0.0, "mixed_t": 0.0,
                               "gold_noqty_usd": 0.0, "t_content": 0.0,
                               "t_gross": 0.0})
        v = float(r["value_usd"])
        a["value_usd"] += v
        if r["gold_class"] == "other":
            a["nongold_usd"] += v
        elif r["gold_class"] == "mixed":
            a["mixed_usd"] += v
            a["mixed_t"] += float(r["qty1"]) / 1e6 if r["unit1"] == "GM" else 0
        elif r["gold_t"] in ("", None) or float(r["gold_t"]) == 0:
            a["gold_noqty_usd"] += v
        elif r["gold_basis"] == "content":
            a["t_content"] += float(r["gold_t"])
        else:
            a["t_gross"] += float(r["gold_t"])

    out = []
    for (date, cty, flow), a in sorted(acc.items()):
        p = px.get(date)
        if not p:
            continue
        to_t = 1 / p / OZ_PER_T
        rep = a["t_content"] + a["t_gross"]
        der = a["value_usd"] * to_t
        out.append({
            "date": date, "cty_code": cty, "cty_name": a["cty_name"],
            "is_country": a["is_country"], "flow": flow,
            "lbma_avg_usd": round(p, 2),
            "value_usd": int(a["value_usd"]),
            "derived_t": round(der, 4),
            "reported_t": round(rep, 4),
            "reported_t_content": round(a["t_content"], 4),
            "reported_t_gross": round(a["t_gross"], 4),
            "gap_t": round(der - rep, 4),
            "gap_nongold_t": round(a["nongold_usd"] * to_t, 4),
            "gap_mixed_t": round(a["mixed_usd"] * to_t, 4),
            "gap_gold_noqty_t": round(a["gold_noqty_usd"] * to_t, 4),
            "gap_unit_value_t": round(der - rep - (a["nongold_usd"]
                                      + a["mixed_usd"]
                                      + a["gold_noqty_usd"]) * to_t, 4),
            "mixed_t_gross": round(a["mixed_t"], 4),
            "derived_over_reported": round(der / rep, 4) if rep else "",
        })

    # Summary on the all-countries total, which is what the figures plot.
    tot = [r for r in out if r["cty_code"] == "-"]
    print()
    print("   QUANTITY: reported HS10 tonnes vs tonnes derived from value")
    print(f"   {'flow':7s} {'months':>6s} {'derived t':>10s} {'reported t':>10s}"
          f" {'gap t':>8s} {'non-gold':>9s} {'mixed':>7s} {'no qty':>7s}"
          f" {'unit val':>9s}"
          f"   monthly ratio p10/p50/p90")
    for flow in FLOWS:
        f = [r for r in tot if r["flow"] == flow]
        if not f:
            continue
        sm = lambda c: sum(r[c] for r in f)
        rat = sorted(r["derived_over_reported"] for r in f
                     if r["derived_over_reported"] != "")
        q = lambda x: rat[min(int(x * len(rat)), len(rat) - 1)]
        print(f"   {flow:7s} {len(f):>6d} {sm('derived_t'):>10,.0f} "
              f"{sm('reported_t'):>10,.0f} {sm('gap_t'):>8,.0f} "
              f"{sm('gap_nongold_t'):>9,.0f} {sm('gap_mixed_t'):>7,.0f} "
              f"{sm('gap_gold_noqty_t'):>7,.0f} "
              f"{sm('gap_unit_value_t'):>9,.0f}   "
              f"{q(.1):.3f} / {q(.5):.3f} / {q(.9):.3f}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="refetch even if the output already exists")
    args = ap.parse_args()
    os.chdir(ROOT)

    print("=" * 74)
    print("US CENSUS HS10 GOLD PULL")
    print("=" * 74)
    path = OUT / OUT_NAME
    if path.exists() and not args.force:
        print(f"   {OUT_NAME} already present - skipping (--force to refetch)")
    else:
        key = api_key()
        hi = TO or latest_month(key)
        print(f"   {FROM} .. {hi}")
        write(pull(key, FROM, hi), path)

    rows = read(path)
    line_list(rows)
    bad = reconcile(rows)
    write(bad, OUT / RECON_NAME)
    write(qty_compare(rows), OUT / QTY_NAME)
    print()
    print("   reconciliation: " + ("HS10 sums match the HS4 files exactly."
                                   if not bad else
                                   f"{len(bad):,} cells disagree - see "
                                   f"{RECON_NAME}."))


if __name__ == "__main__":
    main()
