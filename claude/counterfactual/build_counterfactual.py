#!/usr/bin/env python3
"""
How much gold trade was there that would not otherwise have happened?

A back-of-the-envelope counterfactual. Fit a baseline to gold shipments into
the United States before the tariff episode, project it through the episode,
and call the gap excess trade.

The method is deliberately simple and the point of the exercise is to find out
how much the answer depends on that simplicity. It does, and in an informative
way: over the five months of the episode the estimate barely moves across
sixteen baseline specifications, and over the full period since it moves by a
factor of two. The short-window number is the one worth quoting.

    baseline    fitted on months before November 2024
    excess      actual shipments minus the projected baseline
    episode     November 2024 to March 2025

Reads   data/processed/bilateral_panel_2015_2026.csv   (Swiss and UK customs)
        data/processed/us_hs4_universe_monthly.csv     (US trade, for context)
Writes  claude/counterfactual/counterfactual_monthly.csv
        claude/counterfactual/counterfactual.pdf and .png
        claude/counterfactual/build_counterfactual_output.txt

Run from anywhere:
    python claude/counterfactual/build_counterfactual.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

BREAK = "2024-11-01"        # the US election: when tariff risk became priceable
EPISODE_END = "2025-03-31"  # the last month before the April exemption
PRE_START = "2021-01-01"    # headline baseline starts after the covid distortion

import os
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/counterfactual"

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


# --- the series --------------------------------------------------------------

def leg(f: pd.DataFrame, reporter: str, col: str, scale: float) -> pd.Series:
    s = f[(f.reporter_iso3 == reporter) & (f.country_iso3 == "USA")
          & (f.flow == "export")]
    g = s.groupby("date")[col].sum() / scale
    return g[g.index >= "2015-01-01"]


# --- the counterfactual ------------------------------------------------------

def design(index, offset: int, seasonal: bool, trend: bool) -> pd.DataFrame:
    X = pd.DataFrame({"const": 1.0}, index=index)
    if trend:
        X["trend"] = np.arange(offset, offset + len(index))
    if seasonal:
        for m in range(2, 13):
            X[f"m{m}"] = (index.month == m).astype(float)
    return X


def counterfactual(y: pd.Series, pre_start: str, seasonal: bool, trend: bool,
                   logs: bool, drop_2020: bool = False) -> pd.Series:
    """Fit a baseline before the break and project it forward."""
    pre = y[(y.index >= pre_start) & (y.index < BREAK)]
    if drop_2020:
        pre = pre[pre.index.year != 2020]
    post = y[y.index >= BREAK]
    X = design(pre.index, 0, seasonal, trend)
    target = np.log(pre.values) if logs else pre.values
    beta, *_ = np.linalg.lstsq(X.values, target, rcond=None)
    resid = target - X.values @ beta
    Xf = design(post.index, len(pre), seasonal, trend)[X.columns]
    fitted = Xf.values @ beta
    if logs:
        # Duan's smearing: exponentiating a log fit understates the mean, and
        # with a residual standard deviation above half a log point here the
        # correction is not a rounding detail.
        fitted = np.exp(fitted) * np.exp(resid).mean()
    return pd.Series(np.clip(fitted, 0, None), index=post.index)


SPECS = [(pre_label, pre_start, drop20, seas, tr, lg)
         for pre_label, pre_start, drop20 in
         (("2021-24", PRE_START, False), ("2015-24 ex 2020", "2015-01-01", True))
         for seas in (False, True) for tr in (False, True) for lg in (False, True)]


def spec_range(y: pd.Series) -> pd.DataFrame:
    rows = []
    post = y[y.index >= BREAK]
    ep = post.index <= EPISODE_END
    for pre_label, pre_start, drop20, seas, tr, lg in SPECS:
        cf = counterfactual(y, pre_start, seas, tr, lg, drop20)
        rows.append({
            "baseline": pre_label,
            "spec": ("trend" if tr else "mean")
                     + (" + seasonality" if seas else "") + (", log" if lg else ""),
            "cf_total": cf.sum(), "excess_total": (post - cf).sum(),
            "excess_episode": (post[ep] - cf[ep]).sum(),
        })
    return pd.DataFrame(rows)


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv("data/processed/bilateral_panel_2015_2026.csv",
                    parse_dates=["date"])

    che_t, gbr_t = leg(f, "CHE", "net_mass_kg", 1000), leg(f, "GBR", "net_mass_kg", 1000)
    che_v, gbr_v = leg(f, "CHE", "value_usd", 1e9), leg(f, "GBR", "value_usd", 1e9)
    both_t = (che_t + gbr_t).dropna()
    both_v = (che_v + gbr_v).dropna()

    heading("STEP 1  What is being counterfactualled")
    note("   Gold shipped to the United States from the two places it comes from")
    note("   when the arbitrage runs: Switzerland, where London bars are recast")
    note("   into the sizes COMEX accepts, and the United Kingdom directly.")
    note("")
    note("   Both legs are the exporters' own customs figures. US import figures")
    note("   would do for value but carry no mass, so tonnage has to come from")
    note("   the other side.")
    note("")
    note(f"   Switzerland   {len(che_t)} months, {che_t.index.min():%Y-%m} to "
         f"{che_t.index.max():%Y-%m}")
    note(f"   United Kingdom{len(gbr_t):>4} months, {gbr_t.index.min():%Y-%m} to "
         f"{gbr_t.index.max():%Y-%m}")
    note(f"   break at {BREAK[:7]}, the US election, when tariff risk became")
    note(f"   priceable; episode ends {EPISODE_END[:7]}, the last month before")
    note("   the April exemption")

    heading("STEP 2  The baseline is fragile, and that is the finding")
    note("   A single baseline would hide how much the answer depends on it, so")
    note("   sixteen are fitted: two pre-periods, with and without a trend, with")
    note("   and without seasonality, in levels and in logs.")
    note("")
    r = spec_range(both_t)
    note(f"   {'baseline':<18}{'shape':<30}{'excess, full':>14}{'episode':>10}")
    for _, row in r.iterrows():
        note(f"   {row.baseline:<18}{row.spec:<30}{row.excess_total:>14,.0f}"
             f"{row.excess_episode:>10,.0f}")
    note("")
    note(f"   full window   {r.excess_total.min():,.0f} to "
         f"{r.excess_total.max():,.0f} t, a factor of "
         f"{r.excess_total.max()/max(r.excess_total.min(), 1):.1f}")
    note(f"   episode only  {r.excess_episode.min():,.0f} to "
         f"{r.excess_episode.max():,.0f} t, a spread of "
         f"{100*(r.excess_episode.max()/r.excess_episode.min() - 1):.0f}%")
    note("")
    note("   Over five months any sane baseline predicts a small number against")
    note("   an actual one that is very large, so the choice barely matters. Over")
    note("   twenty-one months the baseline accumulates and the trend assumption")
    note("   starts to drive the answer. Quote the episode; treat the longer")
    note("   window as an illustration, not an estimate.")

    heading("STEP 3  The back-of-the-envelope number")
    headline = {}
    for label, y_t, y_v in (("Switzerland", che_t, che_v),
                            ("United Kingdom", gbr_t, gbr_v),
                            ("Both legs", both_t, both_v)):
        cf_t = counterfactual(y_t, PRE_START, True, False, False)
        cf_v = counterfactual(y_v, PRE_START, True, False, False)
        post_t, post_v = y_t[y_t.index >= BREAK], y_v[y_v.index >= BREAK]
        ep = post_t.index <= EPISODE_END
        ex_t, ex_v = (post_t[ep] - cf_t[ep]).sum(), (post_v[ep] - cf_v[ep]).sum()
        headline[label] = (ex_t, ex_v, post_t[ep].sum(), cf_t, post_t)
        note(f"   {label:<16} actual {post_t[ep].sum():6.0f} t   baseline "
             f"{cf_t[ep].sum():5.0f} t   excess {ex_t:6.0f} t   ${ex_v:5.1f}bn")
    ex_t, ex_v = headline["Both legs"][0], headline["Both legs"][1]
    note("")
    note(f"   implied price of the excess ${1e9*ex_v/(ex_t*32150.7):,.0f} an ounce,")
    note("   which is where gold traded over those months - the tonnage and the")
    note("   value are telling the same story rather than two different ones.")

    heading("STEP 4  What that is next to the trade statistics it lands in")
    u = pd.read_csv("data/processed/us_hs4_universe_monthly.csv",
                    parse_dates=["date"])
    tot = u.pivot_table(index="date", columns="flow", values="value_usd",
                        aggfunc="sum") / 1e9
    imports = tot["imports"].loc[BREAK:EPISODE_END].sum()
    exports = tot["exports"].loc[BREAK:EPISODE_END].sum()
    deficit = imports - exports
    note(f"   US goods imports, Nov 2024 - Mar 2025   ${imports:,.0f}bn")
    note(f"   US goods deficit, same months           ${deficit:,.0f}bn")
    note(f"   excess gold                             ${ex_v:,.1f}bn")
    note("")
    note(f"   {100*ex_v/imports:.1f}% of imports and {100*ex_v/deficit:.1f}% of the "
         f"goods deficit over those five months.")
    note("")
    note("   That is the point of the exercise. None of this metal was consumed,")
    note("   imported for use, or in any economic sense bought by America: it was")
    note("   moved between vaults because a tariff might otherwise have applied to")
    note("   it, and a fifth of it went back out within five months. It still")
    note("   enters the trade balance at full value.")

    # --- outputs ----------------------------------------------------------
    cf_t, post_t = headline["Both legs"][3], headline["Both legs"][4]
    monthly = pd.DataFrame({"actual_t": post_t, "counterfactual_t": cf_t})
    monthly["excess_t"] = monthly.actual_t - monthly.counterfactual_t
    monthly["cumulative_excess_t"] = monthly.excess_t.cumsum()
    monthly.index.name = "month"
    monthly.to_csv(OUT / "counterfactual_monthly.csv")
    r.to_csv(OUT / "counterfactual_specifications.csv", index=False)

    figure(both_t, monthly, r, ex_t, ex_v, deficit)
    (OUT / "build_counterfactual_output.txt").write_text("\n".join(LOG) + "\n",
                                                         encoding="utf-8")


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ax.spines:
        ax.spines[side].set_visible(False)
    ax.grid(True, axis="both", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SOFT, labelsize=9, length=0)


def panel_head(ax, title: str, deck: str) -> None:
    ax.set_title(title, color=INK, fontsize=13, loc="left", pad=22)
    ax.text(0.0, 1.035, deck, transform=ax.transAxes, fontsize=9.5,
            color=SOFT, ha="left", va="bottom")


def figure(both_t, monthly, r, ex_t, ex_v, deficit) -> None:
    hist = both_t[both_t.index >= "2021-01-01"]
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11.0, 8.2),
        gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.40})
    fig.patch.set_facecolor(SURFACE)

    fig.text(0.030, 0.972, TAB, fontsize=11, color=RED, ha="left", va="top")
    fig.text(0.030, 0.944,
             f"About {ex_t:,.0f} tonnes of gold crossed that otherwise "
             f"would not have",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.906,
             f"Gold shipped to the United States from Switzerland and the "
             f"United Kingdom, against a baseline fitted before\n"
             f"the November 2024 election. The five-month excess is worth "
             f"${ex_v:.0f}bn, or {100*ex_v/deficit:.0f}% of the US goods "
             f"trade deficit over the same months",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    style(ax1)
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.plot(hist.index, hist.values, color=GREY, linewidth=1.4, zorder=3)
    ax1.plot(monthly.index, monthly.actual_t, color=RED, linewidth=1.8, zorder=5)
    ax1.plot(monthly.index, monthly.counterfactual_t, color=INK, linewidth=1.0,
             linestyle=(0, (4, 3)), zorder=4)
    ax1.fill_between(monthly.index, monthly.counterfactual_t, monthly.actual_t,
                     where=monthly.actual_t > monthly.counterfactual_t,
                     color=RED, alpha=0.20, zorder=2, interpolate=True)
    ax1.axvline(pd.Timestamp(BREAK), color=SOFT, linewidth=0.8,
                linestyle=(0, (2, 2)), zorder=1)
    ax1.set_ylabel("Tonnes a month", color=SOFT, fontsize=10)
    panel_head(ax1, "Shipments, and the baseline they left behind",
               "Switzerland and the United Kingdom to the United States. "
               "Dashed: the projected baseline. Shaded: the excess")
    ax1.text(pd.Timestamp(BREAK) - pd.Timedelta(days=40), ax1.get_ylim()[1] * 0.96,
             "US election", fontsize=9, color=SOFT, ha="right", va="top")

    style(ax2)
    # A dot strip rather than bars: the message is how tightly the sixteen
    # estimates cluster, and overlaid bars hide exactly that.
    rows = [("Episode\nNov 24 - Mar 25", r.excess_episode, GREY),
            ("Full window\nNov 24 - Jul 26", r.excess_total, RED)]
    for i, (label, vals, colour) in enumerate(rows):
        y = len(rows) - 1 - i
        ax2.hlines(y, vals.min(), vals.max(), color=colour, linewidth=1.2,
                   alpha=0.55, zorder=2)
        ax2.scatter(vals, np.full(len(vals), y), s=55, color=colour, alpha=0.55,
                    linewidths=0, zorder=3)
        ax2.scatter([vals.median()], [y], s=90, color=colour, zorder=4,
                    marker="|", linewidths=2.2)
        ax2.text(vals.max() + 18, y, f"{vals.min():,.0f} to {vals.max():,.0f} t"
                 f"   (median {vals.median():,.0f})",
                 fontsize=10, color=INK, ha="left", va="center")
    ax2.set_yticks([1, 0])
    ax2.set_yticklabels([rows[0][0], rows[1][0]], fontsize=10, color=INK)
    ax2.tick_params(axis="y", labelsize=10)
    ax2.set_ylim(-0.7, 1.7)
    ax2.set_xlim(0, max(r.excess_total.max(), r.excess_episode.max()) * 1.32)
    ax2.grid(False, axis="y")
    ax2.set_xlabel("Tonnes of excess trade", color=SOFT, fontsize=10)
    panel_head(ax2, "How much the answer depends on the baseline",
               "Each dot is one of sixteen specifications: two pre-periods, "
               "with and without trend and seasonality, in levels and logs")

    src = ("Baseline is a seasonal monthly mean fitted to January 2021 - October "
           "2024 and projected forward; the dots show all sixteen\n"
           " \n"
           "Source: Swiss Federal Office for Customs and Border Security; "
           "HM Revenue and Customs; US Census Bureau")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.105, right=0.985, top=0.780, bottom=0.140)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"counterfactual.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    note("")
    note(f"   wrote {OUT / 'counterfactual.pdf'}")


if __name__ == "__main__":
    main()
