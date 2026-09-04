# What the panel shows

Draft prose for `figures/gold_panel.png`, written for an educated general reader
and ordered the way the article runs: a short chronology, then the figure, then
the mechanism. Every figure quoted is computed by `gold_panel.do` from the same
Census pull the chart is drawn from, except the Swiss tonnages, which come from
Swiss customs via `data/processed/bilateral_panel_2015_2026.csv`, and the
phase-average gold price, from `data/processed/efp_dislocation_v2.csv`.

---

## Before the figure

In November 2024 an American election put a broad programme of import tariffs
back on the table, and nobody could say whether gold would be caught by it. The
question stayed open for five months. It was answered on 2 April 2025, when the
reciprocal-tariff order exempted bullion outright, and reopened briefly at the
end of July, when a customs ruling moved standard kilo and 100-ounce bars into a
dutiable heading before that too was set aside. Almost nothing about the physical
gold market changed across those months. Mines produced, jewellers bought,
central banks accumulated, all at close to their usual rates. What changed was
the answer to a narrow legal question about where metal needed to be sitting —
and on the strength of that question alone, Switzerland shipped 195 tonnes of
gold to the United States in January 2025, against a normal month of five or ten.

**[Figure 1: `gold_panel.png`]**

## Reading it

Both panels put a series' exports on the horizontal axis and its imports on the
vertical, averaged by month within each of three phases, so that anything the
United States buys more of than it sells sits above the diagonal. Almost
everything stays put. The grey clouds barely move between phases, which is what
two years of ordinary trade looks like: cars, computers, crude and the rest keep
their positions. Gold does not. It goes nearly straight up — imports tenfold,
exports flat — and then swings hard right and down. In the five months from
November 2024 to March 2025, American gold imports averaged $19.4bn a month
against $2.0bn a month in the year before, and gold went from the twentieth
largest American import heading to the largest of all, ahead of cars and
computers. Then it reversed: over the eight months from April, exports averaged
$10.9bn a month against $2.5bn, and gold rose from thirteenth largest export
heading to second. The right-hand panel says where it went and where it came
back from. Switzerland was shipping the United States $11.0bn of gold a month at
the peak and taking $6.2bn a month back afterwards; on the Swiss customs
measure, which is in tonnes rather than dollars, 535 tonnes went west between
December and March and 383 came back east over the eight months that followed —
months that include the four largest eastbound shipments in eleven years.

## Why gold, and nothing else on the chart

Gold is the outlier because gold is the only thing on that chart whose trade is
mostly a financial position rather than a purchase. Gold futures in New York are
settled, if the buyer insists, in metal: a seller who does not close out has to
place approved bars in an exchange-licensed vault inside the United States. For
years that obligation cost almost nothing, because bullion could be moved from
London or Zurich to New York for freight and a few days' interest, which is why
the two prices tracked each other so closely and why nobody needed to hold metal
on any particular side of the Atlantic. A tariff would have broken that. Anyone
carrying a short position in New York against metal held abroad suddenly faced a
bill of unknown size to honour it, and the market began paying for metal that was
already inside the customs border — New York futures opened a premium over
London spot far wider than financing costs could explain. That premium is the
price of location, and it is what freight responds to. It is also why the flow
ran through Switzerland: London's 400-ounce bars cannot be delivered against a
New York contract, so most of the metal was routed through Swiss refineries to be
recast into the 100-ounce and kilo bars the exchange accepts. No other heading on
the chart has any of this. A car sitting in Bremerhaven is not fungible with a
car in Baltimore, no exchange promises to accept it, and no premium could pay for
flying it across the ocean and back.

None of it was consumed. The metal sat in vaults a few miles from where the
futures traded, waiting for a legal question to be settled, and when the April
order settled it the reason to be there disappeared. The premium collapsed, and
bullion in New York reverted to being inventory that earns nothing and pays
storage. It went home. The round trip is the substantive point: the same metal
crossed the border twice and was counted at full value each time, while ownership
never changed hands, so anything computed from the gross figures — a bilateral
deficit, or a tariff rate calibrated on one — absorbed the whole of it.

## The data

Both panels are drawn from one source: the US Census Bureau's monthly
merchandise-trade statistics, which are the customs record rather than an
estimate of it — the declared value of goods that actually crossed the border.
The series was pulled at the four-digit HS heading level, monthly, in both
directions, from October 2023 to November 2025; imports are general imports at
customs value, exports are domestic goods and re-exports together. Gold is
headings 7108 and 7115 added together, because American classification practice
has moved investment bars between the two. The left panel aggregates each heading
over all partner countries; the right panel is the same gold series broken out by
partner. The twenty-five months are grouped into three phases of twelve, five and
eight months, and every point is a monthly average within its phase, so that a
long phase cannot look large merely for being long. One caveat: these are values,
not weights, and gold averaged about a fifth dearer during the surge than in the
baseline year and about half again as dear during the reversal, so the tonnage
moved rose by less than the dollars did. Where tonnes are quoted above they come
from Swiss customs, which does report net mass, and which is an independent
statistical authority from the one behind the chart.

---

## Not settled

The July 2025 spike is real and appears in both statistical systems — US gold
imports jumped to $10.7bn that month before falling to $1.5bn in August, and
Swiss customs records 54 tonnes shipped west in July against 2.4 in June. It sits
next to the customs ruling of 31 July, but the shipments precede the ruling's own
date, so something else prompted them and the article should not assert the
ruling as the cause until the event chronology is pulled properly.
`data/processed/federal_register_events.csv` currently stops at 21 May 2025.
