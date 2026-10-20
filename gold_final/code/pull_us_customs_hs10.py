#!/usr/bin/env python3
"""
US gold trade by partner at HS10, in tonnes of fine gold, Jan 2015 on.

One output:

  us_gold_hs10_partner_monthly.csv   every gold HS10 line under 7108 and 7115,
                                     every partner (and Census's partner
                                     groupings), monthly, imports and exports:
                                     value, reported mass, and fine_t - tonnes
                                     of pure gold.

WHY HS10. Census leaves the quantity fields blank at HS4: a heading mixes lines
reported in different units, so there is nothing to add up. At HS10 every gold
line carries a mass, so tonnage can rest on what Census reports rather than on
value / LBMA price. The HS4 pull's docstring says the opposite; that holds at
HS4 only.

WHICH LINES ARE KEPT. Gold lines with a mass unit, nothing else.
  - Every 7108 line is gold. Gold leaf (7108131000) is dropped: it is
    reported in square centimetres and its second quantity, nominally gold
    content, implies about $20/oz. It is ~$0.1bn over the whole window.
  - Heading 7115 also holds silver bars, platinum-group bars, platinum
    catalyst gauze and silver/platinum articles. Those are dropped. Lines
    are classified from the Census description, and the kept lines are
    printed on every run so a new or renamed line is visible.
  - EXPORT 7115900000 ("other precious-metal articles, NESOI") is dropped by
    the same rule: until Schedule B split gold out as 7115900010 in January
    2026 it held gold, silver and platinum together, and its description
    names no metal. That loses real gold - about $21bn of tariff-episode bars
    left under it in 2025 - so US gold EXPORTS before 2026 are a lower bound.

FINE GOLD. The unit decides how mass becomes pure gold:
  CGM  grams of gold content. Reported fine gold; taken as is.
       fine_t_provenance = "reported"
  GM, with a legal purity floor - imports 7115900530 (the tariff-episode bars)
       and 7108135500, both defined as >= 99.5% gold. Gross mass x 0.995, so
       fine gold is a lower bound, off by at most half a percent.
       fine_t_provenance = "reported_x_floor"
  GM, no floor - powder, semimanufactures NESOI, other unwrought, gold
       articles. Gross mass x a purity estimated from the LBMA price:
           purity = sum(value) / sum(gross troy oz x month's mean LBMA PM)
       over the all-countries total for that line and year, capped at 1. A
       year with under MIN_PURITY_KG of gross mass uses the line's
       whole-window purity instead. fine_t_provenance = "derived_lbma_purity"

  Purity is a constant per line-year, never per cell. Applied cell by cell,
  gross x value / (price x gross) collapses to value / price - the derived
  tonnage this file exists to replace. As a constant it only sets the level;
  the reported mass still drives the monthly series. Customs value includes
  any fabrication premium, so the estimate leans high: fine gold on these
  lines is, if anything, overstated.

PARTNER ROWS. Census returns country groupings (EU, OPEC, "1XXX" North
America, ...) and a "-" all-countries total alongside the countries. They are
kept, and is_country marks the real partners. Never sum over all rows.

Idempotent: an existing output is left alone unless --force is passed.
Requests are spaced deliberately.

Needs CENSUS_API_KEY, in the repo .env or the environment, and lbma_pm.csv
(daily, date,lbma_pm_usd) in OUT_DIR.

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

OUT_NAME = "us_gold_hs10_partner_monthly.csv"
LBMA = "lbma_pm.csv"                # daily, date,lbma_pm_usd

G_PER_OZ = 31.1034768

# Gross-weight lines whose tariff definition sets a minimum gold purity.
PURITY_FLOOR = {
    ("imports", "7115900530"): 0.995,   # rectangular shapes, >= 99.5% gold
    ("imports", "7108135500"): 0.995,   # semimanufactured, >= 99.5% gold
}
# Below this much gross mass in a line-year, the yearly purity is too noisy and
# the line's whole-window purity is used instead.
MIN_PURITY_KG = 100

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
# re-exports. Same value fields as the HS4 pull.
FLOWS = {
    "imports": {"code": "I_COMMODITY", "desc": "I_COMMODITY_SDESC",
                "value": "GEN_VAL_MO", "q1": "GEN_QY1_MO"},
    "exports": {"code": "E_COMMODITY", "desc": "E_COMMODITY_SDESC",
                "value": "ALL_VAL_MO", "q1": "QTY_1_MO"},
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


def is_gold_line(hs10: str, desc: str) -> bool:
    if hs10.startswith("7108"):
        return True
    d = desc.upper()
    # A description naming silver or platinum metals wins over a stray
    # mention of gold.
    if _SILVER_PLAT.search(d):
        return False
    return bool(_GOLD.search(d))


def is_country(code: str) -> bool:
    """Real partner, not a grouping. Countries are four digits from 1000 up;
    groupings are 00xx or carry an X ("1XXX"); the total is "-"."""
    return code.isdigit() and len(code) == 4 and int(code) >= 1000


def lbma_monthly() -> dict[str, float]:
    """Month-start date -> average LBMA PM over the month."""
    path = OUT / LBMA
    if not path.exists():
        raise SystemExit(f"{path} not found - purity needs the LBMA PM series")
    acc: dict[str, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = num(r.get("lbma_pm_usd"))
            if v > 0:
                acc[r["date"][:7] + "-01"].append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


# ---------------------------------------------------------------------- pull
def pull(key: str, lo: str, hi: str) -> list[dict]:
    """Gold lines with a mass unit only, every partner row, mass in grams."""
    out = []
    for flow, s in FLOWS.items():
        fields = ["CTY_CODE", "CTY_NAME", s["code"], s["desc"], s["value"],
                  s["q1"], "UNIT_QY1"]
        for hs in HS_GOLD:
            for a, b in chunks(lo, hi, CHUNK_MONTHS):
                print(f"   hs10  {flow:7s} {hs}*  {a}..{b}", flush=True)
                rows = get(flow, fields, a, b, key, commodity=f"{hs}*")
                h = rows[0]
                ix = {f: h.index(f) for f in fields + ["time"]}
                for r in rows[1:]:
                    hs10, desc = r[ix[s["code"]]], r[ix[s["desc"]]]
                    unit = r[ix["UNIT_QY1"]]
                    if not is_gold_line(hs10, desc) or unit not in MASS_G:
                        continue
                    out.append({
                        "date": f"{r[ix['time']]}-01",
                        "cty_code": r[ix["CTY_CODE"]],
                        "cty_name": r[ix["CTY_NAME"]],
                        "is_country": int(is_country(r[ix["CTY_CODE"]])),
                        "flow": flow,
                        "hs4": hs10[:4],
                        "hs10": hs10,
                        "hs10_desc": desc,
                        "value_usd": int(num(r[ix[s["value"]]])),
                        "mass_g": num(r[ix[s["q1"]]]) * MASS_G[unit],
                        "unit": unit,
                    })
    return out


# --------------------------------------------------------------- fine gold
def purities(rows: list[dict], px: dict[str, float]) -> dict[tuple, tuple]:
    """(flow, hs10, year) -> (purity, source) for the gross lines with no
    floor. Estimated on the all-countries total, so each shipment counts once."""
    yr = defaultdict(lambda: [0.0, 0.0, 0.0])      # value, gold value, grams
    win = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        k = (r["flow"], r["hs10"])
        if r["cty_code"] != "-" or r["unit"] in CONTENT_UNITS \
                or k in PURITY_FLOOR or r["date"] not in px:
            continue
        gv = r["mass_g"] / G_PER_OZ * px[r["date"]]
        a = yr[k + (r["date"][:4],)]
        a[0] += r["value_usd"]; a[1] += gv; a[2] += r["mass_g"]
        win[k][0] += r["value_usd"]; win[k][1] += gv
    out = {}
    for (flow, hs10, y), (v, gv, g) in yr.items():
        if g >= MIN_PURITY_KG * 1000 and gv > 0:
            out[(flow, hs10, y)] = (min(1.0, v / gv), "line-year")
        else:
            wv, wgv = win[(flow, hs10)]
            out[(flow, hs10, y)] = (min(1.0, wv / wgv) if wgv else 0.0,
                                    "line-window")
    return out


def add_fine(rows: list[dict], px: dict[str, float]) -> list[dict]:
    pur = purities(rows, px)
    for r in rows:
        k = (r["flow"], r["hs10"])
        if r["unit"] in CONTENT_UNITS:
            p, basis, prov = 1.0, "content", "reported"
        elif k in PURITY_FLOOR:
            p, basis, prov = PURITY_FLOOR[k], "gross_floor", "reported_x_floor"
        else:
            p, src = pur.get(k + (r["date"][:4],), (None, ""))
            basis, prov = "gross_lbma", "derived_lbma_purity"
            if p is None:                       # no LBMA price for that year
                p, prov = "", ""
        r["basis"] = basis
        r["purity"] = p if p == "" else round(p, 4)
        r["fine_t"] = "" if p == "" else round(r["mass_g"] * p / 1e6, 6)
        r["fine_t_provenance"] = prov
        r["mass_g"] = round(r["mass_g"], 1)
    return rows


def summary(rows: list[dict]) -> None:
    """Kept lines, how each becomes fine gold, and the purity it gets. Totals
    are all-countries over the window."""
    acc: dict[tuple, dict] = {}
    for r in rows:
        if r["cty_code"] != "-":
            continue
        e = acc.setdefault((r["flow"], r["hs10"]), {
            "desc": r["hs10_desc"], "basis": r["basis"], "gross": 0.0,
            "fine": 0.0, "p": set(), "lo": r["date"], "hi": r["date"]})
        e["gross"] += r["mass_g"] / 1e6
        e["fine"] += r["fine_t"] or 0.0
        if r["purity"] != "":
            e["p"].add(r["purity"])
        e["lo"], e["hi"] = min(e["lo"], r["date"]), max(e["hi"], r["date"])
    print()
    print("   GOLD LINES KEPT  (all countries, full window)")
    print(f"   {'flow':7s} {'hs10':10s} {'basis':11s} {'purity':>13s} "
          f"{'gross t':>8s} {'fine t':>8s}  {'first':7s} {'last':7s} description")
    for (flow, hs10), e in sorted(acc.items()):
        p = sorted(e["p"])
        ps = (f"{p[0]:.3f}" if len(p) == 1 else
              f"{p[0]:.3f}-{p[-1]:.3f}" if p else "")
        print(f"   {flow:7s} {hs10:10s} {e['basis']:11s} {ps:>13s} "
              f"{e['gross']:8,.0f} {e['fine']:8,.0f}  {e['lo'][:7]} "
              f"{e['hi'][:7]} {e['desc']}")
    print()
    for flow in FLOWS:
        by = defaultdict(float)
        for (f, _), e in acc.items():
            if f == flow:
                by[e["basis"]] += e["fine"]
        print(f"   {flow:7s} fine t  {sum(by.values()):8,.0f}   = "
              + "  ".join(f"{b} {by[b]:,.0f}" for b in
                          ("content", "gross_floor", "gross_lbma")))


def write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"   wrote {path.relative_to(ROOT)}  ({len(rows):,} rows)", flush=True)


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["mass_g"] = float(r["mass_g"])
        r["fine_t"] = float(r["fine_t"]) if r["fine_t"] else ""
        r["purity"] = float(r["purity"]) if r["purity"] else ""
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="refetch even if the output already exists")
    args = ap.parse_args()
    os.chdir(ROOT)

    print("=" * 74)
    print("US CENSUS HS10 GOLD PULL - FINE TONNES")
    print("=" * 74)
    path = OUT / OUT_NAME
    if path.exists() and not args.force:
        print(f"   {OUT_NAME} already present - skipping (--force to refetch)")
        rows = read(path)
    else:
        px = lbma_monthly()
        key = api_key()
        hi = TO or latest_month(key)
        print(f"   {FROM} .. {hi}")
        rows = add_fine(pull(key, FROM, hi), px)
        write(rows, path)
    summary(rows)


if __name__ == "__main__":
    main()
