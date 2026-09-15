"""
Print every number quoted in SPREAD_EXPLAINED.md.

Reads only what is already on disk - data/processed/efp_dislocation_v2.csv and
data/processed/comex_contract_daily.csv - and imports the constant-maturity
implementation from claude/mechanism-figures/validate_mechanism.py rather than
re-implementing it, so the explainer cannot drift from the code it explains.
Writes nothing.

Run from the repo root:
    .venv/Scripts/python.exe claude/spread-explainer/worked_examples.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanism-figures"))
from validate_mechanism import HORIZON, MAX_DAYS, MIN_DAYS, MIN_OI, constant_maturity  # noqa: E402

P = Path("data/processed")
DAY = pd.Timestamp("2025-01-29")       # the worked example
CALM_DAY = pd.Timestamp("2019-06-03")  # a day on which nothing happened
WIDE_DAY = pd.Timestamp("2025-08-08")  # a large premium at a long horizon


def rule(s):
    print(f"\n{'=' * 78}\n{s}\n{'=' * 78}")


def row(df, day):
    return df.loc[df.date == day].iloc[0]


def main():
    pd.set_option("display.width", 200)
    e = pd.read_csv(P / "efp_dislocation_v2.csv", parse_dates=["date"])
    c = pd.read_csv(P / "comex_contract_daily.csv", parse_dates=["date"])

    rule("1  Version 1, front month: the worked example")
    r = row(e, DAY)
    print(r[["active_contract", "comex_settle", "lbma_pm_usd", "days_to_first_notice",
             "short_rate", "carry_rate", "basis_usd", "implied_rate", "dislocation",
             "carry_implied_basis_usd", "excess_basis_usd"]].to_string())
    print(f"F/S - 1 = {r.comex_settle / r.lbma_pm_usd - 1:.3%}")
    for tau in (61, 10):
        print(f"pure carry at {tau:>2} days: ${r.lbma_pm_usd * r.carry_rate * tau / 365:.2f}/oz")

    rule("2  A constant premium, annualised at different horizons")
    w = row(e, WIDE_DAY)
    level = w.excess_basis_usd / w.lbma_pm_usd
    print(f"{WIDE_DAY:%d %b %Y}: excess ${w.excess_basis_usd:.2f} on ${w.lbma_pm_usd:,.2f} "
          f"= {level:.2%} of spot, tau = {w.days_to_first_notice}")
    for tau in (w.days_to_first_notice, 30, 10):
        print(f"  read at {tau:>3} days: {level * 365 / tau:.1%} a year")

    rule("3  Roll timing and what the joins and filters drop")
    switch = e.active_contract != e.active_contract.shift()
    outgoing = e[switch.shift(-1, fill_value=False)]
    incoming = e[switch].iloc[1:]
    print("tau of outgoing contract on its last day: ",
          outgoing.days_to_first_notice.describe()[["count", "50%", "min", "max"]].to_dict())
    print("tau of incoming contract on its first day:",
          incoming.days_to_first_notice.describe()[["count", "50%", "min", "max"]].to_dict())
    print(f"share of days with tau < 20: {(e.days_to_first_notice < 20).mean():.1%}")

    weekdays = pd.bdate_range(e.date.min(), e.date.max())
    missing = pd.DatetimeIndex(sorted(set(weekdays) - set(e.date)))
    print(f"weekdays {len(weekdays)}, rows {len(e)}, dropped by the join {len(missing)}")
    print("most common dropped dates:",
          pd.Series(missing.strftime("%d %b")).value_counts().head(8).to_dict())

    rule("4  Noise is a level, so annualising amplifies it (calm 2019)")
    y = e[e.date.dt.year == 2019]
    for lo, hi in [(7, 19), (20, 39), (40, 69), (70, 130)]:
        b = y[y.days_to_first_notice.between(lo, hi)]
        print(f"tau {lo:>3}-{hi:<3} n={len(b):>3}  sd excess ${b.excess_basis_usd.std():.2f}"
              f"  sd dislocation {b.dislocation.std() * 100:.1f} pp")

    rule("5  Version 2, constant maturity: the same days by hand")
    cm = constant_maturity()
    print("contracts per day in the fit:",
          cm.n_contracts.describe()[["50%", "min", "max"]].to_dict())
    for day in (DAY, CALM_DAY):
        g = c[c.date == day]
        fit = g[g.days_to_first_notice.between(MIN_DAYS, MAX_DAYS)
                & (g.open_interest.fillna(0) >= MIN_OI) & g.settle.notna()]
        print(f"\n{day:%d %b %Y}, contracts in the fit:")
        print(fit[["symbol", "days_to_first_notice", "settle", "open_interest"]].to_string(index=False))
        slope, a = np.polyfit(fit.days_to_first_notice.to_numpy(float),
                              np.log(fit.settle.to_numpy(float)), 1,
                              w=np.sqrt(fit.open_interest.to_numpy(float)))
        r = row(e, day)
        S = r.lbma_pm_usd
        f90 = np.exp(a + slope * HORIZON)
        implied = (f90 / S - 1) * 365 / HORIZON
        disloc = implied - r.carry_rate
        print(f"exp(a) = ${np.exp(a):,.2f}   b = {slope:.4e}/day ({365 * slope:.2%} a year)")
        print(f"F90 = ${f90:,.2f}   F90/S - 1 = {f90 / S - 1:.3%}   implied {implied:.2%}"
              f"   carry {r.carry_rate:.2%}   dislocation {disloc * 100:.2f} pp"
              f"   excess ${disloc * HORIZON / 365 * S:.2f}/oz over {HORIZON} days")
        lvl = (a - np.log(S)) * 365 / HORIZON
        slp = 365 * slope - r.carry_rate
        print(f"split: level ${np.exp(a) - S:.2f} ({a - np.log(S):.2%}) -> {lvl * 100:.2f} pp;"
              f" slope {slp * 100:+.2f} pp; cross-term {(disloc - lvl - slp) * 100:+.2f} pp")
        print(f"constant_maturity() says: disloc_pp {cm.loc[day, 'disloc_pp']:.2f},"
              f" 10-session mean {cm.loc[day, 'disloc_pp_10d']:.2f}")

    rule("6  The two versions over the tariff episode, monthly means, pp a year")
    v1 = (e[e.days_to_first_notice >= 20].set_index("date")
          .dislocation.mul(100).resample("ME").mean())
    v2 = cm.disloc_pp.resample("ME").mean()
    t = pd.DataFrame({"version_1_front_month": v1, "version_2_90_day": v2})
    print(t.loc["2024-11":"2025-04"].round(2).to_string())

    rule("7  Day count")
    print(f"SOFR 4.35% on ACT/360 is {4.35 * 365 / 360:.2f}% on ACT/365")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
