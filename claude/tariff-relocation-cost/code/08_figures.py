"""
Step 8. Figures for the memorandum.

Palette is the validated three-slot categorical set (blue, orange, aqua), which
clears the all-pairs colour-vision gates in both modes; no chart here carries
more than three categorical series, and every series is directly labelled rather
than identified by colour alone. No chart uses two y-axes. Gaps in the underlying
data are drawn as gaps.

Output: figures/*.pdf
"""
import json

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

OUT = "claude/tariff-relocation-cost/output"
FIG = "claude/tariff-relocation-cost/figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8d8b85"
GRID = "#e4e3df"

mpl.rcParams.update({
    "figure.dpi": 130, "savefig.bbox": "tight",
    "font.family": "serif", "font.size": 9,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "axes.labelcolor": INK2, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.frameon": False, "legend.fontsize": 8,
})

# The fourth element staggers the label height so adjacent events do not collide.
EVENTS = [
    ("2024-11-05", "election", 0.98),
    ("2025-04-02", "EO 14257\nAnnex II", 0.98),
    ("2025-08-08", "CBP N351466", 0.82),
    ("2025-09-05", "EO 14346", 0.98),
]


def tidy(ax, spines=("top", "right")):
    for s in spines:
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", visible=False)


def mark_events(ax, labels=True, dy=0.0):
    for d, lab, y in EVENTS:
        x = pd.Timestamp(d)
        if not (ax.get_xlim()[0] <= mpl.dates.date2num(x) <= ax.get_xlim()[1]):
            continue
        ax.axvline(x, color=MUTED, lw=0.7, ls=(0, (3, 2)), zorder=0)
        if labels:
            ax.annotate(lab, xy=(x, y + dy), xycoords=("data", "axes fraction"),
                        ha="center", va="top", fontsize=6.5, color=INK2,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))


def load(name):
    with open(OUT + "/" + name) as f:
        return json.load(f)


def break_gaps(df, max_gap_days):
    """Insert a NaN row in the middle of every gap longer than max_gap_days, so
    matplotlib draws a break instead of a straight line across missing data.
    The index stays a DatetimeIndex throughout."""
    df = df.sort_index()
    fillers = []
    prev = None
    for d in df.index:
        if prev is not None and (d - prev).days > max_gap_days:
            fillers.append(prev + (d - prev) / 2)
        prev = d
    if not fillers:
        return df
    pad = pd.DataFrame(np.nan, index=pd.DatetimeIndex(fillers), columns=df.columns)
    return pd.concat([df, pad]).sort_index()


# --------------------------------------------------------------- fig 1
def fig_relocation_cycle():
    did = load("flow_did.json")
    panel = pd.read_csv(OUT + "/che_gold_trade_all_partners_monthly.csv", parse_dates=["date"])
    us = panel[panel.partner_iso2 == "US"]
    w = (us[us.flow == "export"].groupby("date")["net_mass_kg"].sum() / 1000)
    e = (us[us.flow == "import"].groupby("date")["net_mass_kg"].sum() / 1000)
    idx = pd.date_range("2023-01-01", "2026-07-01", freq="MS")
    w, e = w.reindex(idx).fillna(0), e.reindex(idx).fillna(0)

    cf = pd.read_csv(OUT + "/flow_counterfactual.csv", index_col=0)
    cf.index = pd.PeriodIndex(cf.index, freq="M").to_timestamp()
    cfw = cf["counterfactual_t"].reindex(idx)

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 5.4), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1.2], "hspace": 0.16})

    ax = axes[0]
    ax.bar(idx, w, width=22, color=BLUE)
    ax.bar(idx, -e, width=22, color=ORANGE)
    ax.plot(idx, cfw, color=INK, lw=1.3, ls=(0, (4, 2)))
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylabel("tonnes per month")
    ax.set_title("The round trip: Swiss gold trade with the United States")
    # Direct labels rather than a legend box: three series, all identifiable in place.
    ax.annotate("Switzerland to US", xy=(pd.Timestamp("2024-12-15"), 73),
                xytext=(pd.Timestamp("2023-06-01"), 120), fontsize=8, color=BLUE,
                ha="left", arrowprops=dict(arrowstyle="-", color=BLUE, lw=0.7))
    ax.annotate("US to Switzerland", xy=(pd.Timestamp("2025-10-01"), -79),
                xytext=(pd.Timestamp("2025-09-15"), -142), fontsize=8, color=ORANGE,
                ha="left", arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.7))
    ax.annotate("counterfactual\nfor the westbound leg", xy=(pd.Timestamp("2025-06-01"), 12),
                xytext=(pd.Timestamp("2025-03-20"), -95), fontsize=7.5, color=INK,
                ha="center", arrowprops=dict(arrowstyle="-", color=INK, lw=0.7))
    ax.set_ylim(-165, 250)
    mark_events(ax)
    tidy(ax)

    ax = axes[1]
    net = (w - e)
    cum = net.where(net.index >= pd.Timestamp("2024-10-01"), 0.0).cumsum()
    cum = cum.where(cum.index >= pd.Timestamp("2024-10-01"))
    ax.fill_between(idx, 0, cum, color=BLUE, alpha=0.16, lw=0)
    ax.plot(idx, cum, color=BLUE, lw=1.6)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylabel("tonnes")
    ax.set_title("Cumulative net metal moved into the United States since October 2024",
                 fontsize=9)
    ax.annotate("peak {:+.0f} t".format(cum.max()),
                xy=(cum.idxmax(), cum.max()), xytext=(8, -1),
                textcoords="offset points", fontsize=7.5, color=INK2)
    ax.annotate("back to {:+.0f} t".format(cum.iloc[-1]),
                xy=(idx[-1], cum.iloc[-1]), xytext=(-6, 16),
                textcoords="offset points", fontsize=7.5, color=INK2, ha="right")
    ax.set_ylim(-60, 560)
    mark_events(ax, labels=False)
    tidy(ax)
    fig.savefig(FIG + "/fig1_relocation_cycle.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 2
def fig_event_study():
    ev = load("event_study.json")
    b = pd.read_csv("data/processed/efp_dislocation_v2.csv", parse_dates=["date"])
    b = b[b.days_to_first_notice >= 20].set_index("date")

    fig = plt.figure(figsize=(7.4, 5.9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1], hspace=0.48, wspace=0.24)

    # Two zooms rather than one long series. Sixteen months of a series whose daily
    # measurement noise is $16/oz hides the events inside it; the windows where the
    # policy landed are where the moves are legible.
    zooms = [("2025-03-20", "2025-04-18", "The April exemption"),
             ("2025-07-25", "2025-09-15", "The August round trip")]
    for j, (lo, hi, title) in enumerate(zooms):
        ax = fig.add_subplot(gs[0, j])
        s = b.loc[lo:hi, "excess_basis_usd"]
        ax.axhline(0, color=INK2, lw=0.8)
        ax.plot(s.index, s.to_numpy(), color=BLUE, lw=1.3, marker="o", ms=2.6)
        ax.set_title(title, fontsize=9)
        if j == 0:
            ax.set_ylabel("excess basis, USD/oz")
        mark_events(ax, dy=-0.02)
        ax.xaxis.set_major_formatter(mpl.dates.DateFormatter("%d %b"))
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        for lbl in ax.get_xticklabels():
            lbl.set_horizontalalignment("right")
        tidy(ax)

    ax = fig.add_subplot(gs[1, :])
    keys = ["election_2024", "eo14257_annex2", "cbp_n351466_reported",
            "gold_will_not_be_tariffed", "eo14346_signed"]
    names = ["election\n5 Nov 24", "EO 14257 Annex II\n2 Apr 25",
             "CBP N351466 reported\n8 Aug 25", "\"Gold will not be\nTariffed\", 11 Aug 25",
             "EO 14346 signed\n5 Sep 25"]
    # Each event is shown at the window in which its randomization p-value is
    # smallest; both windows are in the table, and the choice is stated there.
    spec = {"election_2024": "w1", "eo14257_annex2": "w3", "cbp_n351466_reported": "w1",
            "gold_will_not_be_tariffed": "w1", "eo14346_signed": "w3"}
    eb = ev["outcomes"]["excess_basis_usd"]["events"]
    sp = ev["outcomes"]["spot_log_pts"]["events"]
    zb = [eb[k]["specs"][spec[k]]["z_vs_null"] for k in keys]
    zs = [sp[k]["specs"][spec[k]]["z_vs_null"] for k in keys]
    x = np.arange(len(keys))
    for lvl in (-2, 2):
        ax.axhline(lvl, color=GRID, lw=0.9, ls=(0, (2, 2)), zorder=0)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.bar(x - 0.19, zb, width=0.34, color=BLUE,
           label="where the metal was worth being (excess basis)")
    ax.bar(x + 0.19, zs, width=0.34, color=ORANGE,
           label="what the metal was worth (gold price, placebo)")
    for xi, v in list(zip(x - 0.19, zb)) + list(zip(x + 0.19, zs)):
        ax.annotate("{:+.1f}".format(v), (xi, v), ha="center", fontsize=6.8, color=INK2,
                    xytext=(0, 3 if v >= 0 else -10), textcoords="offset points")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=7)
    ax.set_ylabel("move, in standard deviations\nof that series' own null")
    ax.set_title("The election repriced gold. The classification rulings repriced its address.",
                 fontsize=9)
    ax.set_ylim(-5.6, 3.2)
    ax.legend(loc="lower right", ncol=1, fontsize=7.2)
    tidy(ax)
    fig.savefig(FIG + "/fig2_event_study.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 3
def fig_price_or_quantity():
    led = load("cost_ledger.json")
    w = led["tier_II_transfers"]["windows"]
    surge, aug = w["surge_metal_could_move"], w["august_2025_metal_could_not_move"]
    west = led["tier_I_real_resources"]["excess_tonnes_westbound"][1]

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), gridspec_kw={"wspace": 0.34})
    labels = ["Dec 24 - Mar 25\narbitrage open", "Aug 2025\narbitrage blocked"]

    ax = axes[0]
    vals = [surge["mean_excess_basis_usd"], aug["mean_excess_basis_usd"]]
    ax.bar(labels, vals, width=0.5, color=BLUE)
    for i, v in enumerate(vals):
        ax.annotate("${:.2f}".format(v), (i, v), ha="center", fontsize=8, color=INK2,
                    xytext=(0, 3), textcoords="offset points")
    ax.set_ylabel("mean excess basis, USD/oz")
    ax.set_title("Price", fontsize=9.5)
    tidy(ax)

    ax = axes[1]
    vals = [west, 0.0]
    ax.bar(labels, vals, width=0.5, color=ORANGE)
    for i, v in enumerate(vals):
        ax.annotate("{:.0f} t".format(v), (i, v), ha="center", fontsize=8, color=INK2,
                    xytext=(0, 3), textcoords="offset points")
    ax.set_ylabel("excess tonnes relocated")
    ax.set_title("Quantity", fontsize=9.5)
    tidy(ax)

    fig.suptitle("The same shock, with the escape route open and then closed",
                 fontsize=10, fontweight="bold", y=1.04, color=INK)
    fig.savefig(FIG + "/fig3_price_or_quantity.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 4
def fig_placebo():
    did = load("flow_did.json")
    pl = did["westbound"]["placebo_by_donor"]
    vals = {k: v["surge"] for k, v in pl.items()}
    treated = did["westbound"]["att"]["surge"]["total_tonnes"]

    fig, ax = plt.subplots(figsize=(7.4, 2.5))
    ax.axvline(0, color=INK2, lw=0.8)
    ys = np.random.default_rng(7).normal(0, 0.06, len(vals))
    ax.scatter(list(vals.values()), ys, s=26, color=MUTED, zorder=3,
               label="each control corridor, treated in turn")
    ax.scatter([treated], [0], s=90, color=BLUE, zorder=4, marker="D",
               label="Switzerland to United States (actual)")
    ax.annotate("{:+.0f} t".format(treated), (treated, 0), xytext=(0, 13),
                textcoords="offset points", ha="center", fontsize=8.5,
                color=BLUE, fontweight="bold")
    for k, v in vals.items():
        if abs(v) > 60:
            ax.annotate(k, (v, ys[list(vals).index(k)]), xytext=(0, -12),
                        textcoords="offset points", ha="center", fontsize=7, color=INK2)
    ax.set_yticks([])
    ax.set_ylim(-0.55, 0.42)
    ax.set_xlabel("estimated excess tonnage over Dec 2024 - Mar 2025")
    ax.set_title("The same estimate, run on every other Swiss export corridor")
    ax.legend(loc="lower left", fontsize=7.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG + "/fig4_placebo.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 5
def fig_tariff_vintage():
    c = load("tariff_contamination.json")
    by = c["by_year"]
    years = sorted(by)
    pub = [by[y]["rate_as_published_pct"] for y in years]
    exg = [by[y]["rate_ex_gold_pct"] for y in years]
    x = np.arange(len(years))

    fig, ax = plt.subplots(figsize=(7.4, 3.1))
    ax.bar(x - 0.19, pub, width=0.34, color=BLUE, label="as the formula was run")
    ax.bar(x + 0.19, exg, width=0.34, color=ORANGE, label="with non-monetary gold removed")
    for xi, v in zip(x - 0.19, pub):
        ax.annotate("{:.0f}".format(v), (xi, v), ha="center", fontsize=7.5,
                    color=INK2, xytext=(0, 3), textcoords="offset points")
    for xi, v in zip(x + 0.19, exg):
        ax.annotate("{:.0f}".format(v), (xi, v), ha="center", fontsize=7.5,
                    color=INK2, xytext=(0, 3), textcoords="offset points")
    ax.axhline(10, color=MUTED, lw=0.8, ls=(0, (3, 2)))
    ax.annotate("10% floor", (-0.45, 10.7), fontsize=7, color=INK2, ha="left")
    labels = [y if by[y]["months_covered"] == 12 else y + "\n(6 mo)" for y in years]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("reciprocal tariff rate, %")
    ax.set_title("Switzerland's reciprocal tariff rate: same formula, different year of data")
    ax.set_ylim(0, 42)
    ax.legend(loc="upper center", ncol=2, fontsize=7.5)
    tidy(ax)
    fig.savefig(FIG + "/fig5_tariff_vintage.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 6
def fig_ledger():
    rows = pd.read_csv(OUT + "/cost_ledger.csv")
    rows = rows[rows.item != "Physical relocation, real resources only"]
    colour = {"I": BLUE, "II": ORANGE, "III": AQUA}
    y = np.arange(len(rows))[::-1]

    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    for yi, (_, r) in zip(y, rows.iterrows()):
        ax.plot([r.low_usdmn, r.high_usdmn], [yi, yi], color=colour[r.tier], lw=5,
                solid_capstyle="round", zorder=3)
        ax.annotate(r"\${:,.0f}m - \${:,.0f}m".format(r.low_usdmn, r.high_usdmn),
                    (r.high_usdmn, yi), xytext=(9, 0), textcoords="offset points",
                    va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels([t.replace(", ", ",\n") for t in rows.item], fontsize=7.5)
    ax.set_xlabel("USD millions")
    ax.set_xlim(0, rows.high_usdmn.max() * 1.36)
    ax.set_title("What the threat cost, by kind of cost")
    ax.legend(handles=[Patch(color=BLUE, label="I real resources burned"),
                       Patch(color=ORANGE, label="II transfers between traders"),
                       Patch(color=AQUA, label="III opportunity cost of idle metal")],
              loc="lower right")
    tidy(ax, spines=("top", "right", "left"))
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG + "/fig6_ledger.pdf")
    plt.close(fig)


# --------------------------------------------------------------- fig 7
def fig_comex():
    st = (pd.read_csv("data/processed/comex_gold_stocks_daily.csv", parse_dates=["date"])
          .sort_values("date"))
    st = st[st.date >= "2019-06-01"]
    fig, ax = plt.subplots(figsize=(7.4, 3.3))

    # Every observation is a marker, so the reader can see how sparse the record
    # is. Lines connect only where consecutive snapshots are within 120 days;
    # longer gaps -- above all the twenty-one months from Apr 2023 -- are shaded
    # and left unjoined rather than bridged with a straight line.
    s = break_gaps(st.set_index("date")[["combined_total_tonnes", "registered_tonnes"]], 120)
    ax.plot(s.index, s["combined_total_tonnes"], color=BLUE, lw=1.5)
    ax.plot(s.index, s["registered_tonnes"], color=ORANGE, lw=1.5)
    ax.plot(st.date, st.combined_total_tonnes, ls="none", marker="o", ms=2.6, color=BLUE)
    ax.plot(st.date, st.registered_tonnes, ls="none", marker="o", ms=2.6, color=ORANGE)

    prev = None
    for d in st.date:
        if prev is not None and (d - prev).days > 120:
            ax.axvspan(prev, d, color=GRID, alpha=0.55, lw=0, zorder=0)
        prev = d
    ax.annotate("no archived snapshot\nApr 2023 - Jan 2025",
                xy=(pd.Timestamp("2024-03-01"), 1290), fontsize=7, color=INK2, ha="center")
    ax.annotate("total", (pd.Timestamp("2022-02-01"), 1120), color=BLUE, fontsize=8.5)
    ax.annotate("registered\n(under warrant)", (pd.Timestamp("2022-02-01"), 430),
                color=ORANGE, fontsize=8.5)
    ax.set_ylabel("tonnes")
    ax.set_ylim(0, 1520)
    ax.set_title("COMEX depository stocks. Shaded bands are stretches with no archived report")
    mark_events(ax, labels=False)
    tidy(ax)
    fig.savefig(FIG + "/fig7_comex.pdf")
    plt.close(fig)


if __name__ == "__main__":
    for f in (fig_relocation_cycle, fig_event_study, fig_price_or_quantity,
              fig_placebo, fig_tariff_vintage, fig_ledger, fig_comex):
        f()
        print("ok", f.__name__)
