"""
Step 5. What the phantom flow did to the policy instrument.

The reciprocal tariff rates announced on 2 April 2025 were not negotiated. They
were computed from a published formula. USTR's note gives

    delta_tau_i = (m_i - x_i) / (epsilon * phi * m_i)

with the price elasticity of import demand epsilon = 4 and the tariff pass-through
to prices phi = 0.25, so that epsilon * phi = 1 and the expression collapses to
the bilateral goods deficit divided by bilateral goods imports. The announced
"discounted" rate is half of that, floored at 10 percent, using calendar-2024
Census goods data.

That formula is mechanical, so it can be replicated exactly and then re-run on
a counterfactual trade base. This script does three things:

  1. Replicates the announced rate for four partners, as a check that the
     formula and the vintage of data are right.
  2. Re-runs Switzerland's rate with non-monetary gold (HS 7108 and 7115)
     removed from both sides of the bilateral account.
  3. Re-runs Switzerland's rate on 2023, 2025 and 2026 data, to show how much
     of the number is a property of which year's vault movements happened to
     land in the sample.

The economic case for removing gold is the same one the international accounts
already accept for monetary gold, which BPM6 excludes from goods trade because
it is a financial asset transfer rather than a shipment of merchandise. Bullion
moving between an LBMA vault and a COMEX warehouse is the same transaction with
a different owner. Nothing is consumed, no productive capacity changes hands,
and, as the round trip in this episode shows, the metal frequently goes home.

Inputs:  output/us_che_goods_trade_monthly.csv (from 01)
         data/processed/us_gold_trade_hs4_monthly.csv
Output:  output/tariff_contamination.json
"""
import json
import re
import time

import pandas as pd
import requests

OUT = "claude/tariff-relocation-cost/output"
UA = {"User-Agent": "Mozilla/5.0 (compatible; gold-flow-deconvolution research)"}
PAUSE = 2.5

# Census country codes for the trade-balance pages, and the rate each partner
# was assigned in the 2 Apr 2025 announcement.
PARTNERS = {
    "CHE": {"cty": 4419, "name": "Switzerland", "announced_pct": 31},
    "IND": {"cty": 5330, "name": "India", "announced_pct": 26},
    "CHN": {"cty": 5700, "name": "China", "announced_pct": 34},
    "GBR": {"cty": 4120, "name": "United Kingdom", "announced_pct": 10},
}

MONTHS = ("January February March April May June July August September "
          "October November December").split()
ROW = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{4})\s+"
                 r"(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\s+(-?[\d,]+\.\d)\b")


def census_country_trade(cty_code, name):
    url = "https://www.census.gov/foreign-trade/balance/c{:04d}.html".format(cty_code)
    r = requests.get(url, headers=UA, timeout=90)
    r.raise_for_status()
    time.sleep(PAUSE)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    rows = [{
        "date": pd.Timestamp(int(y), MONTHS.index(mo) + 1, 1),
        "us_exports_usdmn": float(e.replace(",", "")),
        "us_imports_usdmn": float(i.replace(",", "")),
        "us_balance_usdmn": float(b.replace(",", "")),
    } for mo, y, e, i, b in ROW.findall(text)]
    d = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
    d["partner"] = name
    return d


def reciprocal_rate(imports, exports, epsilon=4.0, phi=0.25, floor=0.10):
    """USTR's published formula, then the announced halving and 10% floor."""
    if imports <= 0:
        return {"full_pct": None, "announced_pct": None}
    full = (imports - exports) / (epsilon * phi * imports)
    half = full / 2.0
    return {
        "deficit_over_imports": (imports - exports) / imports,
        "full_pct": 100 * full,
        "half_pct": 100 * half,
        "announced_pct": 100 * max(half, floor),
        "hit_floor": half < floor,
    }


def main():
    gold = pd.read_csv("data/processed/us_gold_trade_hs4_monthly.csv", parse_dates=["date"])
    gold_imp = (gold[gold.flow == "import"]
                .groupby([gold.date.dt.year, "country_iso3"])["value_usd"].sum()
                .unstack().fillna(0.0) / 1e6)          # USD millions
    gold_exp = (gold[gold.flow == "export_total"]
                .groupby([gold.date.dt.year, "country_iso3"])["value_usd"].sum()
                .unstack().fillna(0.0) / 1e6)

    results = {"formula": {
        "source": ("USTR, 'Reciprocal Tariff Calculations', 2 Apr 2025: "
                   "delta_tau = (m - x) / (epsilon * phi * m), epsilon = 4, phi = 0.25; "
                   "announced rate = half of that, floored at 10 percent"),
        "trade_data_vintage": "calendar 2024 US Census goods trade, nominal",
        "gold_scope": "HS 7108 (gold, non-monetary) + 7115.90 (articles of precious metal)",
    }, "replication": {}, "switzerland_counterfactual": {}, "by_year": {}}

    panels = {}
    for iso, meta in PARTNERS.items():
        d = census_country_trade(meta["cty"], meta["name"])
        panels[iso] = d
        yr = d[d.date.dt.year == 2024]
        imports, exports = yr.us_imports_usdmn.sum(), yr.us_exports_usdmn.sum()
        calc = reciprocal_rate(imports, exports)
        results["replication"][iso] = {
            "partner": meta["name"],
            "us_imports_2024_usdbn": imports / 1000,
            "us_exports_2024_usdbn": exports / 1000,
            "us_deficit_2024_usdbn": (imports - exports) / 1000,
            "computed_announced_pct": calc["announced_pct"],
            "actually_announced_pct": meta["announced_pct"],
            "gap_pp": calc["announced_pct"] - meta["announced_pct"],
            "gold_share_of_us_imports_2024_pct":
                100 * float(gold_imp.get(iso, pd.Series(dtype=float)).get(2024, 0.0)) / imports,
        }

    # ---- Switzerland with gold removed from both sides, 2024 vintage
    che = panels["CHE"]
    yr = che[che.date.dt.year == 2024]
    imports, exports = yr.us_imports_usdmn.sum(), yr.us_exports_usdmn.sum()
    g_in = float(gold_imp["CHE"].get(2024, 0.0))
    g_out = float(gold_exp["CHE"].get(2024, 0.0))

    actual = reciprocal_rate(imports, exports)
    ex_gold = reciprocal_rate(imports - g_in, exports - g_out)
    results["switzerland_counterfactual"] = {
        "vintage": 2024,
        "as_published": {
            "us_imports_usdbn": imports / 1000, "us_exports_usdbn": exports / 1000,
            "deficit_usdbn": (imports - exports) / 1000, **actual,
        },
        "gold_removed": {
            "gold_imports_usdbn": g_in / 1000, "gold_exports_usdbn": g_out / 1000,
            "us_imports_usdbn": (imports - g_in) / 1000,
            "us_exports_usdbn": (exports - g_out) / 1000,
            "deficit_usdbn": (imports - g_in - exports + g_out) / 1000, **ex_gold,
        },
        "rate_attributable_to_gold_pp": actual["announced_pct"] - ex_gold["announced_pct"],
        "non_gold_import_base_usdbn": (imports - g_in) / 1000,
        "duty_difference_on_non_gold_base_usdbn":
            (actual["announced_pct"] - ex_gold["announced_pct"]) / 100 * (imports - g_in) / 1000,
        "note": ("Sign warning. On the 2024 vintage the gold in the data LOWERED "
                 "Switzerland's computed rate rather than raising it, because the "
                 "corridor is close to balanced in gold -- $14.0bn in, $9.4bn out -- "
                 "while the rest of the relationship is heavily one-sided. Removing "
                 "gold therefore strips more from the export side proportionally "
                 "than from the import side and widens the ratio. This contradicts "
                 "the intuition that the phantom flow inflated the tariff, and it is "
                 "the direction the data actually gives. The duty-difference line is "
                 "arithmetic on statutory rates and the 2024 non-gold import base, "
                 "not a revenue forecast: the reciprocal rates were suspended, "
                 "revised to 39 percent for Switzerland on 7 Aug 2025, and superseded "
                 "by the framework agreement implemented in FR 2025-23316."),
    }

    # ---- how much of the number is a property of the vintage
    for y in (2022, 2023, 2024, 2025, 2026):
        yr = che[che.date.dt.year == y]
        if not len(yr):
            continue
        imports, exports = yr.us_imports_usdmn.sum(), yr.us_exports_usdmn.sum()
        g_in = float(gold_imp["CHE"].get(y, 0.0))
        g_out = float(gold_exp["CHE"].get(y, 0.0))
        a, b = reciprocal_rate(imports, exports), reciprocal_rate(imports - g_in, exports - g_out)
        results["by_year"][str(y)] = {
            "months_covered": int(len(yr)),
            "us_imports_usdbn": imports / 1000,
            "us_exports_usdbn": exports / 1000,
            "us_balance_usdbn": (exports - imports) / 1000,
            "gold_imports_usdbn": g_in / 1000,
            "gold_share_of_imports_pct": 100 * g_in / imports,
            "rate_as_published_pct": a["announced_pct"],
            "rate_ex_gold_pct": b["announced_pct"],
        }

    # ---- vintage sensitivity: the number the formula produces for one country,
    # holding the formula fixed and changing only which year's data goes in.
    by_year = results["by_year"]
    pub = [v["rate_as_published_pct"] for v in by_year.values()]
    exg = [v["rate_ex_gold_pct"] for v in by_year.values()]
    results["vintage_sensitivity"] = {
        "years": sorted(by_year),
        "published_rate_range_pp": [min(pub), max(pub)],
        "published_rate_spread_pp": max(pub) - min(pub),
        "ex_gold_rate_range_pp": [min(exg), max(exg)],
        "ex_gold_rate_spread_pp": max(exg) - min(exg),
        "spread_ratio": (max(pub) - min(pub)) / (max(exg) - min(exg)),
        "reading": ("Holding the formula and the country fixed and varying only the "
                    "year of trade data, the rate the formula produces for "
                    "Switzerland swings across a wide band. Strip non-monetary gold "
                    "out and the same exercise produces a far narrower band. The "
                    "instability is not a property of the Swiss economy; it is a "
                    "property of which direction bullion happened to be moving "
                    "between vaults during the sample year."),
    }

    # ---- gold's footprint in the aggregate US goods deficit
    world = census_country_trade(15, "World")
    w = world.set_index("date")
    gm = (gold[gold.flow == "import"].groupby("date")["value_usd"].sum() / 1e6)
    gx = (gold[gold.flow == "export_total"].groupby("date")["value_usd"].sum() / 1e6)
    comb = pd.DataFrame({"world_balance": w.us_balance_usdmn,
                         "gold_imports": gm, "gold_exports": gx}).dropna(subset=["world_balance"])
    comb = comb.fillna(0.0)
    comb["gold_net_imports"] = comb.gold_imports - comb.gold_exports
    comb["balance_ex_gold"] = comb.world_balance + comb.gold_net_imports

    q = comb.loc["2024-01-01":].resample("QE").sum()
    results["us_goods_deficit"] = {
        "note": ("Gold here is the four-partner total (CHE, GBR, IND, CHN) at HS "
                 "7108+7115, which is most but not all of US gold trade, so these "
                 "shares are a lower bound. World totals are Census, not seasonally "
                 "adjusted."),
        "quarterly_usdbn": {
            str(k.to_period("Q")): {
                "us_goods_balance": v.world_balance / 1000,
                "gold_net_imports": v.gold_net_imports / 1000,
                "balance_excluding_gold": v.balance_ex_gold / 1000,
                "gold_share_of_deficit_pct":
                    (100 * v.gold_net_imports / -v.world_balance) if v.world_balance < 0 else None,
            } for k, v in q.iterrows()
        },
    }
    peak = q.gold_net_imports.idxmax()
    results["us_goods_deficit"]["peak_quarter"] = {
        "quarter": str(peak.to_period("Q")),
        "gold_net_imports_usdbn": q.loc[peak, "gold_net_imports"] / 1000,
        "us_goods_balance_usdbn": q.loc[peak, "world_balance"] / 1000,
        "balance_excluding_gold_usdbn": q.loc[peak, "balance_ex_gold"] / 1000,
        "share_of_deficit_pct": 100 * q.loc[peak, "gold_net_imports"] / -q.loc[peak, "world_balance"],
    }

    comb.to_csv(OUT + "/us_deficit_gold_decomposition.csv")
    with open(OUT + "/tariff_contamination.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    print("FORMULA REPLICATION (2024 Census goods data)\n")
    rep = pd.DataFrame(results["replication"]).T
    print(rep[["partner", "us_imports_2024_usdbn", "us_exports_2024_usdbn",
               "computed_announced_pct", "actually_announced_pct",
               "gold_share_of_us_imports_2024_pct"]].round(2).to_string())

    print("\nSWITZERLAND, GOLD REMOVED FROM BOTH SIDES")
    s = results["switzerland_counterfactual"]
    print("  as published : imports ${:.1f}bn  exports ${:.1f}bn  ->  {:.1f}%".format(
        s["as_published"]["us_imports_usdbn"], s["as_published"]["us_exports_usdbn"],
        s["as_published"]["announced_pct"]))
    print("  ex gold      : imports ${:.1f}bn  exports ${:.1f}bn  ->  {:.1f}%".format(
        s["gold_removed"]["us_imports_usdbn"], s["gold_removed"]["us_exports_usdbn"],
        s["gold_removed"]["announced_pct"]))
    print("  attributable to gold: {:.1f} percentage points".format(
        s["rate_attributable_to_gold_pp"]))

    print("\nSAME FORMULA, DIFFERENT VINTAGE")
    print(pd.DataFrame(results["by_year"]).T[
        ["months_covered", "us_balance_usdbn", "gold_share_of_imports_pct",
         "rate_as_published_pct", "rate_ex_gold_pct"]].round(2).to_string())

    print("\nGOLD IN THE US GOODS DEFICIT")
    print(pd.DataFrame(results["us_goods_deficit"]["quarterly_usdbn"]).T.round(1).to_string())


if __name__ == "__main__":
    main()
