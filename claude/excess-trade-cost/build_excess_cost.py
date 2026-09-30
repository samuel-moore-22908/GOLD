#!/usr/bin/env python3
"""
What the excess gold trade cost to carry out.

The counterfactual in claude/counterfactual says roughly 645 tonnes crossed the
Atlantic in the five-month episode that would not otherwise have moved, and the
customs data say almost all of it has since come back. This script prices that
round trip.

It keeps two ledgers apart, because they are different economic objects:

  RESOURCES   freight, insurance, recasting, handling, and the financing of
              metal in transit. Real inputs consumed. Gone.
  TRANSFERS   the location premium paid to convert a London position into a
              New York one. Someone paid it and someone received it. It is a
              cost to a desk on the wrong side and zero in aggregate, so it is
              never added to the resource line without saying so.

Reads   claude/counterfactual/counterfactual_monthly.csv   (westbound excess)
        data/processed/bilateral_panel_2015_2026.csv       (the return leg)
        claude/carry-threshold/carry_threshold_daily.csv   (premium, gold price)
Writes  claude/excess-trade-cost/cost_ledger.csv
        claude/excess-trade-cost/excess_cost_monthly.csv
        claude/excess-trade-cost/build_excess_cost_output.txt

Run from anywhere:
    python claude/excess-trade-cost/build_excess_cost.py
"""
from __future__ import annotations

# ============================================================================
# EDIT THIS IF YOU MOVE THE SCRIPT
# ============================================================================
REPO_ROOT = ""        # blank = infer from this file's location
# ============================================================================

# ----------------------------------------------------------------------------
# UNIT COSTS.  Replace any of these with a real quote when one can be had; the
# ledger carries the range through to the headline so it is always visible how
# much of the answer is assumption.
#
# The split matters. Freight is charged by weight, recasting by the bar and
# handling by the ounce, so those three are flat dollars per ounce and do not
# move when the gold price does. Insurance and the financing of metal in
# transit are charged on value, so they are rates, and they nearly doubled over
# this sample because the gold price did.
# ----------------------------------------------------------------------------
FLAT_USD_PER_OZ = {                      #  low   central   high
    "recasting 400 oz bars to kilobars and 100 oz": (0.50, 1.25, 2.00),
    "secure air freight, transatlantic":            (0.30, 0.65, 1.00),
    "handling, assay, vault in and out":            (0.20, 0.35, 0.80),
}
INSURANCE_BP = (0.5, 1.0, 2.0)           # basis points of value, one way
TRANSIT_DAYS = (10, 15, 20)              # door to door, London <-> New York
LEASE_RATE = (0.005, 0.015, 0.030)       # forgone gold lease income, per year

# The only public number in the stack: CME's own depository handling charge.
# It sits inside the handling range above, which is the one sanity check
# available on any of these.
CME_HANDLING_USD_PER_OZ = 0.35

PRE_START = "2015-01-01"     # same fit window as the counterfactual
BREAK = "2024-11-01"
EPISODE_END = "2025-03-31"
OZ_PER_TONNE = 32150.7

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(REPO_ROOT).expanduser().resolve() if REPO_ROOT \
    else Path(__file__).resolve().parents[2]
OUT = ROOT / "claude/excess-trade-cost"

LOG: list[str] = []


def note(text: str = "") -> None:
    print(text, flush=True)
    LOG.append(text)


def heading(text: str) -> None:
    note("")
    note("=" * 78)
    note(text)
    note("=" * 78)


def need(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"missing input: {path}\n"
                         f"run the script in {path.parent.name} first")
    return path


# ---------------------------------------------------------------------------
# The two legs
# ---------------------------------------------------------------------------
def leg(flow: str) -> pd.Series:
    """Tonnes a month between the US and the London-Zurich pair, one direction.

    flow="export" is Swiss and UK exports to the US, the westbound leg.
    flow="import" is their imports from the US, the metal coming back.
    """
    f = pd.read_csv(need(ROOT / "data/processed/bilateral_panel_2015_2026.csv"),
                    parse_dates=["date"])
    out = None
    for rep in ("CHE", "GBR"):
        s = f[(f.reporter_iso3 == rep) & (f.country_iso3 == "USA")
              & (f.flow == flow)]
        g = s.groupby("date").net_mass_kg.sum() / 1000.0
        out = g if out is None else out.add(g, fill_value=np.nan)
    return out.dropna()


def extrapolate(y: pd.Series) -> pd.Series:
    """The counterfactual line: least squares on everything before the break,
    carried forward unchanged. Same method as claude/counterfactual."""
    pre = y[(y.index >= PRE_START) & (y.index < BREAK)]
    slope, intercept = np.polyfit(np.arange(len(pre)), pre.values, 1)
    whole = y[y.index >= PRE_START]
    return pd.Series(slope * np.arange(len(whole)) + intercept, index=whole.index)


def gold_price() -> pd.Series:
    """LBMA PM, monthly mean, USD an ounce."""
    d = pd.read_csv(need(ROOT / "claude/carry-threshold/carry_threshold_daily.csv"),
                    parse_dates=["date"], index_col="date")
    return d.lbma_pm_usd.resample("MS").mean().dropna()


def premium() -> pd.Series:
    """The re-timed location premium, monthly mean, USD an ounce. This is what
    it cost to hold metal in New York rather than London, over and above
    carry - the price of switching a position between the two."""
    d = pd.read_csv(need(ROOT / "claude/carry-threshold/carry_threshold_daily.csv"),
                    parse_dates=["date"], index_col="date")
    return d.spread_usd.resample("MS").mean().dropna()


# ---------------------------------------------------------------------------
def step_tonnage() -> pd.DataFrame:
    heading("STEP 1  How much metal moved that otherwise would not have")
    west, east = leg("export"), leg("import")
    note("   Two legs, both from the exporters' and importers' own customs")
    note("   returns rather than from US figures, which carry no mass:")
    note("")
    note("     westbound   Swiss and UK exports to the United States")
    note("     eastbound   Swiss and UK imports from the United States")
    note("")
    note("   Each gets the same counterfactual the tonnage estimate used: a")
    note("   straight line fitted to every month from January 2015 to October")
    note("   2024, carried forward unchanged. The excess is what came in above")
    note("   that line, and shipping cannot be negative, so a month below the")
    note("   line is charged nothing rather than credited back.")

    d = pd.DataFrame({"west": west, "east": east}).dropna(how="all")
    d["west_cf"] = extrapolate(west)
    d["east_cf"] = extrapolate(east)
    d = d[d.index >= BREAK].copy()
    d["west_excess"] = (d.west - d.west_cf).clip(lower=0)
    d["east_excess"] = (d.east - d.east_cf).clip(lower=0)
    d["price_usd"] = gold_price().reindex(d.index)
    d["premium_usd"] = premium().reindex(d.index)

    ep = d.index <= EPISODE_END
    note("")
    note(f"   {'':22}{'westbound':>12}{'eastbound':>12}{'both legs':>12}")
    note(f"   {'episode, t':22}{d.west_excess[ep].sum():>12,.0f}"
         f"{d.east_excess[ep].sum():>12,.0f}"
         f"{d.west_excess[ep].sum() + d.east_excess[ep].sum():>12,.0f}")
    note(f"   {'whole window, t':22}{d.west_excess.sum():>12,.0f}"
         f"{d.east_excess.sum():>12,.0f}"
         f"{d.west_excess.sum() + d.east_excess.sum():>12,.0f}")
    note("")
    note(f"   The window runs {d.index[0]:%B %Y} to {d.index[-1]:%B %Y}.")
    note("")
    note("   The eastbound excess is not a second shipment of different metal.")
    note("   It is the same metal going home once the exemption of 11 April")
    note("   2025 made the tariff risk go away, and it is charged again because")
    note("   a return flight costs what an outbound one costs. A tonne relocated")
    note("   and then relocated back is two tonne-legs of freight and two")
    note("   recastings: 400 oz bars into kilobars on the way out, kilobars back")
    note("   into 400 oz bars on the way home.")
    return d


def step_unit_costs(d: pd.DataFrame) -> pd.DataFrame:
    heading("STEP 2  What a leg costs, per ounce")
    note("   None of these is a quoted price. No public series for bullion")
    note("   logistics or refining fees exists, and the flow-based threshold in")
    note("   claude/carry-threshold could not identify one either: it put the")
    note("   westward cost at $0.78 an ounce with a 90% interval of [-0.46,")
    note("   +2.43], which contains zero. So the stack below is an assumed")
    note("   range with the sensitivity carried through, and the one number in")
    note(f"   it that is public - CME's ${CME_HANDLING_USD_PER_OZ:.2f} depository handling charge -")
    note("   sits inside the handling row as the only available check.")
    note("")
    note(f"   {'charged per ounce, flat':46}{'low':>8}{'central':>9}{'high':>8}")
    note("   " + "-" * 71)
    flat = np.zeros(3)
    for name, band in FLAT_USD_PER_OZ.items():
        flat = flat + np.array(band)
        note(f"   {name:46}{band[0]:>8.2f}{band[1]:>9.2f}{band[2]:>8.2f}")
    note(f"   {'subtotal, flat':46}{flat[0]:>8.2f}{flat[1]:>9.2f}{flat[2]:>8.2f}")
    note("")

    # Ad valorem lines, at the price actually prevailing in each month.
    p = d.price_usd
    ins = [p * bp / 10_000.0 for bp in INSURANCE_BP]
    fin = [p * r * days / 365.0
           for r, days in zip(LEASE_RATE, TRANSIT_DAYS)]
    note(f"   {'charged on value, so it moved with the gold price':46}"
         f"{'low':>8}{'central':>9}{'high':>8}")
    note("   " + "-" * 71)
    note(f"   {'insurance in transit (0.5 / 1.0 / 2.0 bp)':46}"
         f"{ins[0].mean():>8.2f}{ins[1].mean():>9.2f}{ins[2].mean():>8.2f}")
    note(f"   {'forgone lease income in transit':46}"
         f"{fin[0].mean():>8.2f}{fin[1].mean():>9.2f}{fin[2].mean():>8.2f}")
    note("")
    tot = [flat[i] + ins[i] + fin[i] for i in range(3)]
    note(f"   {'ALL IN, mean over the window':46}"
         f"{tot[0].mean():>8.2f}{tot[1].mean():>9.2f}{tot[2].mean():>8.2f}")
    note("")
    note(f"   The two ad valorem lines rose from ${(ins[1] + fin[1]).iloc[0]:.2f} an ounce in "
         f"{d.index[0]:%B %Y} to ${(ins[1] + fin[1]).iloc[-1]:.2f}")
    note(f"   by {d.index[-1]:%B %Y}, purely because gold went from "
         f"${p.iloc[0]:,.0f} to ${p.iloc[-1]:,.0f}. Holding the")
    note("   unit cost flat in dollars would have understated the later legs.")

    d["legs_t"] = d.west_excess + d.east_excess
    for i, tag in enumerate(("lo", "mid", "hi")):
        d[f"unit_{tag}"] = tot[i]
        d[f"cost_{tag}_usdmn"] = d.legs_t * OZ_PER_TONNE * tot[i] / 1e6
    return d


def step_resources(d: pd.DataFrame) -> dict:
    heading("STEP 3  The resource bill")
    ep = d.index <= EPISODE_END
    def bill(tonnes: pd.Series) -> tuple[float, float, float]:
        oz = tonnes * OZ_PER_TONNE
        return tuple(float((oz * d[f"unit_{t}"]).sum() / 1e6)
                     for t in ("lo", "mid", "hi"))

    west_ep = bill(d.west_excess.where(ep, 0.0))
    west_all = bill(d.west_excess)
    east_all = bill(d.east_excess)
    both = tuple(west_all[i] + east_all[i] for i in range(3))

    note(f"   {'':40}{'low':>11}{'central':>11}{'high':>11}   $ millions")
    note("   " + "-" * 74)
    note(f"   {'westbound, the five-month episode':40}"
         f"{west_ep[0]:>11.1f}{west_ep[1]:>11.1f}{west_ep[2]:>11.1f}")
    note(f"   {'westbound, whole window':40}"
         f"{west_all[0]:>11.1f}{west_all[1]:>11.1f}{west_all[2]:>11.1f}")
    note(f"   {'eastbound, the metal coming back':40}"
         f"{east_all[0]:>11.1f}{east_all[1]:>11.1f}{east_all[2]:>11.1f}")
    note("   " + "-" * 74)
    note(f"   {'BOTH LEGS':40}{both[0]:>11.1f}{both[1]:>11.1f}{both[2]:>11.1f}")
    note("")

    tonnes = float(d.west_excess.sum() + d.east_excess.sum())
    value = float((d.west_excess + d.east_excess).mul(
        d.price_usd * OZ_PER_TONNE).sum())
    note(f"   That is ${both[1] / tonnes * 1e6:,.0f} a tonne at the central assumption, on "
         f"{tonnes:,.0f} tonne-legs")
    note(f"   worth ${value / 1e9:,.0f}bn as they crossed - so "
         f"{100 * both[1] * 1e6 / value:.3f}% of the value moved,")
    note(f"   a range of {100 * both[0] * 1e6 / value:.3f}% to "
         f"{100 * both[2] * 1e6 / value:.3f}%.")
    note("")
    note("   The order of magnitude is the point, not the third decimal. Moving")
    note("   gold is cheap relative to what it is worth, which is exactly why a")
    note("   tariff threat of ten or thirty percent was able to move hundreds of")
    note("   tonnes: the arbitrage only had to clear a few dollars an ounce.")
    return {"west_episode": west_ep, "west_window": west_all,
            "east_window": east_all, "both": both,
            "tonne_legs": tonnes, "value_usd": value}


def step_positions(d: pd.DataFrame) -> dict:
    heading("STEP 4  The cost of switching positions")
    note("   Relocating metal is also a trade: a London unallocated claim is")
    note("   sold and a COMEX warrant is bought. The price of that switch is the")
    note("   location premium - the New York price over London, net of carry -")
    note("   which is the series estimated in claude/spread-series.")
    note("")
    note("   For the arbitrageur this premium is revenue, not cost: it is what")
    note("   paid for the freight in step 3. It is a cost to whoever was on the")
    note("   other side, typically a dealer short COMEX and long London who had")
    note("   to close at a dislocated level. So it is a transfer, and the right")
    note("   way to report it is separately from the resource bill, never added")
    note("   to it.")
    note("")
    ep = d.index <= EPISODE_END
    oz = (d.west_excess + d.east_excess) * OZ_PER_TONNE
    paid = (oz * d.premium_usd).fillna(0.0)

    note(f"   {'month':>10}{'tonne-legs':>12}{'premium $/oz':>15}{'$ millions':>13}")
    note("   " + "-" * 50)
    for m, r in d.iterrows():
        if (r.west_excess + r.east_excess) < 1.0:
            continue
        note(f"   {m:%Y-%m}{r.west_excess + r.east_excess:>14,.0f}"
             f"{r.premium_usd:>15.2f}{paid.loc[m] / 1e6:>13,.0f}")
    note("   " + "-" * 50)
    note(f"   {'episode':>10}{d.legs_t[ep].sum():>12,.0f}"
         f"{'':>15}{paid[ep].sum() / 1e6:>13,.0f}")
    note(f"   {'window':>10}{d.legs_t.sum():>12,.0f}"
         f"{'':>15}{paid.sum() / 1e6:>13,.0f}")
    note("")
    note("   The signs are informative. Westbound in the surge the premium was")
    note("   positive, so New York paid up for metal. On the return legs from")
    note("   April 2025 the premium is often negative, which is the same trade")
    note("   run backwards: London paid up to get the metal home. A negative")
    note("   entry is not a refund, it is a transfer in the other direction.")
    note("")
    note("   What this line does NOT contain: the mark-to-market on hedged short")
    note("   books that were never closed, and the premium paid on metal that")
    note("   did not move at all - which in August 2025, with the duty attached")
    note("   to the delivery bar and the escape route shut, is where the whole")
    note("   shock went. Both need CFTC position data, which is not in this")
    note("   repo, so they are named and not invented.")
    return {"episode_usdmn": float(paid[ep].sum() / 1e6),
            "window_usdmn": float(paid.sum() / 1e6),
            "gross_usdmn": float(paid.abs().sum() / 1e6)}


def main() -> None:
    os.chdir(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    heading("WHAT THE EXCESS GOLD TRADE COST")
    note("   Two ledgers, kept apart: resources consumed, and value transferred.")

    d = step_tonnage()
    d = step_unit_costs(d)
    res = step_resources(d)
    pos = step_positions(d)

    heading("THE ANSWER")
    note(f"   Resources consumed moving the excess metal out and back:")
    note(f"       ${res['both'][1]:,.0f} million central, range "
         f"${res['both'][0]:,.0f}m to ${res['both'][2]:,.0f}m")
    note(f"       on {res['tonne_legs']:,.0f} tonne-legs worth "
         f"${res['value_usd'] / 1e9:,.0f}bn as they crossed")
    note("")
    note(f"   Value transferred switching positions between London and New York:")
    note(f"       ${pos['window_usdmn']:,.0f} million net over the window, "
         f"${pos['gross_usdmn']:,.0f} million gross of sign")
    note("")
    note("   These do not add. The first is destroyed, the second changes hands.")
    note(f"   Against the ${res['value_usd'] / 1e9:,.0f}bn of metal shuttled, the resource bill is")
    note(f"   {100 * res['both'][1] * 1e6 / res['value_usd']:.2f}% - which is the finding, not a rounding")
    note("   error. The episode was expensive in what it did to the statistics")
    note("   and cheap in what it consumed, and those are different questions.")

    ledger = pd.DataFrame([
        ("resources", "westbound, episode", *res["west_episode"]),
        ("resources", "westbound, whole window", *res["west_window"]),
        ("resources", "eastbound, whole window", *res["east_window"]),
        ("resources", "both legs, whole window", *res["both"]),
        ("transfer", "position switch, net", pos["window_usdmn"],
         pos["window_usdmn"], pos["window_usdmn"]),
        ("transfer", "position switch, gross of sign", pos["gross_usdmn"],
         pos["gross_usdmn"], pos["gross_usdmn"]),
    ], columns=["ledger", "item", "low_usdmn", "central_usdmn", "high_usdmn"])
    ledger.to_csv(OUT / "cost_ledger.csv", index=False)
    d.round(4).to_csv(OUT / "excess_cost_monthly.csv", index_label="month")
    (OUT / "build_excess_cost_output.txt").write_text(
        "\n".join(LOG) + "\n", encoding="utf-8")
    note("")
    note(f"   wrote {OUT / 'cost_ledger.csv'}")


if __name__ == "__main__":
    main()
