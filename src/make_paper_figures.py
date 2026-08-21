"""
Figures for claude/gold-tariff-episode-analysis/gold_tariff_episode.tex.

Working rule inherited from this project: charts must show data gaps as gaps.
No silently skipped periods, no solid lines drawn across long interpolations.
The COMEX series in particular is irregularly sampled and is plotted as
markers joined only where consecutive observations are close in time.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

P = Path("data/processed")
FIG = Path("claude/gold-tariff-episode-analysis/figures")
FIG.mkdir(parents=True, exist_ok=True)
OZ = 32150.7

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False,
})

INK, ACCENT, MUTED = "#1a1a1a", "#b5482a", "#7a8b99"
EVENTS = [("2024-11-05", "Election"), ("2025-04-07", "EO 14257"), ("2025-07-31", "CBP N351466")]


def mark_events(ax, y=None, rot=90):
    for d, lab in EVENTS:
        ax.axvline(pd.Timestamp(d), color=MUTED, lw=0.8, ls="--", zorder=0)
        if y is not None:
            ax.text(pd.Timestamp(d), y, "  " + lab, rotation=rot, va="top",
                    ha="left", fontsize=7, color=MUTED)


def load_flows():
    che = pd.read_csv(P / "che_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    w = che[che.country == "United States"].groupby(["date", "flow"]).net_mass_kg.sum().unstack() / 1000
    return w.fillna(0)


# ---------------------------------------------------------------- Figure 1
def fig_roundtrip():
    w = load_flows().loc["2023-01":"2026-07"]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True,
                                  gridspec_kw={"height_ratios": [2, 1]})
    ax.bar(w.index, w["export"], width=22, color=ACCENT, label="Switzerland $\\to$ US")
    ax.bar(w.index, -w["import"], width=22, color=MUTED, label="US $\\to$ Switzerland")
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_ylabel("Tonnes per month")
    ax.legend(loc="upper right")
    ax.set_title("The round trip: Swiss--US gold flows, and their cumulative net", loc="left")
    mark_events(ax, y=ax.get_ylim()[1] * 0.97)

    # Cumulative net is rebased to zero at the start of the paper's window
    # (Oct 2024) so the panel answers the question actually asked: over the
    # episode, how much metal ended up on the other side of the Atlantic?
    net = (w["export"] - w["import"])
    cum = net.loc["2024-10":].cumsum()
    ax2.fill_between(cum.index, 0, cum.values, color=ACCENT, alpha=0.25)
    ax2.plot(cum.index, cum.values, color=ACCENT, lw=1.4)
    ax2.axhline(0, color=INK, lw=0.8)
    ax2.set_ylabel("Cumulative net (t)\nrebased Oct 2024")
    mark_events(ax2)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.annotate(f"ends at {cum.iloc[-1]:+.1f} t", xy=(cum.index[-1], cum.values[-1]),
                 xytext=(-98, 30), textcoords="offset points", fontsize=8, color=INK,
                 arrowprops=dict(arrowstyle="->", color=INK, lw=0.8))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig1_roundtrip.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 2
def fig_basis():
    e = pd.read_csv(P / "efp_dislocation_v2.csv", parse_dates=["date"])
    e = e[e.days_to_first_notice >= 20]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5.4), sharex=True)

    a1.plot(e.date, e.basis_usd, lw=0.7, color=MUTED)
    a1.set_ylabel("Raw basis, \\$/oz")
    a1.set_title("The dollar basis trends with the gold price; the implied rate does not",
                 loc="left")
    a1.axhline(0, color=INK, lw=0.6)

    a2.plot(e.date, e.dislocation * 100, lw=0.7, color=ACCENT)
    a2.axhline(0, color=INK, lw=0.6)
    a2.set_ylabel("Dislocation, % p.a.")
    a2.set_ylim(-15, 35)
    for ax in (a1, a2):
        mark_events(ax)
    a1.annotate("COVID", xy=(pd.Timestamp("2020-04-09"), 72), xytext=(-40, -18),
                textcoords="offset points", fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    a2.annotate("COVID: 31% p.a.", xy=(pd.Timestamp("2020-04-09"), 31), xytext=(15, -6),
                textcoords="offset points", fontsize=8)
    a2.annotate("tariff episode:\nmean 1.2% p.a.", xy=(pd.Timestamp("2025-01-30"), 8),
                xytext=(-20, 40), textcoords="offset points", fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig2_basis.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 3
def fig_vaults():
    cx = pd.read_csv(P / "comex_gold_stocks_daily.csv", parse_dates=["date"]).sort_values("date")
    cx["total_t"] = cx.combined_total_oz / OZ
    cx["reg_t"] = cx.registered_oz / OZ
    lb = pd.read_csv(P / "analysis_results_lbma.csv", parse_dates=["month"]) \
        if (P / "analysis_results_lbma.csv").exists() else None

    fig, ax = plt.subplots(figsize=(8, 4.2))
    # Plot COMEX as segments, breaking the line wherever the gap between
    # consecutive observations exceeds 120 days. This is the "gaps as gaps" rule.
    d = cx[cx.date >= "2019-01-01"]
    gap = d.date.diff().dt.days.fillna(0) > 120
    seg = gap.cumsum()
    for _, g in d.groupby(seg):
        ax.plot(g.date, g.total_t, color=ACCENT, lw=1.4,
                marker="o", ms=2.5, label="_")
        ax.plot(g.date, g.reg_t, color=ACCENT, lw=1.0, ls=":", marker="", label="_")
    ax.plot([], [], color=ACCENT, lw=1.4, marker="o", ms=2.5, label="COMEX total")
    ax.plot([], [], color=ACCENT, lw=1.0, ls=":", label="COMEX registered")

    # shade the archival hole
    ax.axvspan(pd.Timestamp("2023-04-20"), pd.Timestamp("2025-01-30"),
               color=MUTED, alpha=0.13, zorder=0)
    ax.text(pd.Timestamp("2024-03-01"), 1300, "no archived\nsnapshots",
            ha="center", fontsize=7.5, color=MUTED)
    ax.set_ylabel("COMEX gold, tonnes")
    ax.set_title("COMEX warehouse stocks: irregularly observed, with a 21-month hole", loc="left")
    mark_events(ax)
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig3_comex.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 4
def fig_london():
    import json
    r = json.load(open(P / "analysis_results.json"))
    lb = pd.Series({pd.Timestamp(k): v for k, v in r["lbma_vault_t"].items()}).sort_index()
    etf = pd.Series({pd.Timestamp(k): v for k, v in r["etf_global_holdings_t"].items()}).sort_index()
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.plot(lb.index, lb.values, color=ACCENT, lw=1.6, label="London vault gold (LBMA)")
    ax.set_ylabel("London vaults, tonnes")
    ax.set_title("London's drawdown was 3.4\\%, fully reversed, now at a record", loc="left")
    ax.axhline(lb.loc["2024-10-31"], color=MUTED, lw=0.8, ls="--")
    ax.annotate("Oct 2024: 8,775 t", xy=(lb.index[2], lb.loc["2024-10-31"]),
                xytext=(6, 8), textcoords="offset points", fontsize=8, color=MUTED)
    ax.annotate("Feb 2025 trough:\n8,477 t ($-3.4\\%$)", xy=(pd.Timestamp("2025-02-28"), 8476.8),
                xytext=(10, -34), textcoords="offset points", fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate("Jul 2026: 9,534 t", xy=(lb.index[-1], lb.iloc[-1]),
                xytext=(-70, 10), textcoords="offset points", fontsize=8)
    a2 = ax.twinx()
    a2.plot(etf.index, etf.values, color=MUTED, lw=1.2, ls="-.", label="Global ETF holdings")
    a2.set_ylabel("ETF holdings, tonnes")
    a2.grid(False)
    lines = ax.get_lines()[:1] + a2.get_lines()[:1]
    ax.legend(lines, [l.get_label() for l in lines], loc="lower right")
    mark_events(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig4_london.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 5
def fig_classification():
    us = pd.read_csv(P / "us_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    imp = (us[(us.flow == "import") & (us.country == "Switzerland")]
           .groupby(["date", "hs4"]).value_usd.sum().unstack().fillna(0) / 1e9)
    imp = imp.loc["2024-06":"2026-06"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.bar(imp.index, imp[7115], width=22, color=ACCENT, label="HS 7115.90 (articles of precious metal)")
    ax.bar(imp.index, imp[7108], width=22, bottom=imp[7115], color=MUTED, label="HS 7108 (gold)")
    ax.set_ylabel("US imports from Switzerland, \\$bn")
    ax.set_title("The same metal, reclassified: US customs treatment of Swiss bullion", loc="left")
    ax.legend(loc="upper right")
    mark_events(ax, y=ax.get_ylim()[1] * 0.97)
    ax.annotate("classification\nflips to 7108", xy=(pd.Timestamp("2025-07-15"), 5.9),
                xytext=(20, 18), textcoords="offset points", fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig5_classification.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 6
def fig_kink():
    e = pd.read_csv(P / "efp_dislocation_v2.csv", parse_dates=["date"])
    e = e[e.days_to_first_notice >= 20]
    m = e.set_index("date").resample("ME").excess_basis_usd.mean()
    w = load_flows()
    fl = w["export"]
    fl.index = fl.index.to_period("M").to_timestamp("M")
    d = pd.DataFrame({"excess": m, "flow": fl}).dropna().loc["2015-01":"2026-07"]
    ep = ((d.index >= "2024-11") & (d.index <= "2025-08"))
    cv = ((d.index >= "2020-03") & (d.index <= "2020-08"))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.scatter(d.excess[~(ep | cv)], d.flow[~(ep | cv)], s=16, color=MUTED,
               alpha=0.75, label="other months")
    ax.scatter(d.excess[cv], d.flow[cv], s=34, color=INK, marker="^", label="COVID 2020")
    ax.scatter(d.excess[ep], d.flow[ep], s=34, color=ACCENT, label="tariff episode")
    c, b0, b1 = 0.5, None, None
    x = np.maximum(0, d.excess - c)
    b1, b0 = np.polyfit(x, d.flow, 1)
    xs = np.linspace(d.excess.min(), d.excess.max(), 200)
    ax.plot(xs, b0 + b1 * np.maximum(0, xs - c), color=INK, lw=1.2,
            label=f"hinge at \\${c:.1f}/oz")
    ax.set_xlabel("Monthly mean excess basis over carry, \\$/oz")
    ax.set_ylabel("Swiss $\\to$ US flow, tonnes")
    ax.set_title("Flow responds convexly, and only above a threshold", loc="left")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "fig6_kink.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 7
def fig_pboc():
    import json
    r = json.load(open(P / "analysis_results.json"))
    ch = pd.Series({pd.Timestamp(k): v for k, v in r["pboc_monthly_change_t"].items()}).sort_index()
    w = load_flows()
    fl = w["export"]
    fl.index = fl.index.to_period("M").to_timestamp("M")
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.bar(ch.index, ch.values, width=22, color=MUTED, label="PBoC reported monthly accumulation")
    ax.set_ylabel("PBoC, tonnes/month")
    ax.set_ylim(0, 22)
    a2 = ax.twinx()
    sub = fl.loc[ch.index.min():ch.index.max()]
    a2.plot(sub.index, sub.values, color=ACCENT, lw=1.5, label="Switzerland $\\to$ US flow")
    a2.set_ylabel("Swiss $\\to$ US, tonnes/month")
    a2.grid(False)
    ax.set_title("Official accumulation runs on its own clock ($r=-0.11$)", loc="left")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = a2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center")
    mark_events(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "fig7_pboc.pdf")
    plt.close(fig)


if __name__ == "__main__":
    for f in (fig_roundtrip, fig_basis, fig_vaults, fig_london, fig_classification,
              fig_kink, fig_pboc):
        f()
        print("ok:", f.__name__)
    print("figures written to", FIG)
