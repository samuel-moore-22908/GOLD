# Mechanisms section — next steps

Where the section stands: three figures built and merged, the transfer-cost
threshold estimated rather than drawn, and one substantive claim already
softened by better data. What follows is ordered by what unblocks the most,
not by effort.

**Done and on `main`:** `fig2_dislocation`, `fig3_two_legs`, `fig4_monthly_path`,
with `estimate_kink.py` and `validate_mechanism.py` behind them.

---

## 1. Re-time the COMEX leg to the London auction

**Free, and the single largest improvement available.** The LBMA PM fix prints at
15:00 London; the COMEX settle is 13:30 New York. A 1% intraday move between them
is worth roughly four points annualised — the same order as the signal. That gap
is why Figure 2 needs a ten-session mean to be legible, why 41 of 389 daily
observations fall outside its frame, and why the threshold interval in Figure 3
is [$0.83, $10.25] rather than something publishable.

The fix needs no purchase: Databento already gives full COMEX intraday, and the
LBMA auction price is public. Take the GC price *at the moment of the auction*
instead of at settle.

Unblocks: a tighter threshold, a Figure 2 that can show daily data honestly, and
any claim about the timing of the response within a month.

## 2. Pull CME warehouse stocks properly

**Probably free — check before buying.** `comex_gold_stocks_daily.csv` is built
from Internet Archive snapshots and holds six usable points between January 2025
and January 2026. The original obstacle was scrape access, not licensing; CME
publishes the daily gold stocks report itself.

This is now the missing variable rather than a missing figure. Among months with
a premium above $6/oz the median westward shipment is 68.7 t before April 2025
and 5.8 t after — same signal, twelvefold difference. The obvious explanation is
that registered stock went from 440 t to 752 t and an arbitrage can then be
closed by delivering metal already in New York rather than importing more. Until
the series exists that stays an interpretation in `FIGURE_PLAN.md`, not a finding.

If it holds it is the sharpest evidence in the paper that these were relocation
flows: a real demand shock does not switch itself off when the warehouse fills.

## 3. Get gold lease / forward rates

**A threat to Figure 2's interpretation, not a refinement of it.** `carry_rate`
is currently SOFR plus an assumed 25bp of storage. But gold's own financing rate
is the gold forward rate, and lease rates moved hard during the squeeze. If they
spiked in December–January, some of what the figure calls "dislocation" is
mismeasured carry, and the peak is overstated by an unknown amount.

GOFO was discontinued in 2015, so this means the ICE/LBMA forward curve or
Bloomberg's implied lease rates. Verify tickers on the terminal rather than
trusting a remembered one.

## 4. Extend the event chronology past May 2025

`data/processed/federal_register_events.csv` stops at 21 May 2025. The article
currently cannot source: the July 2025 westward spike (54 t in one month), the
31 July CBP ruling, or whatever resolved it in August. Figure 2 marks the ruling
date; the prose should not assert it caused the July shipments, because those
shipments *precede* it.

Cheap, and it removes the one unsourced causal claim in the section.

## 5. Run the whole exercise on silver

**High return for almost no cost.** HS 7106 — silver — was the third-largest
round trip in the Figure 1 commodity panel, behind gold and pharmaceuticals.
Silver has its own physically-deliverable COMEX contract and its own London
market, so the mechanism predicts it should be there, and COMEX SI is already
inside the Databento subscription. Swiss customs reports silver separately.

A mechanism that fires on a second metal, for the same reason, on the same dates,
is much harder to argue with than one fitted to gold alone — and it partly
replaces the cross-episode evidence that restricting the window took off the
figures.

## 6. Re-pull US trade at HS6 or HS10 with quantities

`us_hs4_universe_monthly.csv` carries a quantity for 0 of 63,628 rows; Census
returns nothing for `GEN_QY1_MO`/`QTY_1_MO` at the country-aggregated HS4 level.
That blocks two things: tonnes on the US side (only Swiss customs reports mass),
and the value-density figure that would answer "why gold and not cars"
quantitatively rather than by assertion.

Lower priority because the Swiss series already carries the tonnage the argument
needs. Worth doing before the paper is finished.

---

## Claims that need changing in the prose

These are corrections to things already written or said, not new work.

**"The return leg is not priced" is too strong.** With the window open to the
present there are nine months with a premium below −$2, not two, and they support
a weak negative slope — the direction `CLAUDE.md`'s "sign is directional"
prediction called for. Write it as *barely* priced and not reliably so: threshold
interval [−$2.69, +$4.65] spanning zero, straight-line R² of 0.01, correlation
−0.11 on 43 months. The asymmetry survives and is now quantified — westward has a
threshold six times its own below-slope, eastward one indistinguishable from
zero — which is a stronger sentence than the flat version was.

**The premium never returns to the pre-election band.** Figure 2 shows it falling
from +3.8 to −2.1 within a fortnight of the exemption and then settling near +0.5
for the rest of 2025. Do not write "arbitrage was restored". The correct sentence
pairs it with Figure 3: half a point is *below the threshold*, so it does not pay
for a shipment, which is why flows stop even though the spread does not close.
The two figures corroborate each other exactly where only one was expected to
speak, and the prose should say so.

**The three-unrelated-causes argument belongs in the text.** Restricting the
window took covid and the 2022 sanctions shock off the figure, and that was the
strongest single piece of evidence here: three unrelated causes, one response.
The full-sample fit gives $2.99 against $3.77 on the restricted window. That
agreement is the answer to a referee asking whether the hinge is an artefact of
one episode, and it now lives only in `FIGURE_PLAN.md` and `validation_output.txt`.

**State the threshold's units question rather than burying it.** Dollar space
beats rate space by 13% of SSR on the full series and loses by 15% on the
restricted one. The two are only distinguishable when the gold price moves a lot.
The reason to prefer dollars is a prior, not a fitted result: freight, insurance
and recasting are charged on weight. Say that plainly; it is a defensible choice
and looks evasive only if left implicit.

---

## What the section still cannot say

Worth keeping visible so it does not get asserted by accident.

- **Why nothing arrived at an $11 premium in September 2025.** The candidate answer is the full warehouse, and it needs item 2 above.
- **What caused the July 2025 spike.** Needs item 4.
- **Whether the threshold is really the physical transfer cost.** $2.99–$3.77 an ounce is $96,000–$121,000 a tonne, or about 0.11% of metal value, which is where air freight, insurance and recasting plausibly sit. That is a sanity check, not a validation. An actual freight and refining quote would turn it into one.
