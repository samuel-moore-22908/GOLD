"""
Build the inflow scatter: the 100 most-traded HS4 headings, positioned by US
import value and import share, before and during the tariff scare.

Reads   data/processed/us_hs4_universe_monthly.csv
Writes  figures/inflow_scatter.html
        data/processed/inflow_scatter_points.csv

Axes, and why:
  x  US imports, Jan-Apr, log10. HS4 import values span five orders of
     magnitude, so a linear axis would compress everything but the top decile
     into the left margin.
  y  import share = M / (M + X). 0 = pure export, 0.5 = balanced two-way
     trade, 1 = pure import. Rising means shifting toward net imports, which
     is the claim being made.

Not Grubel-Lloyd. GL = 1 - |X-M|/(X+M) equals 1 when trade is *balanced* and 0
when it is one-directional, so it runs backwards for this figure, and it is
unsigned: a pure exporter and a pure importer both score 0, which cannot
express "flowing into the US". See figures/FIGURE_DECISIONS.md.
"""
import csv
import html
import json
import math
import os
from collections import defaultdict

SRC = "data/processed/us_hs4_universe_monthly.csv"
OUTDIR = "claude/inflow-scatter"

# The two flows are mirror images on the y-axis (export share = 1 - import
# share) but not on the x-axis, which is the point: a heading can grow its
# import channel and its export channel at once. Gold does exactly that -
# imports 15.6x, exports 2.5x - because the metal went in and then came back
# out when the tariff exemption landed in April.
FLOWS = {
    "imports": {"val": ("m24", "m25"), "share": lambda r, y: r[f"share{y}"],
                "xlab": "US imports, Jan-Apr (log scale)",
                "ylab": "Import share  M / (M+X)",
                "title": "Gold was an outlier in direction and in size",
                "ref": "0.50 - balanced two-way trade"},
    "exports": {"val": ("x24", "x25"), "share": lambda r, y: 1 - r[f"share{y}"],
                "xlab": "US exports, Jan-Apr (log scale)",
                "ylab": "Export share  X / (M+X)",
                "title": "The same episode seen from the export side",
                "ref": "0.50 - balanced two-way trade"},
}
# Two headings, not one. Switzerland reports the bullion as 7108; US Census
# books the same shipments under 7115 ("articles of precious metal NESOI"),
# which is where the 2025 inflow actually lands - $0.5bn/month in 2024 rising
# to $30bn in January 2025. Plotting only 7108 misses the entire episode.
GOLD_CODES = ("7115", "7108")
GOLD_COMBINED = "7108+7115"
GOLD = "7108+7115"
TOP_N = 100


def load():
    agg = defaultdict(float)          # (hs4, year, flow) -> value
    for r in csv.DictReader(open(SRC, encoding="utf-8")):
        year = r["date"][:4]
        agg[(r["hs4"], year, r["flow"])] += float(r["value_usd"] or 0)
    return agg


def build(agg, descs):
    codes = {k[0] for k in agg}
    rows = []
    for c in sorted(codes):
        m24, x24 = agg.get((c, "2024", "imports"), 0), agg.get((c, "2024", "exports"), 0)
        m25, x25 = agg.get((c, "2025", "imports"), 0), agg.get((c, "2025", "exports"), 0)
        # A heading needs trade in both windows to have a movement to plot, and
        # a positive import value or the log axis is undefined.
        if min(m24, m25, x24, x25) <= 0:
            continue
        rows.append({
            "hs4": c, "desc": descs.get(c, ""),
            "m24": m24, "x24": x24, "m25": m25, "x25": x25,
            "share24": m24 / (m24 + x24), "share25": m25 / (m25 + x25),
            "trade": m24 + x24 + m25 + x25,
        })

    # The 7108/7115 split is a classification artifact, not an economic
    # distinction: Switzerland reports the same bars as 7108 and US Census as
    # 7115. Add their sum as a synthetic heading, because only the combined
    # series shows gold crossing the balance line - 7115 alone was already
    # import-dominated before the episode.
    parts = {c: next((r for r in rows if r["hs4"] == c), None) for c in GOLD_CODES}
    if all(parts.values()):
        a, b = parts["7115"], parts["7108"]
        m24, x24 = a["m24"] + b["m24"], a["x24"] + b["x24"]
        m25, x25 = a["m25"] + b["m25"], a["x25"] + b["x25"]
        # Replace the parts rather than adding to them: the 7108/7115 split is
        # a bookkeeping artifact, so gold should appear once in the universe,
        # not three times competing with itself for a place in the top 100.
        rows = [r for r in rows if r["hs4"] not in GOLD_CODES]
        rows.append({"hs4": GOLD_COMBINED, "desc": "GOLD (HS 7108 + 7115)",
                     "m24": m24, "x24": x24, "m25": m25, "x25": x25,
                     "share24": m24 / (m24 + x24), "share25": m25 / (m25 + x25),
                     "trade": m24 + x24 + m25 + x25})

    rows.sort(key=lambda r: -r["trade"])
    top = rows[:TOP_N]
    order = [r["hs4"] for r in rows]
    for code in [GOLD_COMBINED]:
        rank = order.index(code) + 1 if code in order else None
        if any(r["hs4"] == code for r in top):
            print(f"  HS {code} ranks #{rank} by total trade - already in top {TOP_N}")
        else:
            g = next((r for r in rows if r["hs4"] == code), None)
            if g:
                top.append(g)
                print(f"  HS {code} ranks #{rank} by total trade - appended")

    return top


def score(top, flow):
    """Standardised displacement for one flow.

    Ranked separately per flow because the value axis differs: a heading that
    barely moved its imports may have moved its exports a great deal.
    """
    v0, v1 = FLOWS[flow]["val"]
    sh = FLOWS[flow]["share"]
    for r in top:
        r["dx"] = math.log10(r[v1]) - math.log10(r[v0])
        r["dy"] = sh(r, "25") - sh(r, "24")
    for k in ("dx", "dy"):
        vals = [r[k] for r in top]
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
        for r in top:
            r["z_" + k] = (r[k] - mu) / sd
    for r in top:
        r["disp"] = math.hypot(r["z_dx"], r["z_dy"])
    for i, r in enumerate(sorted(top, key=lambda r: -r["disp"])):
        r["rank"] = i + 1
    return top


def emit(top, flow, n):
    """Write one figure for one flow."""
    cfg = FLOWS[flow]
    v0, v1 = cfg["val"]
    sh = cfg["share"]
    score(top, flow)
    g = next(r for r in top if r["hs4"] == GOLD)
    print(f"  [{flow}] gold rank #{g['rank']} of {n} "
          f"({100 * (1 - (g['rank'] - 1) / n):.0f}th pct) | "
          f"${g[v0] / 1e9:.2f}bn -> ${g[v1] / 1e9:.2f}bn | "
          f"share {sh(g, '24'):.3f} -> {sh(g, '25'):.3f}")

    csv_path = f"{OUTDIR}/scatter_points_{flow}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        cols = ["hs4", "desc", "m24", "x24", "m25", "x25", "share24", "share25",
                "trade", "dx", "dy", "disp", "rank"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(top, key=lambda r: r["rank"]))

    payload = [{"c": r["hs4"], "d": r["desc"] or r["hs4"],
                "m0": round(r[v0] / 1e6, 2), "s0": round(sh(r, "24"), 4),
                "m1": round(r[v1] / 1e6, 2), "s1": round(sh(r, "25"), 4),
                "rk": r["rank"]} for r in top]
    html_path = f"{OUTDIR}/scatter_{flow}.html"
    sub = (f"Gold moved further than all but {g['rank'] - 1} of the {n} "
           f"most-traded headings on this axis.")
    open(html_path, "w", encoding="utf-8").write(
        TEMPLATE.replace("__DATA__", json.dumps(payload))
                .replace("__GOLD__", GOLD).replace("__N__", str(n))
                .replace("__TITLE__", html.escape(cfg["title"]))
                .replace("__XLAB__", html.escape(cfg["xlab"]))
                .replace("__YLAB__", html.escape(cfg["ylab"]))
                .replace("__REF__", html.escape(cfg["ref"]))
                .replace("__FLOW__", flow)
                .replace("__SUB__", html.escape(sub)))
    print(f"       wrote {html_path} and {csv_path}")


def main():
    if not os.path.exists(SRC):
        print(f"error: {SRC} not found - run src/pull_us_hs4_universe.py first")
        return 2
    descs = {}
    if os.path.exists("data/processed/hs4_descriptions.csv"):
        for r in csv.DictReader(open("data/processed/hs4_descriptions.csv",
                                     encoding="utf-8")):
            descs[r["hs4"]] = r["desc"]

    top = build(load(), descs)
    n = len(top)
    print(f"  plotting {n} headings")
    os.makedirs(OUTDIR, exist_ok=True)
    for flow in FLOWS:
        emit(top, flow, n)
    return 0


TEMPLATE = r"""<title>Gold Scatter — __FLOW__</title>
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
 .sub{color:var(--text-secondary);font-size:13px;margin:0 0 14px}
 .legend{display:flex;gap:18px;font-size:12px;color:var(--text-secondary);margin:0 0 8px}
 .key{display:inline-flex;align-items:center;gap:7px}
 .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
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
<h1>__TITLE__</h1>
<p class="sub">The __N__ most-traded HS4 headings, Jan–Apr 2024 → Jan–Apr 2025.
Each heading is two points joined by an arrow. __SUB__</p>
<div class="legend">
  <span class="key"><span class="dot" style="background:var(--gold)"></span>Gold (HS 7108 + 7115)</span>
  <span class="key"><span class="dot" style="background:var(--other)"></span>Other headings</span>
  <span class="key">→ arrow points to Jan–Apr 2025</span>
</div>
<div class="wrap"><svg id="chart" width="1000" height="600" role="img"
 aria-label="Connected scatter of US imports against import share by HS4 heading"></svg></div>
<table id="tbl"><caption>The ten headings that moved furthest, by standardised
displacement across both axes</caption>
<thead><tr><th>#</th><th>HS4</th><th>2024</th><th>2025</th><th>Share 2024</th><th>Share 2025</th></tr></thead><tbody></tbody></table>
</div><div id="tip"></div>
<script>
const D=__DATA__, GOLDS=["7108+7115"], GOLD="__GOLD__";
const W=1000,H=600,M={t:26,r:120,b:58,l:70},iw=W-M.l-M.r,ih=H-M.t-M.b;
const xs=D.flatMap(d=>[d.m0,d.m1]).filter(v=>v>0);
const X0=Math.log10(Math.min(...xs)*0.7),X1=Math.log10(Math.max(...xs)*1.4);
const sx=v=>M.l+(Math.log10(v)-X0)/(X1-X0)*iw, sy=v=>M.t+(1-v)*ih;
const svg=document.getElementById("chart"),NS="http://www.w3.org/2000/svg";
const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e};
const defs=el("defs",{});
[["ah","var(--gold)"],["ah2","var(--other)"]].forEach(([id,c])=>{
 const m=el("marker",{id,viewBox:"0 0 10 10",refX:"8",refY:"5",markerWidth:"5",
  markerHeight:"5",orient:"auto-start-reverse"});
 m.appendChild(el("path",{d:"M0,0 L10,5 L0,10 z",fill:c}));defs.appendChild(m)});
svg.appendChild(defs);
for(let s=0;s<=1.0001;s+=0.25){
 svg.appendChild(el("line",{x1:M.l,x2:M.l+iw,y1:sy(s),y2:sy(s),stroke:"var(--grid)","stroke-width":1}));
 const t=el("text",{x:M.l-10,y:sy(s)+4,"text-anchor":"end","font-size":11,fill:"var(--muted)"});
 t.textContent=s.toFixed(2);svg.appendChild(t)}
svg.appendChild(el("line",{x1:M.l,x2:M.l+iw,y1:sy(.5),y2:sy(.5),stroke:"var(--baseline)",
 "stroke-width":1.5,"stroke-dasharray":"5 4"}));
const bl=el("text",{x:M.l+6,y:sy(.5)-7,"font-size":11,fill:"var(--muted)"});
bl.textContent="__REF__";svg.appendChild(bl);
for(let e=Math.ceil(X0);e<=X1;e++){const v=Math.pow(10,e);
 svg.appendChild(el("line",{x1:sx(v),x2:sx(v),y1:M.t,y2:M.t+ih,stroke:"var(--grid)","stroke-width":1}));
 const t=el("text",{x:sx(v),y:M.t+ih+20,"text-anchor":"middle","font-size":11,fill:"var(--muted)"});
 t.textContent=v>=1000?"$"+(v/1000)+"bn":"$"+v+"m";svg.appendChild(t)}
svg.appendChild(el("line",{x1:M.l,x2:M.l+iw,y1:M.t+ih,y2:M.t+ih,stroke:"var(--baseline)","stroke-width":1}));
let t=el("text",{x:M.l+iw/2,y:H-14,"text-anchor":"middle","font-size":12,fill:"var(--text-secondary)"});
t.textContent="__XLAB__";svg.appendChild(t);
t=el("text",{x:-(M.t+ih/2),y:17,transform:"rotate(-90)","text-anchor":"middle","font-size":12,
 fill:"var(--text-secondary)"});t.textContent="__YLAB__";svg.appendChild(t);
const tip=document.getElementById("tip");
function hov(n,h){n.addEventListener("mousemove",e=>{tip.innerHTML=h;tip.style.opacity=1;
 tip.style.left=(e.clientX+14)+"px";tip.style.top=(e.clientY-10)+"px"});
 n.addEventListener("mouseleave",()=>tip.style.opacity=0)}
const fmt=v=>v>=1000?"$"+(v/1000).toFixed(2)+"bn":"$"+v.toFixed(0)+"m";
D.slice().sort((a,b)=>GOLDS.includes(a.c)-GOLDS.includes(b.c)).forEach(d=>{
 const g=GOLDS.includes(d.c),col=g?"var(--gold)":"var(--other)",grp=el("g",{});
 grp.appendChild(el("line",{x1:sx(d.m0),y1:sy(d.s0),x2:sx(d.m1),y2:sy(d.s1),stroke:col,
  "stroke-width":g?3:1.5,"marker-end":g?"url(#ah)":"url(#ah2)",opacity:g?1:.45}));
 grp.appendChild(el("circle",{cx:sx(d.m0),cy:sy(d.s0),r:g?7:3.5,fill:"var(--surface-1)",
  stroke:col,"stroke-width":g?3:1.5,opacity:g?1:.55}));
 grp.appendChild(el("circle",{cx:sx(d.m1),cy:sy(d.s1),r:g?9:4.5,fill:col,
  stroke:"var(--surface-1)","stroke-width":g?2:1,opacity:g?1:.55}));
 hov(grp,`<b>${d.d}</b> (HS ${d.c})<br>2024: ${fmt(d.m0)} · share ${d.s0.toFixed(2)}`+
  `<br>2025: ${fmt(d.m1)} · share ${d.s1.toFixed(2)}<br>movement rank #${d.rk}`);
 svg.appendChild(grp);
 if(g||d.rk<=4){const lb=el("text",{x:sx(d.m1)+12,y:sy(d.s1)+4,"font-size":g?13:11,
  "font-weight":g?700:400,fill:g?"var(--text-primary)":"var(--text-secondary)"});
  lb.textContent=g?"GOLD (7108+7115)":d.d.slice(0,26);svg.appendChild(lb)}});
const tb=document.querySelector("#tbl tbody");
D.slice().sort((a,b)=>a.rk-b.rk).slice(0,10).forEach(d=>{
 const tr=document.createElement("tr");if(GOLDS.includes(d.c))tr.className="g";
 tr.innerHTML=`<td>${d.rk}</td><td>${d.d} (${d.c})</td><td>${fmt(d.m0)}</td>`+
  `<td>${fmt(d.m1)}</td><td>${d.s0.toFixed(2)}</td><td>${d.s1.toFixed(2)}</td>`;
 tb.appendChild(tr)});
</script>
"""

if __name__ == "__main__":
    raise SystemExit(main())
