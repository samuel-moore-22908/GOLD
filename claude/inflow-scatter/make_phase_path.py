"""
Three-phase path on the trade-balance plane: baseline, surge, reversal.

A two-point arrow shows *net* displacement, which is exactly the wrong measure
for a round trip - metal that goes in and comes back out nets to almost
nothing, so the annual-window figure cancels the phenomenon it is meant to
show. Three points and two segments turn the round trip into a shape: a
permanent repositioning draws a straight path, a round trip doubles back.

Phases, split where the series turns:
  baseline  Nov 2023 - Oct 2024   12 months, every calendar month once
  surge     Nov 2024 - Mar 2025    5 months, the inflow
  reversal  Apr 2025 - Nov 2025    8 months, the outflow

Because the phases are different lengths, positions are **monthly-average
rates**, not cumulative totals. Plotting cumulative values would make a long
phase look larger purely for being long.

Round-trip amplitude = min(out-leg, back-leg), both measured in log space.

The obvious statistic - path length / net displacement - is scale-free, and
that makes it useless for ranking: a heading whose net displacement happens to
land near zero gets an enormous ratio from a tiny wobble. It put engine parts
(23.5x) and footwear (21x) above gold, neither of which moved anywhere.
Requiring *both* legs to be long instead means a heading only scores by going a
long way out and a long way back, which is the claim being made. The ratio is
still reported, because it is the natural way to say "it came back", but it
does not drive the ranking.

Reads   data/processed/us_hs4_universe_monthly.csv
        data/processed/hs4_descriptions.csv
Writes  claude/inflow-scatter/scatter_phase_path.html
        claude/inflow-scatter/phase_path_points.csv
"""
import csv
import json
import math
import os
from collections import defaultdict

SRC = "data/processed/us_hs4_universe_monthly.csv"
DESCS = "data/processed/hs4_descriptions.csv"
OUTDIR = "claude/inflow-scatter"
GOLD_PARTS = ("7108", "7115")
GOLD = "7108+7115"
TOP_N = 100

PHASES = [("baseline", "2023-11", "2024-10"),
          ("surge",    "2024-11", "2025-03"),
          ("reversal", "2025-04", "2025-11")]


def load():
    agg = defaultdict(float)
    months = defaultdict(set)
    for r in csv.DictReader(open(SRC, encoding="utf-8")):
        m = r["date"][:7]
        for name, lo, hi in PHASES:
            if lo <= m <= hi:
                agg[(r["hs4"], name, r["flow"])] += float(r["value_usd"] or 0)
                months[name].add(m)
    return agg, {k: len(v) for k, v in months.items()}


def build(agg, nmon, descs):
    codes = {k[0] for k in agg}
    rows = []
    for c in sorted(codes):
        pts = []
        for name, _, _ in PHASES:
            # Monthly-average rate, so phases of different length compare.
            m = agg.get((c, name, "imports"), 0) / nmon[name]
            x = agg.get((c, name, "exports"), 0) / nmon[name]
            pts.append((m, x))
        if min(min(p) for p in pts) <= 0:
            continue
        rows.append({"hs4": c, "desc": descs.get(c, c), "pts": pts,
                     "trade": sum(m + x for m, x in pts)})

    # Gold is one heading: the 7108/7115 split is a bookkeeping artifact.
    parts = [r for r in rows if r["hs4"] in GOLD_PARTS]
    if len(parts) == len(GOLD_PARTS):
        rows = [r for r in rows if r["hs4"] not in GOLD_PARTS]
        merged = [(sum(p["pts"][i][0] for p in parts),
                   sum(p["pts"][i][1] for p in parts)) for i in range(len(PHASES))]
        rows.append({"hs4": GOLD, "desc": "GOLD (HS 7108 + 7115)",
                     "pts": merged, "trade": sum(m + x for m, x in merged)})

    for r in rows:
        (m0, x0), (m1, x1), (m2, x2) = r["pts"]
        seg = (math.hypot(math.log10(m1 / m0), math.log10(x1 / x0)) +
               math.hypot(math.log10(m2 / m1), math.log10(x2 / x1)))
        net = math.hypot(math.log10(m2 / m0), math.log10(x2 / x0))
        out = math.hypot(math.log10(m1 / m0), math.log10(x1 / x0))
        back = math.hypot(math.log10(m2 / m1), math.log10(x2 / x1))
        r["out"], r["back"] = out, back
        r["path"], r["net"] = seg, net
        # Both legs must be long. A wobble scores near zero however cleanly it
        # happens to return to its starting point.
        r["amp"] = min(out, back)
        # Guard the degenerate case where a heading returns exactly to its
        # start: the ratio is unbounded, so cap it rather than emit infinity.
        r["retrace"] = seg / net if net > 1e-6 else 999.0
        r["share"] = [m / (m + x) for m, x in r["pts"]]

    rows.sort(key=lambda r: -r["trade"])
    top = rows[:TOP_N]
    if not any(r["hs4"] == GOLD for r in top):
        g = next(r for r in rows if r["hs4"] == GOLD)
        top.append(g)
    for i, r in enumerate(sorted(top, key=lambda r: -r["amp"])):
        r["rank"] = i + 1
    return top


def main():
    descs = {}
    if os.path.exists(DESCS):
        for r in csv.DictReader(open(DESCS, encoding="utf-8")):
            descs[r["hs4"]] = r["desc"]
    agg, nmon = load()
    print("  phase months:", nmon)
    top = build(agg, nmon, descs)
    g = next(r for r in top if r["hs4"] == GOLD)
    n = len(top)
    print(f"  {n} headings")
    for (name, _, _), (m, x), s in zip(PHASES, g["pts"], g["share"]):
        print(f"    gold {name:9} M ${m/1e9:6.2f}bn/mo  X ${x/1e9:6.2f}bn/mo  share {s:.2f}")
    print(f"  gold: out {g['out']:.2f} back {g['back']:.2f} -> amplitude "
          f"{g['amp']:.2f}, retrace {g['retrace']:.2f}x, rank #{g['rank']} of {n}")
    print("  largest round trips (min of the two legs):")
    for r in sorted(top, key=lambda r: r["rank"])[:6]:
        print(f"    #{r['rank']:>2} {r['hs4']:10} {r['desc'][:32]:34} "
              f"amp {r['amp']:.2f}  out {r['out']:.2f} back {r['back']:.2f} "
              f"retrace {r['retrace']:.1f}x")

    with open(f"{OUTDIR}/phase_path_points.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hs4", "desc", "rank", "amp", "out", "back", "retrace", "path", "net"] +
                   [f"{k}_{p[0]}" for p in PHASES for k in ("m", "x")])
        for r in sorted(top, key=lambda r: r["rank"]):
            w.writerow([r["hs4"], r["desc"], r["rank"], round(r["amp"], 3),
                        round(r["out"], 3), round(r["back"], 3),
                        round(r["retrace"], 3), round(r["path"], 3),
                        round(r["net"], 3)] +
                       [round(v, 1) for p in r["pts"] for v in p])

    payload = [{"c": r["hs4"], "d": r["desc"], "rk": r["rank"],
                "rt": round(r["retrace"], 2), "amp": round(r["amp"], 2),
                "p": [[round(m / 1e6, 2), round(x / 1e6, 2)] for m, x in r["pts"]]}
               for r in top]
    open(f"{OUTDIR}/scatter_phase_path.html", "w", encoding="utf-8").write(
        TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
                .replace("__GOLD__", GOLD).replace("__N__", str(n))
                .replace("__RT__", f"{g['retrace']:.1f}")
                .replace("__RANK__", str(g["rank"])))
    print(f"  wrote {OUTDIR}/scatter_phase_path.html")
    return 0


TEMPLATE = r"""<title>Gold — Round Trip</title>
<style>
 .viz-root{color-scheme:light;--surface-1:#fcfcfb;--text-primary:#0b0b0b;
  --text-secondary:#52514e;--muted:#898781;--grid:#e1e0d9;--baseline:#c3c2b7;
  --gold:#eda100;--other:#a9a7a0;--ring:rgba(11,11,11,0.10);
  background:var(--surface-1);color:var(--text-primary);
  font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  padding:22px;max-width:1040px;margin:0 auto}
 @media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{
  color-scheme:dark;--surface-1:#1a1a19;--text-primary:#fff;--text-secondary:#c3c2b7;
  --muted:#898781;--grid:#2c2c2a;--baseline:#383835;--gold:#c98500;--other:#6f6d67;
  --ring:rgba(255,255,255,0.10)}}
 :root[data-theme="dark"] .viz-root{color-scheme:dark;--surface-1:#1a1a19;
  --text-primary:#fff;--text-secondary:#c3c2b7;--muted:#898781;--grid:#2c2c2a;
  --baseline:#383835;--gold:#c98500;--other:#6f6d67;--ring:rgba(255,255,255,0.10)}
 body{margin:0;background:var(--surface-1)}
 h1{font-size:19px;margin:0 0 4px}
 .sub{color:var(--text-secondary);font-size:13px;margin:0 0 12px}
 .legend{display:flex;gap:16px;font-size:12px;color:var(--text-secondary);
  margin:0 0 8px;flex-wrap:wrap}
 .key{display:inline-flex;align-items:center;gap:6px}
 .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
 .hollow{background:transparent;border:2.5px solid var(--gold)}
 table{border-collapse:collapse;font-size:12px;margin-top:20px;width:100%}
 th,td{text-align:right;padding:5px 9px;border-bottom:1px solid var(--grid)}
 th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
 th{color:var(--text-secondary);font-weight:600}
 caption{caption-side:top;text-align:left;font-size:12px;color:var(--text-secondary);
  padding-bottom:7px}
 tr.g td{background:rgba(237,161,0,.13);font-weight:600}
 #tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--surface-1);border:1px solid var(--ring);border-radius:5px;
  padding:7px 10px;font-size:12px;box-shadow:0 3px 10px rgba(0,0,0,.13);z-index:9}
 .wrap{overflow-x:auto}
</style>
<div class="viz-root">
<h1>Gold went in, then came back out</h1>
<p class="sub">The __N__ most-traded HS4 headings. Horizontal is US exports,
vertical is US imports, both monthly-average rates on a log scale. The diagonal
is M&nbsp;=&nbsp;X. Each heading is three points — <b>baseline</b> (Nov&nbsp;23–Oct&nbsp;24),
<b>surge</b> (Nov&nbsp;24–Mar&nbsp;25), <b>reversal</b> (Apr–Nov&nbsp;25) — joined in order.
A permanent repositioning draws a straight path. <b>A round trip doubles back</b>,
and gold's retraces __RT__× its net displacement, rank #__RANK__ of __N__.</p>
<div class="legend">
 <span class="key"><span class="dot hollow"></span>baseline</span>
 <span class="key"><span class="dot" style="background:var(--gold);opacity:.55"></span>surge</span>
 <span class="key"><span class="dot" style="background:var(--gold)"></span>reversal (end)</span>
 <span class="key"><span class="dot" style="background:var(--other)"></span>other headings</span>
</div>
<div class="wrap"><svg id="chart" width="1000" height="640" role="img"
 aria-label="Three-phase path of US imports against exports by HS4 heading"></svg></div>
<table id="tbl"><caption>Largest round trips — ranked on the shorter of the two legs,
so a heading must travel far out <em>and</em> far back</caption>
<thead><tr><th>#</th><th>HS4</th><th>Amplitude</th><th>Retrace</th><th>Imports M, $bn/mo</th>
<th>Exports X, $bn/mo</th></tr></thead><tbody></tbody></table>
</div><div id="tip"></div>
<script>
const D=__DATA__, GOLD="__GOLD__";
const W=1000,H=640,M={t:26,r:150,b:58,l:74},iw=W-M.l-M.r,ih=H-M.t-M.b;
const all=D.flatMap(d=>d.p.flat()).filter(v=>v>0);
const L0=Math.log10(Math.min(...all)*0.7),L1=Math.log10(Math.max(...all)*1.5);
const sx=v=>M.l+(Math.log10(v)-L0)/(L1-L0)*iw;
const sy=v=>M.t+ih-(Math.log10(v)-L0)/(L1-L0)*ih;
const svg=document.getElementById("chart"),NS="http://www.w3.org/2000/svg";
const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e};
const defs=el("defs",{});
[["ah","var(--gold)"],["ah2","var(--other)"]].forEach(([id,c])=>{
 const m=el("marker",{id,viewBox:"0 0 10 10",refX:"8",refY:"5",markerWidth:"5",
  markerHeight:"5",orient:"auto-start-reverse"});
 m.appendChild(el("path",{d:"M0,0 L10,5 L0,10 z",fill:c}));defs.appendChild(m)});
svg.appendChild(defs);
for(let e=Math.ceil(L0);e<=L1;e++){const v=Math.pow(10,e);
 svg.appendChild(el("line",{x1:sx(v),x2:sx(v),y1:M.t,y2:M.t+ih,stroke:"var(--grid)","stroke-width":1}));
 svg.appendChild(el("line",{x1:M.l,x2:M.l+iw,y1:sy(v),y2:sy(v),stroke:"var(--grid)","stroke-width":1}));
 const lab=v>=1000?"$"+(v/1000)+"bn":"$"+v+"m";
 let t=el("text",{x:sx(v),y:M.t+ih+20,"text-anchor":"middle","font-size":11,fill:"var(--muted)"});
 t.textContent=lab;svg.appendChild(t);
 t=el("text",{x:M.l-10,y:sy(v)+4,"text-anchor":"end","font-size":11,fill:"var(--muted)"});
 t.textContent=lab;svg.appendChild(t)}
const lo=Math.pow(10,L0),hi=Math.pow(10,L1);
svg.appendChild(el("line",{x1:sx(lo),y1:sy(lo),x2:sx(hi),y2:sy(hi),
 stroke:"var(--baseline)","stroke-width":2,"stroke-dasharray":"6 5"}));
let t=el("text",{x:sx(hi)-8,y:sy(hi)+18,"text-anchor":"end","font-size":11,fill:"var(--muted)"});
t.textContent="M = X · balanced";svg.appendChild(t);
t=el("text",{x:M.l+14,y:M.t+18,"font-size":11.5,fill:"var(--muted)"});
t.textContent="↑ import-dominated";svg.appendChild(t);
t=el("text",{x:M.l+iw-8,y:M.t+ih-12,"text-anchor":"end","font-size":11.5,fill:"var(--muted)"});
t.textContent="export-dominated ↓";svg.appendChild(t);
t=el("text",{x:M.l+iw/2,y:H-14,"text-anchor":"middle","font-size":12,fill:"var(--text-secondary)"});
t.textContent="US exports, $m per month (log scale)";svg.appendChild(t);
t=el("text",{x:-(M.t+ih/2),y:18,transform:"rotate(-90)","text-anchor":"middle","font-size":12,
 fill:"var(--text-secondary)"});t.textContent="US imports, $m per month (log scale)";svg.appendChild(t);
const tip=document.getElementById("tip");
function hov(n,h){n.addEventListener("mousemove",e=>{tip.innerHTML=h;tip.style.opacity=1;
 tip.style.left=(e.clientX+14)+"px";tip.style.top=(e.clientY-10)+"px"});
 n.addEventListener("mouseleave",()=>tip.style.opacity=0)}
const fmt=v=>v>=1000?"$"+(v/1000).toFixed(2)+"bn":"$"+v.toFixed(0)+"m";
const NAMES=["baseline","surge","reversal"];
D.slice().sort((a,b)=>(a.c===GOLD)-(b.c===GOLD)).forEach(d=>{
 const g=d.c===GOLD, big=d.amp>=0.5, col=g?"var(--gold)":"var(--other)", grp=el("g",{});
 const op=g?1:(big?.65:.28);
 for(let i=0;i<d.p.length-1;i++){
  grp.appendChild(el("line",{x1:sx(d.p[i][1]),y1:sy(d.p[i][0]),
   x2:sx(d.p[i+1][1]),y2:sy(d.p[i+1][0]),stroke:col,
   "stroke-width":g?3:(big?1.8:1.2),"marker-end":g?"url(#ah)":"url(#ah2)",opacity:op}))}
 d.p.forEach((pt,i)=>{
  const last=i===d.p.length-1;
  grp.appendChild(el("circle",{cx:sx(pt[1]),cy:sy(pt[0]),
   r:g?(last?9:6.5):(last?4:3),
   fill:i===0?"var(--surface-1)":col,stroke:col,
   "stroke-width":g?(i===0?3:2):1.2,
   opacity:i===0?op:(last?op:op*0.8)}))});
 hov(grp,`<b>${d.d}</b> (HS ${d.c})<br>`+
  d.p.map((pt,i)=>`${NAMES[i]}: M ${fmt(pt[0])} · X ${fmt(pt[1])}`).join("<br>")+
  `<br>amplitude ${d.amp} · retrace ${d.rt}× (rank #${d.rk})`);
 svg.appendChild(grp);
 if(g||d.rk<=3){const lb=el("text",{x:sx(d.p[2][1])+11,y:sy(d.p[2][0])+4,
  "font-size":g?13:10.5,"font-weight":g?700:400,
  fill:g?"var(--text-primary)":"var(--text-secondary)"});
  lb.textContent=g?"GOLD":d.d.slice(0,22);svg.appendChild(lb)}});
const tb=document.querySelector("#tbl tbody");
D.slice().sort((a,b)=>a.rk-b.rk).slice(0,10).forEach(d=>{
 const tr=document.createElement("tr"); if(d.c===GOLD)tr.className="g";
 tr.innerHTML=`<td>${d.rk}</td><td>${d.d.slice(0,32)} (${d.c})</td>`+
  `<td>${d.amp}</td><td>${d.rt}×</td>`+
  `<td>${d.p.map(p=>(p[0]/1000).toFixed(1)).join(" → ")}</td>`+
  `<td>${d.p.map(p=>(p[1]/1000).toFixed(1)).join(" → ")}</td>`;
 tb.appendChild(tr)});
</script>
"""

if __name__ == "__main__":
    raise SystemExit(main())
