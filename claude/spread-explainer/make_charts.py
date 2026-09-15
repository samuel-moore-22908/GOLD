"""
Draw the three figures in SPREAD_EXPLAINED.html as inline SVG, from the same
files the explainer quotes, and write them into the page between its
<!-- chart:name --> and <!-- /chart:name --> markers. Rerun this whenever the
underlying data change; nothing else in the page is touched.

Colours are CSS classes, not literals, so the page's light and dark themes
style the charts too.

Run from the repo root:
    .venv/Scripts/python.exe claude/spread-explainer/make_charts.py
"""
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

P = "data/processed/"
PAGE = Path(__file__).with_name("SPREAD_EXPLAINED.html")
W, H = 640, 270
L, R, T, B = 56, 24, 26, 40


class Frame:
    def __init__(self, x0, x1, y0, y1):
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

    def x(self, v):
        return L + (v - self.x0) / (self.x1 - self.x0) * (W - L - R)

    def y(self, v):
        return H - B - (v - self.y0) / (self.y1 - self.y0) * (H - T - B)


def path(fr, xs, ys):
    return "M" + " L".join(f"{fr.x(a):.1f},{fr.y(b):.1f}" for a, b in zip(xs, ys))


def dollars(v):
    return f"−${-v:,}" if v < 0 else f"${v:,}"


def axes(fr, xticks, yticks, xlab, ylab):
    out = []
    for v, lab in yticks:
        yy = fr.y(v)
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        out.append(f'<text class="tick" x="{L - 8}" y="{yy + 4:.1f}" text-anchor="end">{lab}</text>')
    for v, lab in xticks:
        xx = fr.x(v)
        out.append(f'<line class="axis" x1="{xx:.1f}" x2="{xx:.1f}" y1="{H - B}" y2="{H - B + 5}"/>')
        out.append(f'<text class="tick" x="{xx:.1f}" y="{H - B + 19}" text-anchor="middle">{lab}</text>')
    out.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}"/>')
    out.append(f'<text class="axlab" x="{L}" y="{T - 12}">{ylab}</text>')
    out.append(f'<text class="axlab" x="{W - R}" y="{H - 3}" text-anchor="end">{xlab}</text>')
    return out


def svg(label, body):
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label}">\n  '
            + "\n  ".join(body) + "\n</svg>")


def chart_sawtooth():
    """Raw dollar spread and pure carry for the active contract, Sep 2024 - Apr 2025."""
    e = pd.read_csv(P + "efp_dislocation_v2.csv", parse_dates=["date"])
    t0, t1 = pd.Timestamp("2024-09-01"), pd.Timestamp("2025-04-30")
    w = e[e.date.between(t0, t1)].reset_index(drop=True)
    d = (w.date - t0).dt.days.to_numpy(float)
    # Headroom above the data so the roll labels never sit on the series.
    fr = Frame(0, (t1 - t0).days, -50, 80)

    months = pd.date_range(t0, t1, freq="MS")
    xt = [((m - t0).days, m.strftime("%b %Y") if m.month in (9, 1) else m.strftime("%b"))
          for m in months]
    yt = [(v, dollars(v)) for v in range(-40, 61, 20)]
    body = axes(fr, xt, yt, "date", "$ per troy ounce")

    # Gaps as gaps: break the line wherever consecutive observations are > 7 days apart.
    seg = np.concatenate([[0], np.cumsum(np.diff(d) > 7)])
    for col, cls in (("basis_usd", "line-raw"), ("carry_implied_basis_usd", "line-ny")):
        for s in np.unique(seg):
            m = seg == s
            body.append(f'<path class="{cls}" d="{path(fr, d[m], w[col].to_numpy()[m])}"/>')

    switch = w.active_contract != w.active_contract.shift()
    for i in np.flatnonzero(switch.to_numpy())[1:]:
        xx = fr.x(d[i])
        body.append(f'<line class="roll" x1="{xx:.1f}" x2="{xx:.1f}" y1="{T}" y2="{H - B}"/>')
        body.append(f'<text class="note" x="{xx + 5:.1f}" y="{T + 11}">roll to {w.active_contract[i]}, '
                    f'{int(w.days_to_first_notice[i])} days left</text>')
    return svg("Raw COMEX minus London spread and pure carry, September 2024 to April 2025", body)


def chart_premium():
    """One fixed premium, annualised at every horizon."""
    e = pd.read_csv(P + "efp_dislocation_v2.csv", parse_dates=["date"])
    r = e.loc[e.date == "2025-08-08"].iloc[0]
    level = r.excess_basis_usd / r.lbma_pm_usd
    fr = Frame(0, 130, 0, 60)
    body = axes(fr, [(v, str(v)) for v in range(0, 121, 20)],
                [(v, f"{v}%") for v in range(0, 61, 15)],
                "days to first notice (τ)", f"annualised reading of a {level:.2%} premium")
    body.append(f'<rect class="shade" x="{fr.x(0):.1f}" y="{T}" width="{fr.x(20) - fr.x(0):.1f}" '
                f'height="{H - B - T}"/>')
    body.append(f'<text class="note" x="{fr.x(0) + 6:.1f}" y="{T + 12}">τ &lt; 20 dropped</text>')
    taus = np.arange(10, 131, 1.0)
    body.append(f'<path class="line-ny" d="{path(fr, taus, level * 365 / taus * 100)}"/>')
    tau_actual = int(r.days_to_first_notice)
    for tau, dx, dy, anchor, text in (
            (tau_actual, 4, -22, "end", f"{level * 365 / tau_actual:.1%}, the actual reading at τ = {tau_actual}"),
            (30, 8, -8, "start", f"{level * 365 / 30:.1%} at 30 days"),
            (10, 10, 4, "start", f"{level * 365 / 10:.1%} at 10 days")):
        v = level * 365 / tau * 100
        body.append(f'<circle class="dot-ny" cx="{fr.x(tau):.1f}" cy="{fr.y(v):.1f}" r="4"/>')
        body.append(f'<text class="note strong" x="{fr.x(tau) + dx:.1f}" y="{fr.y(v) + dy:.1f}" '
                    f'text-anchor="{anchor}">{text}</text>')
    return svg("The same 1.45 percent premium read as an annual rate at horizons from 10 to 130 days", body)


def chart_curve():
    """The 29 Jan 2025 term-structure fit that version 2 reads at 90 days."""
    c = pd.read_csv(P + "comex_contract_daily.csv", parse_dates=["date"])
    e = pd.read_csv(P + "efp_dislocation_v2.csv", parse_dates=["date"])
    g = c[(c.date == "2025-01-29") & c.days_to_first_notice.between(15, 400)
          & (c.open_interest.fillna(0) >= 1000) & c.settle.notna()]
    S = float(e.loc[e.date == "2025-01-29", "lbma_pm_usd"].iloc[0])
    x = g.days_to_first_notice.to_numpy(float)
    b, a = np.polyfit(x, np.log(g.settle.to_numpy(float)), 1, w=np.sqrt(g.open_interest.to_numpy(float)))
    ny0, f90 = math.exp(a), math.exp(a + 90 * b)

    fr = Frame(-60, 320, 2740, 2900)
    body = axes(fr, [(v, str(v)) for v in (0, 90, 180, 270)],
                [(v, dollars(v)) for v in range(2750, 2901, 50)],
                "days to first notice (τ)", "29 Jan 2025, $ per troy ounce")
    ts = np.arange(0, 311, 2.0)
    body.append(f'<path class="line-ny" d="{path(fr, ts, np.exp(a + b * ts))}"/>')
    body.append(f'<line class="roll" x1="{fr.x(90):.1f}" x2="{fr.x(90):.1f}" y1="{fr.y(f90):.1f}" y2="{H - B}"/>')

    top = g.open_interest.max()
    for row in g.itertuples():
        rad = 3 + 6 * math.sqrt(row.open_interest / top)
        cx, cy = fr.x(row.days_to_first_notice), fr.y(row.settle)
        body.append(f'<circle class="dot-contract" cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}"/>')
        body.append(f'<text class="note" x="{cx:.1f}" y="{cy - rad - 5:.1f}" text-anchor="middle">{row.symbol}</text>')

    x0 = fr.x(0)
    body.append(f'<line class="gap" x1="{x0:.1f}" x2="{x0:.1f}" y1="{fr.y(S):.1f}" y2="{fr.y(ny0):.1f}"/>')
    body.append(f'<circle class="dot-ldn" cx="{x0:.1f}" cy="{fr.y(S):.1f}" r="5"/>')
    body.append(f'<circle class="ring-ny" cx="{x0:.1f}" cy="{fr.y(ny0):.1f}" r="5"/>')
    body.append(f'<text class="note ny" x="{x0 - 10:.1f}" y="{fr.y(ny0) + 4:.1f}" text-anchor="end">curve at 0: ${ny0:,.2f}</text>')
    body.append(f'<text class="note strong" x="{x0 + 9:.1f}" y="{fr.y(S) - 2:.1f}">+${ny0 - S:.2f}</text>')
    body.append(f'<text class="note ldn" x="{x0 + 9:.1f}" y="{fr.y(S) + 16:.1f}">London ${S:,.2f}</text>')
    body.append(f'<circle class="dot-ny" cx="{fr.x(90):.1f}" cy="{fr.y(f90):.1f}" r="4.5"/>')
    body.append(f'<text class="note strong" x="{fr.x(90) + 10:.1f}" y="{fr.y(f90) + 17:.1f}">F₉₀ = ${f90:,.2f}</text>')
    return svg("COMEX settlement prices by days to first notice on 29 January 2025, with the fitted curve read at 90 days", body)


CHARTS = (("sawtooth", chart_sawtooth), ("premium", chart_premium), ("curve", chart_curve))


def main():
    html = PAGE.read_text(encoding="utf-8")
    for name, fn in CHARTS:
        pattern = re.compile(rf"(<!-- chart:{name} -->).*?(<!-- /chart:{name} -->)", re.S)
        markup = fn()
        html, n = pattern.subn(lambda m: f"{m.group(1)}\n{markup}\n{m.group(2)}", html)
        if n != 1:
            raise SystemExit(f"expected one chart:{name} marker pair in {PAGE.name}, found {n}")
    with open(PAGE, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"wrote {len(CHARTS)} charts into {PAGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
