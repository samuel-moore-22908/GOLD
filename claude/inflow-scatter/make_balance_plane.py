"""
Build the trade-balance plane: US imports against US exports, one arrow per
HS4 heading, from window A to window B.

The two single-flow figures share a redundant axis - export share is
arithmetically 1 - import share, and share itself is M/(M+X). Only M and X are
independent, so plotting them against each other carries everything both
panels carry, once.

Reading it: the 45-degree diagonal is M = X. Above it a heading is
import-dominated, below it export-dominated, so crossing the line upward is a
switch to flowing into the US. Distance from the origin is how much trade the
channel carries. Iso-share lines are parallel to the diagonal.

Reads   claude/inflow-scatter/scatter_points_imports.csv
Writes  claude/inflow-scatter/scatter_balance_plane.html
"""
import csv
import json
import pathlib

SRC = "claude/inflow-scatter/scatter_points_imports.csv"
TPL = "claude/inflow-scatter/_plane_template.html"
OUT = "claude/inflow-scatter/scatter_balance_plane.html"
GOLD = "7108+7115"


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    data = [{"c": r["hs4"], "d": r["desc"],
             "m0": float(r["m24"]) / 1e6, "x0": float(r["x24"]) / 1e6,
             "m1": float(r["m25"]) / 1e6, "x1": float(r["x25"]) / 1e6}
            for r in rows]
    crossed = [d for d in data
               if (d["m0"] > d["x0"]) != (d["m1"] > d["x1"])]
    g = next(d for d in data if d["c"] == GOLD)
    print(f"  {len(data)} headings; {len(crossed)} cross the M=X diagonal")
    print(f"  gold: exports ${g['x0'] / 1000:.2f}bn -> ${g['x1'] / 1000:.2f}bn, "
          f"imports ${g['m0'] / 1000:.2f}bn -> ${g['m1'] / 1000:.2f}bn")
    side = lambda d, k: "import-dominated" if d["m" + k] > d["x" + k] else "export-dominated"
    print(f"  gold moves {side(g, '0')} -> {side(g, '1')}")
    for d in sorted(crossed, key=lambda z: -(z["m1"] + z["x1"]))[:6]:
        print(f"     crosses: {d['c']:10} {d['d'][:34]}")
    tpl = pathlib.Path(TPL).read_text(encoding="utf-8")
    pathlib.Path(OUT).write_text(
        tpl.replace("__DATA__", json.dumps(data, separators=(",", ":"))),
        encoding="utf-8")
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
