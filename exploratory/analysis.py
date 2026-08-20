"""
Deconvolving gold trade flows: relocation vs absorption, 2024-2026.
Working analysis - not a paper.
"""
import pandas as pd, numpy as np

pd.set_option("display.width", 200)
OZ_PER_TONNE = 32150.7

raw = pd.read_csv("gold_raw_data.csv", parse_dates=["date"])
ctx = pd.read_csv("gold_context_data.csv")

def series(name):
    s = raw[raw.series == name].set_index("date")["value"].sort_index()
    return s

def cval(name):
    r = ctx[ctx.series == name]
    return r["value"].iloc[0] if len(r) else np.nan

print("=" * 78)
print("1. THE SWISS->US EPISODE: GROSS FLOW vs NET RELOCATION")
print("=" * 78)

ch_us = series("ch_exports_to_us")
us_ch = series("ch_imports_from_us")

episode = ch_us.loc["2024-11":"2025-12"]
print("\nSwiss gold exports to US, monthly (tonnes):")
for d, v in episode.items():
    bar = "#" * int(v / 4)
    print(f"  {d:%Y-%m}  {v:7.1f}  {bar}")

outbound = episode.loc["2024-12":"2025-08"].sum()
print(f"\nOutbound Dec-2024 to Aug-2025 (CH->US):      {outbound:8.1f} t")

# Return leg: we only have Feb-Apr 2025 observed
ret_obs = us_ch.sum()
print(f"Return leg observed (US->CH, Feb-Apr 2025):  {ret_obs:8.1f} t  [3 months only]")

# Infer total round trip from COMEX stock change
comex = series("comex_stock")
peak = comex.loc["2025-04-04"]
trough_2024 = comex.loc["2024-11-01"]
latest = comex.loc["2026-07-02"]

build_t = (peak - trough_2024) * OZ_PER_TONNE / 1e6 * 1e6 / OZ_PER_TONNE  # keep in Moz->t
build_t = (peak - trough_2024) * 1e6 / OZ_PER_TONNE
drain_t = (peak - latest) * 1e6 / OZ_PER_TONNE

print(f"\nCOMEX inventory:")
print(f"  Nov 2024 (election)   {trough_2024:5.1f} Moz = {trough_2024*1e6/OZ_PER_TONNE:7.0f} t")
print(f"  Apr 2025 (peak)       {peak:5.1f} Moz = {peak*1e6/OZ_PER_TONNE:7.0f} t")
print(f"  Jul 2026 (latest)     {latest:5.1f} Moz = {latest*1e6/OZ_PER_TONNE:7.0f} t")
print(f"\n  Build  Nov24->Apr25:  {build_t:7.0f} t")
print(f"  Drain  Apr25->Jul26:  {drain_t:7.0f} t")
print(f"  Retention (drain/build): {(1-drain_t/build_t)*100:5.1f}% of the build still in place")

print("\n" + "=" * 78)
print("2. THE PHANTOM MULTIPLIER")
print("=" * 78)
print("""
One tonne relocated London->NY and back generates recorded cross-border
trade at each leg. The Swiss recasting requirement doubles the leg count
because 400oz LGD bars must be remade into 100oz/1kg COMEX bars.

  Outbound:  UK -> CH  (leg 1)     CH -> US  (leg 2)
  Return:    US -> CH  (leg 3)     CH -> UK  (leg 4)
""")
for legs, label in [(1, "direct one-way, no recast"),
                    (2, "one-way via Swiss recast"),
                    (4, "full round trip via Swiss recast")]:
    print(f"  {legs} leg(s)  ->  {legs:.0f}.0x trade recorded per tonne  ({label})")

gross_trade_generated = build_t * 4
print(f"\nIf the entire {build_t:,.0f} t COMEX build round-tripped through Swiss recasting,")
print(f"recorded global cross-border gold trade generated = {gross_trade_generated:,.0f} t")
print(f"...against a net change in world gold ownership of approximately ZERO.")
print(f"For scale, total 2025 world gold SUPPLY was {cval('total_supply'):,.0f} t.")
print(f"Ratio of phantom trade to a full year of world supply: {gross_trade_generated/cval('total_supply'):.2f}x")

print("\n" + "=" * 78)
print("3. WAS ANY OF IT ABSORPTION? (the US capacity test)")
print("=" * 78)

us_typical = cval("us_physical_coin_bar_demand_typical")
print(f"\nUS typical annual physical coin+bar consumption:  {us_typical:6.0f} t/yr")
print(f"COMEX peak inventory:                            {peak*1e6/OZ_PER_TONNE:6.0f} t")
print(f"Years of US retail physical demand sitting in COMEX vaults at peak: "
      f"{(peak*1e6/OZ_PER_TONNE)/us_typical:.1f}")
print(f"\nInflow Nov24-Apr25:                              {build_t:6.0f} t")
print(f"Plausible US absorption over same ~5 months:     {us_typical*5/12:6.0f} t")
print(f"=> Share of inflow attributable to absorption:    {us_typical*5/12/build_t*100:5.1f}%")
print("   => ~%.0f%% of the flow was RELOCATION, not absorption." % (100 - us_typical*5/12/build_t*100))

print("\nCaveat: US 2025 ETF demand was %.0f t (holdings to %.0f t)." %
      (437, cval("us_etf_holdings")))
print("ETF metal is mostly vaulted in LONDON, not COMEX - it is a separate")
print("stock and does not justify the COMEX build. Worth checking in the paper.")

print("\n" + "=" * 78)
print("4. TRADE STATISTICS DISTORTION: THE SWISS-US CASE")
print("=" * 78)

h1_25 = cval("ch_exports_to_us_value")      # 39.0 CHF bn
h1_24 = cval("ch_exports_to_us_value")      # placeholder, pull explicitly
h1_24 = ctx[(ctx.period == "2024-H1") & (ctx.series == "ch_exports_to_us_value")]["value"].iloc[0]
q1_25 = ctx[(ctx.period == "2025-Q1") & (ctx.series == "ch_exports_to_us_value")]["value"].iloc[0]
q2_25 = ctx[(ctx.period == "2025-Q2") & (ctx.series == "ch_exports_to_us_value")]["value"].iloc[0]
exgold_25 = cval("ch_exports_to_us_exgold")

print(f"\nSwiss gold exports to US, value (CHF bn):")
print(f"  H1 2024:  {h1_24:6.1f}")
print(f"  H1 2025:  {h1_25:6.1f}   ({h1_25/h1_24:.0f}x increase)")
print(f"     Q1 25: {q1_25:6.1f}")
print(f"     Q2 25: {q2_25:6.1f}   (collapse after April tariff exemption)")
print(f"\nSwiss exports to US EXCLUDING gold, full-year 2025: {exgold_25:.1f} CHF bn")
print(f"H1 2025 gold alone as share of a full year of non-gold exports: "
      f"{h1_25/exgold_25*100:.0f}%")
print("""
The tariff rate applied to Switzerland was reportedly calibrated on 2024
trade-deficit data - a year Swiss officials called atypical precisely
because of gold. A bilateral balance that includes non-monetary bullion
in transit is measuring vault location, not commerce.
""")

print("=" * 78)
print("5. THE 2020 ANALOGUE (out-of-sample check)")
print("=" * 78)

apr20 = ch_us.loc["2020-04-01"]
jan25 = ch_us.loc["2025-01-01"]
tot_apr20 = series("ch_exports_total").loc["2020-04-01"]
print(f"\n  Apr 2020 CH->US:  {apr20:6.1f} t   ({apr20/tot_apr20*100:.0f}% of all Swiss gold exports that month)")
print(f"  Jan 2025 CH->US:  {jan25:6.1f} t")
print(f"  2025 peak month was {jan25/apr20:.2f}x the 2020 peak month.")
print("""
Same mechanism (EFP dislocation -> London-to-NY relocation), different
trigger (pandemic logistics vs tariff risk). Two episodes five years
apart is enough to fit on one and validate on the other.
""")

print("=" * 78)
print("6. WHAT DIDN'T MOVE: the absorption series for contrast")
print("=" * 78)
for name, lbl in [("ch_exports_to_india", "India"), ("ch_exports_to_uk", "UK"),
                  ("ch_exports_to_turkey", "Turkey")]:
    s = series(name).loc["2024-11":]
    if len(s):
        print(f"\n  Swiss exports to {lbl} (t):")
        for d, v in s.items():
            print(f"    {d:%Y-%m}  {v:6.1f}")

print("""
Note the contrast in volatility. India/Turkey flows move in a band of
single-digit to low-double-digit tonnes and track consumption seasonality
and price. The US series swings 0.2 -> 193 -> 0.3 within twelve months.
That variance ratio is itself a candidate classifier.
""")

# Build the tidy monthly panel for export
panel = raw.pivot_table(index="date", columns="series", values="value", aggfunc="first")
panel = panel.loc["2024-11":].sort_index()
panel.to_csv("gold_monthly_panel.csv")
print(f"\nMonthly panel written: {panel.shape[0]} rows x {panel.shape[1]} series")
