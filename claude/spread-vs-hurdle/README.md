# The spread against the cost it has to clear

```
python claude/spread-vs-hurdle/make_spread_vs_hurdle.py
```

Panel A puts the estimated spread and the composite carry on one axis, in
dollars an ounce at a fixed ninety-day horizon:

```
spread   = S * (exp(p_hat + 90b) - 1)          the fitted curve at 90 days
hurdle   = S * (exp(90b) - 1) + kappa          carry to delivery plus shipping
```

Where the spread is above the hurdle the westward trade pays, and the gap is
filled blue; where it is below the eastward hurdle the reverse trade pays, and
the gap is orange. The grey band between them is the no-trade region. Panel B
is the net metal that then moved.

The two lines track each other closely — which is the point. Almost everything
in the spread is the cost of carrying gold, and the interesting quantity is the
gap, not the level. Since 2022 the hurdle runs to $50 an ounce at ninety days
while the gap that decides anything is a couple of dollars.

## The flow series is netted, and both legs come from Switzerland

Swiss exports to the United States minus Swiss imports from it, HS 7108 and
7115 together. Two choices worth stating.

**Both directions from one reporter.** US Census export figures carry no mass
at all — every `net_mass_kg` is zero — so a net series taking one leg from each
side would be Swiss exports minus nothing. Swiss customs weighs both.

**Both headings.** US classification moved kilo and 100 oz bars between 7108
and 7115 during the episode, so either alone loses part of the flow.

## What netting changes

| | |
|---|---|
| mean net flow | **−6.8 t a month** |
| months net eastward | **108 of 139** |

The default direction is east. Switzerland is the world's refining hub, so
there is a persistent flow of US metal to Swiss refineries that has nothing to
do with the COMEX–London spread, and it dominates the count.

That shows up in how the threshold sorts the months. On the **gross** westward
series the sort is strong — median 1.7 tonnes when the premium never cleared
against 6.6 when it cleared on five days or more. On the **net** series it is
weaker and shifted:

| Months | n | median net |
|---|---:|---:|
| clearing west on 5+ days | 59 | −4.8 t |
| clearing east on 5+ days | 86 | −15.6 t |

Clearing westward does not produce net westward flow at the median; it produces
*less eastward* flow. The two series answer different questions, and the paper
should use them accordingly: **gross westward** is the better dependent variable
for testing whether the arbitrage fires, because it is the leg the mechanism
acts on; **net** is the better measure of what actually accumulates in New York,
because it is what changes the stock.

## The finding that netting makes visible

| | net flow |
|---|---:|
| Dec 2024 – Mar 2025 | **+466.0 t** west over four months |
| Apr – Aug 2025 | **−107.9 t** east over five months |

**Twenty-three per cent of the westward move reversed within five months of the
April 2025 exemption.** The gross series cannot show this: it only shows
westward shipments falling from 110 tonnes in March to 13.6 in April, which is
equally consistent with metal having been absorbed and simply stopping.

Metal that has been absorbed does not come back. A fifth of this did, within
months, as soon as the reason for moving it was withdrawn — which is close to a
direct observation of relocation rather than demand.

## Files

| File | What it is |
|---|---|
| `make_spread_vs_hurdle.py` | the figure and the numbers above |
| `spread_vs_hurdle_monthly.csv` | monthly spread, hurdles, days clearing, net tonnes |
| `spread_vs_hurdle.pdf` / `.png` | the two panels |
