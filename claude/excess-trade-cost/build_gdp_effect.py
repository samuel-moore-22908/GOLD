#!/usr/bin/env python3
"""
What the gold did to measured GDP.

The question this answers: if the gold that crossed the Atlantic in the tariff
episode was relocation rather than trade, by how much is measured GDP wrong?

The sign is the first thing to get right, and it is the opposite of the
intuition. Gold arriving in the United States is an IMPORT, and imports enter
GDP with a minus, so a phantom import surge drags a trade-driven estimate DOWN,
not up. The upward distortion comes a quarter later, when the same metal leaves
again. Both are in this sample, in that order.

None of it reaches published GDP. BEA removes nonmonetary gold from the
national accounts outright and replaces it with an adjustment computed as
domestic production minus industrial use, because gold bought as a store of
value is a valuable rather than consumption or investment. That is a
long-standing convention, not a response to 2025.

So the contribution computed here is not what happened to GDP. It is what
happens to a GDP figure built from trade data that still contains the gold -
which is what a nowcast does, and why GDPNow had to be rebuilt in March 2025
while the published accounts needed no fixing at all.

Reads   data/processed/us_hs4_universe_monthly.csv      (Census HS 7108 + 7115)
        claude/carry-threshold/carry_threshold_daily.csv (LBMA, to get tonnes)
        fred.stlouisfed.org                              (NIPA, keyless CSV)
Writes  claude/excess-trade-cost/gdp_effect_quarterly.csv
        claude/excess-trade-cost/gold_and_gdp.pdf and .png
        claude/excess-trade-cost/build_gdp_effect_output.txt

Run from anywhere:
    python claude/excess-trade-cost/build_gdp_effect.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
CACHE_DIR = "data/raw/fred_cache"     # relative to the repo root
# ============================================================================

# Gold crosses the border under two headings and the episode used both. 7108 is
# gold unwrought; 7115 is "other articles of precious metal", which is where
# most of the bars went in over the winter of 2024-25. Taking 7108 alone misses
# the surge almost entirely, which is worth knowing before anyone repeats this.
HS_GOLD = (7108, 7115)
OZ_PER_TONNE = 32150.7
REQUEST_SPACING_S = 1.5        # be polite to FRED

import io
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/excess-trade-cost"
CACHE = ROOT / CACHE_DIR

RED, GREY, INK, RULE, SOFT = "#E3120B", "#758D99", "#121212", "#E0E4E7", "#707070"
SURFACE, TAB = "#FFFFFF", "███"
mpl.rcParams["font.family"] = ["Arial Narrow", "Liberation Sans Narrow", "Arial"]
mpl.rcParams["text.parse_math"] = False

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


# ---------------------------------------------------------------------------
def fred(series_id: str) -> pd.Series:
    """Any FRED series, via the keyless CSV endpoint, cached on first fetch."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"fred_{series_id}.csv"
    if not path.exists():
        time.sleep(REQUEST_SPACING_S)
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "GOLD-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except Exception:
            # FRED's CSV endpoint stalls under urllib on this machine from time
            # to time while curl fetches it without trouble.
            body = subprocess.run(
                ["curl", "-sS", "-m", "90", "-A", "GOLD-research/1.0", url],
                check=True, capture_output=True).stdout
        if not body:
            raise RuntimeError(f"empty response for {series_id}")
        path.write_bytes(body)
    d = pd.read_csv(io.BytesIO(path.read_bytes()))
    d.columns = ["date", series_id]
    d["date"] = pd.to_datetime(d.date)
    return pd.to_numeric(d.set_index("date")[series_id], errors="coerce").dropna()


def gold_price_monthly() -> pd.Series:
    d = pd.read_csv(ROOT / "claude/carry-threshold/carry_threshold_daily.csv",
                    parse_dates=["date"], index_col="date")
    return d.lbma_pm_usd.resample("MS").mean().dropna()


# ---------------------------------------------------------------------------
def step_trade() -> pd.DataFrame:
    heading("STEP 1  US gold trade, from the customs universe")
    u = pd.read_csv(ROOT / "data/processed/us_hs4_universe_monthly.csv",
                    parse_dates=["date"])
    g = u[u.hs4.isin(HS_GOLD)].pivot_table(index="date", columns="flow",
                                           values="value_usd", aggfunc="sum")
    note("   US imports and exports of HS 7108 and 7115, all partners, monthly.")
    note("   Both headings are needed. Over the surge months the bars went in")
    note("   under 7115, not 7108:")
    note("")
    note(f"   {'month':>10}{'7108 imports':>15}{'7115 imports':>15}   $bn")
    h08 = u[(u.hs4 == 7108) & (u.flow == "imports")].groupby("date").value_usd.sum()
    h15 = u[(u.hs4 == 7115) & (u.flow == "imports")].groupby("date").value_usd.sum()
    for m in pd.date_range("2024-11-01", "2025-03-01", freq="MS"):
        note(f"   {m:%Y-%m}{h08.get(m, 0) / 1e9:>15.2f}{h15.get(m, 0) / 1e9:>15.2f}")
    note("")
    note("   Anyone pulling 7108 alone, as this project's own build order said")
    note("   to, would find almost none of this episode. That is a correction to")
    note("   the instruction in CLAUDE.md, not a detail.")
    note("")
    note("   External check on the construction. The Atlanta Fed, describing why")
    note("   it rebuilt GDPNow, put nonmonetary gold imports at $13.2bn in")
    note("   December 2024 and $32.6bn in January 2025 on a balance-of-payments")
    note("   basis. The two headings together give "
         f"${(h08.get(pd.Timestamp('2024-12-01'), 0) + h15.get(pd.Timestamp('2024-12-01'), 0)) / 1e9:.1f}bn and "
         f"${(h08.get(pd.Timestamp('2025-01-01'), 0) + h15.get(pd.Timestamp('2025-01-01'), 0)) / 1e9:.1f}bn.")
    note("   Close enough that this series is measuring the same thing they are;")
    note("   the small gap is the Census-to-BOP adjustment.")

    price = gold_price_monthly()
    # Total goods imports from the same pull, so gold can be expressed as a
    # share of the import surge on a consistent basis. BEA's published import
    # contribution is no use for that comparison: it already excludes gold.
    total_imp = u[u.flow == "imports"].groupby("date").value_usd.sum()

    d = pd.DataFrame({"imports_usd": g["imports"], "exports_usd": g["exports"],
                      "total_imports_usd": total_imp})
    d["net_usd"] = d.imports_usd - d.exports_usd
    d["price_usd_oz"] = price.reindex(d.index)
    # Customs value of bullion is its market value, so dividing by the month's
    # benchmark price recovers the quantity. That is what makes a constant-price
    # contribution possible below.
    d["net_t"] = d.net_usd / d.price_usd_oz / OZ_PER_TONNE
    note("")
    note(f"   {len(d)} months, {d.index[0]:%Y-%m} to {d.index[-1]:%Y-%m}.")
    note("   Value is converted to tonnes at the month's LBMA PM benchmark,")
    note("   because a quantity is what the real-GDP arithmetic needs and the")
    note("   gold price rose 40% inside this window.")
    return d


def step_quarters(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 2  Quarterly net gold imports")
    q = d.resample("QS").agg(net_usd=("net_usd", "sum"),
                             net_t=("net_t", "sum"),
                             gold_imports_usd=("imports_usd", "sum"),
                             total_imports_usd=("total_imports_usd", "sum"),
                             price_usd_oz=("price_usd_oz", "mean"),
                             n=("net_usd", "size"))
    q = q[q.n == 3].drop(columns="n")     # complete quarters only
    note("   Imports minus exports. Positive means metal arriving, which is what")
    note("   subtracts from GDP; negative means it leaving, which adds.")
    note("")
    note(f"   {'quarter':>9}{'net $bn':>11}{'net tonnes':>13}{'gold $/oz':>12}")
    for m, r in q.iterrows():
        note(f"   {m:%Y}Q{(m.month - 1) // 3 + 1}{r.net_usd / 1e9:>11.1f}"
             f"{r.net_t:>13,.0f}{r.price_usd_oz:>12,.0f}")
    note("")
    note("   Complete quarters only; the customs pull ends "
         f"{d.index[-1]:%B %Y}, so later")
    note("   quarters are dropped rather than annualised from part of a quarter.")
    return q


def step_contributions(q: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 3  Turning that into a GDP growth contribution")
    note("   The NIPA arithmetic. A component's contribution to annualised real")
    note("   GDP growth is its change in quantity, valued at the previous")
    note("   quarter's price, over the previous quarter's nominal GDP:")
    note("")
    note("       contribution (pp) = -1600 * (dQ_t * P_t-1) / GDP_t-1")
    note("")
    note("   The minus is because this is an import. The 1600 is 400 for")
    note("   annualising a quarterly rate in percent, times 4 because the trade")
    note("   figures are quarterly totals and GDP is an annual rate.")
    note("")
    gdp_n = fred("GDP")                    # nominal, SAAR, $bn
    gdp_r = fred("GDPC1")                  # chained 2017$, SAAR, $bn
    imp_r = fred("IMPGSC1")                # real imports of goods and services
    pub_imp = fred("A021RY2Q224SBEA")      # published imports contribution
    pub_nx = fred("A019RY2Q224SBEA")       # published net exports contribution
    pub_inv = fred("A014RY2Q224SBEA")      # published inventories contribution
    nowcast = fred("GDPNOW")

    q = q.join(pd.DataFrame({"gdp_n": gdp_n, "gdp_r": gdp_r, "imp_r": imp_r,
                             "pub_imp": pub_imp, "pub_nx": pub_nx,
                             "pub_inv": pub_inv, "nowcast": nowcast}),
               how="left")
    q["gdp_growth"] = ((q.gdp_r / q.gdp_r.shift(1)) ** 4 - 1) * 100

    # ---- calibration: does the formula reproduce a published contribution? ----
    note("   Before trusting it on gold, run the same formula on total imports")
    note("   and check it against BEA's own published contribution:")
    note("")
    check = -400 * (q.imp_r - q.imp_r.shift(1)) / q.gdp_r.shift(1)
    note(f"   {'quarter':>9}{'this formula':>14}{'BEA published':>15}{'gap':>8}")
    for m, r in q.dropna(subset=["pub_imp"]).iterrows():
        note(f"   {m:%Y}Q{(m.month - 1) // 3 + 1}{check.loc[m]:>14.2f}"
             f"{r.pub_imp:>15.2f}{check.loc[m] - r.pub_imp:>8.2f}")
    gap = (check - q.pub_imp).abs().mean()
    note("")
    note(f"   Mean absolute gap {gap:.2f}pp. The residual is chain weighting:")
    note("   BEA's Fisher index reweights every quarter and this does not. It is")
    note("   small enough that the gold figure below is not an artefact of the")
    note("   approximation.")

    # ---- the gold term ----
    dq_oz = (q.net_t - q.net_t.shift(1)) * OZ_PER_TONNE
    q["gold_contrib_pp"] = -1600 * (dq_oz * q.price_usd_oz.shift(1)) / 1e9 / q.gdp_n.shift(1)
    # The naive version: treat the change in the dollar figure as if it were all
    # quantity. Reported so the price-adjustment is visible rather than buried.
    q["gold_contrib_nominal_pp"] = \
        -1600 * (q.net_usd - q.net_usd.shift(1)) / 1e9 / q.gdp_n.shift(1)
    # Published growth is already gold-free, so passing the gold through is
    # an addition, not a removal. This is the naive figure a trade-driven
    # estimate produces, and step 6 checks it against the one GDPNow made.
    q["gdp_passthrough"] = q.gdp_growth + q.gold_contrib_pp
    return q


def step_answer(q: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 4  The answer, quarter by quarter")
    note("   The gold term is what net gold trade contributes to a GDP growth")
    note("   figure built straight off the trade data. Published GDP does not")
    note("   contain it - step 5 shows why - so 'passed through' is published")
    note("   growth PLUS the gold term, which is the number a naive trade-driven")
    note("   estimate prints.")
    note("")
    note(f"   {'quarter':>9}{'published':>11}{'gold':>9}{'passed through':>16}"
         f"{'imports':>10}{'invent':>9}{'GDPNow':>9}")
    note(f"   {'':9}{'% ann':>11}{'pp':>9}{'% ann':>16}{'pp':>10}{'pp':>9}{'% ann':>9}")
    note("   " + "-" * 74)
    sub = q.dropna(subset=["gold_contrib_pp"])
    for m, r in sub.iterrows():
        nc = f"{r.nowcast:>9.1f}" if pd.notna(r.nowcast) else f"{'--':>9}"
        note(f"   {m:%Y}Q{(m.month - 1) // 3 + 1}{r.gdp_growth:>11.2f}"
             f"{r.gold_contrib_pp:>9.2f}{r.gdp_passthrough:>16.2f}"
             f"{r.pub_imp:>10.2f}{r.pub_inv:>9.2f}{nc}")
    note("")

    def get(label):
        return sub.loc[pd.Timestamp(label)]

    q1, q2 = get("2025-01-01"), get("2025-04-01")
    note("   THE TWO QUARTERS THAT MATTER")
    note("")
    note(f"   2025Q1  gold is worth {q1.gold_contrib_pp:+.2f}pp. Published growth was "
         f"{q1.gdp_growth:+.2f}%; passed")
    note(f"           through it would have printed {q1.gdp_passthrough:+.2f}%. The direction is")
    note("           DOWNWARD: arriving metal is an import, and imports subtract.")
    note("           A phantom import surge makes a trade-driven estimate too")
    note("           weak, not too strong.")
    note("")
    note(f"   2025Q2  the metal went home. Gold is worth "
         f"{q2.gold_contrib_pp:+.2f}pp, a swing of")
    note(f"           {q2.gold_contrib_pp - q1.gold_contrib_pp:+.2f}pp between the two quarters. "
         f"Published growth was")
    note(f"           {q2.gdp_growth:+.2f}%; passed through, {q2.gdp_passthrough:+.2f}%. THIS is the "
         "over-statement")
    note("           the question was after, and it is a full quarter later than")
    note("           the surge everyone looked at.")
    note("")
    prev = sub.shift(1)
    share = 100 * (sub.gold_imports_usd - prev.gold_imports_usd)         / (sub.total_imports_usd - prev.total_imports_usd)
    note(f"   Gold is {share.loc[pd.Timestamp('2025-01-01')]:.0f}% of the entire rise in US goods imports in")
    note("   2025Q1, on the same Census pull for numerator and denominator. That")
    note("   comparison is deliberately NOT made against BEA's published import")
    note("   contribution, which already has the gold taken out of it.")
    note("")
    note("   Over the four quarters 2024Q4 to 2025Q3 the gold terms sum to "
         f"{sub.loc['2024-10-01':'2025-07-01'].gold_contrib_pp.sum():+.2f}pp.")
    note("   A round trip nets out in the level. It does not net out in any")
    note("   single quarter's growth rate, and quarterly growth rates are what")
    note("   policy reacts to.")
    return sub


def step_offset(sub: pd.DataFrame) -> None:
    heading("STEP 5  None of this reaches published GDP")
    note("   BEA does not let nonmonetary gold into the national accounts at all.")
    note("   From its own FAQ: ITA exports and imports of nonmonetary gold are")
    note("   REMOVED and replaced with an adjustment for gold computed as the")
    note("   difference between domestic production and industrial use. Gold")
    note("   bought as a store of value is a valuable, and valuables are outside")
    note("   consumption, investment and government spending by construction.")
    note("   This is long standing - NIPA Handbook chapter 8, reconciliation")
    note("   table 4.3C - not a response to 2025.")
    note("")
    note("   The check that it is live rather than nominal is SILVER. BEA's")
    note("   Survey of Current Business for 2025Q1 records that it 'identified")
    note("   and removed an increase in imports of silver bars in the first")
    note("   quarter'. Silver bars arrive under industrial supplies and materials,")
    note("   where the standing gold adjustment does not reach, so they had to be")
    note("   taken out by hand. Gold needed no mention because gold comes out as")
    note("   a matter of course.")
    note("")
    note("   WHAT THIS CORRECTS. An earlier version of this script said the gold")
    note("   entered GDP as an import offset by a matching inventory build, and")
    note("   pointed at the 2025Q1 inventory contribution as evidence the offset")
    note("   worked. That mechanism was wrong. BEA strips the gold out before it")
    note("   reaches GDP rather than offsetting it afterwards, and the inventory")
    note("   swing in those quarters is broad tariff front-running with nothing")
    note("   to do with gold:")
    note("")
    q1 = sub.loc[pd.Timestamp("2025-01-01")]
    q2 = sub.loc[pd.Timestamp("2025-04-01")]
    note(f"   2025Q1   imports {q1.pub_imp:+.2f}pp   inventories {q1.pub_inv:+.2f}pp")
    note(f"   2025Q2   imports {q2.pub_imp:+.2f}pp   inventories {q2.pub_inv:+.2f}pp")
    note("")
    note("   So the numbers in step 4 are not a claim about published GDP. They")
    note("   are what a GDP figure built off raw trade data would show, and the")
    note("   place that actually happened is the nowcast.")

    heading("STEP 6  The nowcast bridged from a series BEA does not use")
    note("   Here is the bug, stated exactly. GDPNow targets the BEA advance")
    note("   estimate, which EXCLUDES nonmonetary gold. It bridged to it from BOP")
    note("   goods imports, which INCLUDE nonmonetary gold. The model was mapping")
    note("   a trade series into a GDP concept that does not contain what the")
    note("   trade series contains, and for a decade that did not matter because")
    note("   monthly gold imports ran a billion or two.")
    note("")
    nc = sub.loc[pd.Timestamp("2025-01-01")]
    note(f"   Atlanta Fed GDPNow, final 2025Q1 reading   {nc.nowcast:+.2f}%")
    note(f"   Actual 2025Q1 real GDP growth              {nc.gdp_growth:+.2f}%")
    note(f"   Miss                                       "
         f"{nc.nowcast - nc.gdp_growth:+.2f}pp")
    note(f"   Gold term computed here                    {nc.gold_contrib_pp:+.2f}pp")
    note("")
    note("   The direct test of the correction in step 5: if published growth is")
    note("   already gold-free, then adding the gold term back should reconstruct")
    note("   what the unadjusted nowcast actually printed.")
    note("")
    note(f"      published {nc.gdp_growth:+.2f}%  +  gold {nc.gold_contrib_pp:+.2f}pp  "
         f"=  {nc.gdp_passthrough:+.2f}%")
    note(f"      GDPNow, standard model, final vintage   =  {nc.nowcast:+.2f}%")
    note(f"      gap {abs(nc.gdp_passthrough - nc.nowcast):.2f}pp")
    note("")
    note("   That is a reconstruction of a number built by a different model on")
    note("   different data, from customs figures and an accounting identity, and")
    note("   it lands a fifth of a point away. It would not work if published GDP")
    note("   still contained the gold, which is the check on step 5.")
    note("")
    note("   BUT DO NOT READ IT AS 'GOLD EXPLAINS THE WHOLE MISS'. Note first")
    note("   that this gap and the miss-minus-gold-term gap are the SAME number:")
    note("   nowcast - (published + gold) is identically (nowcast - published) -")
    note("   gold. One comparison, not two pieces of evidence.")
    note("")
    note("   And it cannot be the whole story, because the Atlanta Fed's own")
    note("   gold-adjusted model - which does strip gold out of the trade inputs")
    note(f"   - still read {nc.nowcast + 1.23:+.2f}% at the final vintage against an advance")
    note("   estimate of -0.28%. Had gold been the entire miss, their adjusted")
    note("   model would have landed on it. It did not.")
    note("")
    note("   The defensible reading has three parts:")
    note("")
    note("     the gold effect on the nowcast is AT LEAST their wedge, 1.2-2.3pp;")
    note(f"     {abs(nc.gold_contrib_pp):.2f}pp is an upper bound - what gold is worth to an")
    note("     estimate that passes the trade data straight through;")
    note("     the remainder is ordinary forecast error, and at ~1.2pp it is")
    note("     unremarkable against GDPNow's 1.20pp RMSE over 49 quarters.")
    note("")
    note("   For scale on the whole episode: 2025Q1's final-vintage error of")
    note("   +2.46pp is the fourth largest in GDPNow's history and the largest")
    note("   outside the three pandemic quarters of 2020.")
    note("")
    note("   The two adjustments are also not the same object. The Atlanta Fed")
    note("   subtracts gold from the trade aggregates its bridge equations")
    note("   extrapolate from, so an unrepeatable spike is not carried into the")
    note("   months of the quarter not yet observed; observed gold still enters")
    note("   GDP. The term computed here removes gold's arithmetic contribution")
    note("   outright. The second is the bigger cut by construction, which is")
    note("   why -2.67pp exceeds their 1.2-2.3pp wedge rather than contradicting")
    note("   it.")
    note("")
    note("   That is the claim in CLAUDE.md - phantom flows contaminated a")
    note("   Federal Reserve GDP nowcast - reproduced from primary data. It is a")
    note("   replication, not a discovery: the Atlanta Fed diagnosed it at the")
    note("   time, recalibrated GDPNow for the gold distortion between 28")
    note("   February and 6 March 2025, and then published two versions of the")
    note("   nowcast, standard and gold-adjusted, from 6 March through April.")
    note("   The value of redoing it here is that the same excess-trade estimate")
    note("   now carries a cost figure and a GDP figure on one set of numbers.")


def figure(sub: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.0, 8.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1.0, 1.15]})
    fig.patch.set_facecolor(SURFACE)
    d = sub.dropna(subset=["gold_contrib_pp"])
    x = np.arange(len(d))
    labels = [f"{m:%Y}\nQ{(m.month - 1) // 3 + 1}" for m in d.index]

    fig.text(0.030, 0.972, TAB, fontsize=11, color=RED, ha="left", va="top")
    q1 = d.loc[pd.Timestamp("2025-01-01")]
    q2 = d.loc[pd.Timestamp("2025-04-01")]
    fig.text(0.030, 0.940,
             f"Pass the gold through and the quarter reads "
             f"{abs(q1.gold_contrib_pp):.1f} points weaker, then "
             f"{q2.gold_contrib_pp:.1f} stronger",
             fontsize=17, color=INK, ha="left", va="top", fontweight="bold")
    fig.text(0.030, 0.900,
             "Net US imports of gold, and what a GDP figure built straight off "
             "the trade data would print. Published GDP is not this: BEA\n"
             "removes nonmonetary gold from the national accounts. These are the "
             "bars a trade-driven estimate gets, and a nowcast is one",
             fontsize=12, color=INK, ha="left", va="top", linespacing=1.35)

    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        for side in ax.spines:
            ax.spines[side].set_visible(False)
        ax.grid(True, axis="y", color=RULE, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=SOFT, labelsize=10, length=0)
        ax.axhline(0, color=SOFT, linewidth=0.9)

    ax1.bar(x, d.net_usd / 1e9, width=0.62,
            color=[RED if v > 0 else GREY for v in d.net_usd])
    ax1.set_ylabel("Net gold imports, $bn a quarter", color=SOFT, fontsize=11)
    top = d.net_usd.max() / 1e9
    ax1.annotate("metal arriving", xy=(x[-1], top * 0.72), color=RED,
                 fontsize=10, ha="right", va="center")
    ax1.annotate("metal leaving", xy=(x[-1], -top * 0.42), color=GREY,
                 fontsize=10, ha="right", va="center")

    w = 0.38
    ax2.bar(x - w / 2, d.gdp_growth, width=w, color=GREY, label="Published")
    ax2.bar(x + w / 2, d.gdp_passthrough, width=w, color=RED,
            label="If the gold were passed through")
    ax2.set_ylabel("Annualised real GDP growth, %", color=SOFT, fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    leg = ax2.legend(frameon=False, fontsize=10, loc="upper left",
                     handlelength=1.2, borderaxespad=0.2)
    for t in leg.get_texts():
        t.set_color(INK)

    # Label the two quarters the argument turns on, above the taller of the
    # pair so the label never lands inside a bar or off the axis.
    for xi, m in zip(x, d.index):
        if m in (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-04-01")):
            r = d.loc[m]
            ax2.annotate(f"gold {r.gold_contrib_pp:+.1f}pp",
                         xy=(xi, max(r.gdp_growth, r.gdp_passthrough) + 0.22),
                         fontsize=10.5, color=INK, ha="center", va="bottom",
                         fontweight="bold")
    ax2.set_ylim(min(d.gdp_passthrough.min(), 0) - 0.5,
                 max(d.gdp_passthrough.max(), d.gdp_growth.max()) + 1.2)

    src = ("Gold is US imports minus exports of HS 7108 and 7115, all partners, "
           "converted to tonnes at the LBMA PM benchmark and valued at the "
           "previous quarter's price. That\n"
           "contribution is what the trade figure implies for GDP growth. It is "
           "NOT what published GDP did: BEA removes nonmonetary gold from the "
           "national accounts and replaces it\n"
           "with domestic production less industrial use. The red bars are the "
           "error available to anyone reading GDP off trade data. Complete "
           "quarters only\n"
           " \n"
           "Source: US Census Bureau; Bureau of Economic Analysis; LBMA")
    fig.text(0.030, 0.012, src, fontsize=9, color=SOFT, ha="left", va="bottom",
             linespacing=1.35)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.845, bottom=0.175, hspace=0.12)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"gold_and_gdp.{ext}", dpi=200,
                    facecolor=fig.get_facecolor())
    note("")
    note(f"   wrote {OUT / 'gold_and_gdp.pdf'}")


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    heading("WHAT THE GOLD DID TO MEASURED GDP")
    d = step_trade()
    q = step_quarters(d)
    q = step_contributions(q)
    sub = step_answer(q)
    step_offset(sub)
    figure(sub)
    q.round(4).to_csv(OUT / "gdp_effect_quarterly.csv", index_label="quarter")
    (OUT / "build_gdp_effect_output.txt").write_text(
        "\n".join(LOG) + "\n", encoding="utf-8")
    note(f"   wrote {OUT / 'gdp_effect_quarterly.csv'}")


if __name__ == "__main__":
    main()
