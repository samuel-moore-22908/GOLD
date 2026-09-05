*! Figures 2, 3 and 4 - the mechanism behind the round trip in Figure 1.
*!
*! 2  The price of being on the right side of the border. The constant-maturity
*!    COMEX-London spread in excess of carry: a quantity arbitrage is supposed
*!    to hold at zero, going to four points a year and staying there.
*! 3  The hinge. 139 months of that spread against Swiss shipments to America.
*!    Flat until the premium clears the cost of moving, then a step.
*! 4  The return leg is not priced. The same frame with the flow reversed, and
*!    the monthly path beside it.
*!
*! Styling follows claude/gold-panel/gold_panel.do, which is the source of truth
*! for the palette and the header construction. The locals are repeated rather
*! than included so the folder stands alone; if the house style changes, it
*! changes there first.
*!
*! Reads   claude/mechanism-figures/fig2_dislocation.csv  (build_figure_data.py)
*!         claude/mechanism-figures/fig3_monthly.csv      (build_figure_data.py)
*!         claude/mechanism-figures/kink_estimates.csv    (estimate_kink.py)
*!         claude/mechanism-figures/kink_fit.csv          (estimate_kink.py)
*! Writes  claude/mechanism-figures/figures/fig2_dislocation.pdf and .png
*!         claude/mechanism-figures/figures/fig3_two_legs.pdf and .png
*!         claude/mechanism-figures/figures/fig4_monthly_path.pdf and .png
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           claude\mechanism-figures\mechanism_figures.do ///
*!           --log claude\mechanism-figures\mechanism_figures.log

version 18
clear all
set more off

cd "C:/Users/smoor/GitHub/GOLD"

global PROJ "claude/mechanism-figures"
global OUT  "$PROJ/figures"
cap mkdir "$OUT"

graph set window fontface "Arial Narrow"

* The Economist's published palette. RED carries the tariff episode and the read
* line; BLUE carries the two earlier location shocks, which are the reason the
* hinge is not a story about tariffs.
local RED   "227 18 11"       // #E3120B
local BLUE  "0 107 162"       // #006BA2
local INK   "18 18 18"
local GREY  "117 141 153"     // #758D99
local RULE  "224 228 231"
local SOFT  "112 112 112"

* Shared furniture. Defined once, used by all three figures.
local REGION graphregion(color(white) lcolor(white))                          ///
             plotregion(color(white) lstyle(none) margin(medium))
local GRIDY  grid glcolor("`RULE'") glwidth(vthin) glpattern(solid) notick    ///
             labsize(vsmall) labcolor("`SOFT'") angle(0)
local GRIDX  grid glcolor("`RULE'") glwidth(vthin) glpattern(solid) notick    ///
             labsize(vsmall) labcolor("`SOFT'")
local TAB    title("███", size(vsmall) color("`RED'") position(11)            ///
             justification(left))
local NOTE   size(tiny) color("`SOFT'") position(7) justification(left)
local HEAD   size(medsmall) color("`INK'") position(11) justification(left)

*==============================================================================
* Figure 2 - the price of location
*==============================================================================
import delimited using "$PROJ/fig2_dislocation.csv", varnames(1) clear
rename date datestr
gen int d = date(datestr, "YMD")
format d %tdMon_CCYY
sort d

* Quarter starts, built rather than hardcoded so the window can move.
local TICKS ""
foreach y in 2024 2025 2026 {
    foreach mth in 1 4 7 10 {
        local v = mdy(`mth', 1, `y')
        qui su d, meanonly
        if `v' >= r(min) & `v' <= r(max) local TICKS "`TICKS' `v'"
    }
}
local EXEMPT = mdy(4, 2, 2025)
local RULING = mdy(7, 31, 2025)

qui su disloc_pp_10d, meanonly
di as txt "figure 2: peak of smoothed series " as res %5.2f r(max)

* The daily series goes in as dots, not a line, and clipped to the frame.
*
* A line was tried first and is wrong twice over. yscale(range()) only ever
* WIDENS an axis, so it cannot clip: the frame stretched to the daily minimum
* near -6 and left two thirds of the panel empty. And a line asserts continuity
* between consecutive settlements that the data does not have - the 3-hour gap
* between the London fix and the New York settle makes each day's figure an
* independent draw with about four points of noise in it. Dots say that; a line
* denies it.
local LOFR = -2.6
local HIFR =  4.6
gen double daily_in = disloc_pp if inrange(disloc_pp, `LOFR', `HIFR')
qui count if !missing(disloc_pp) & missing(daily_in)
local OFF = r(N)
qui count if !missing(disloc_pp)
local ALL = r(N)
di as txt "figure 2: " as res `OFF' as txt " of " as res `ALL' ///
    as txt " daily values fall outside the frame"

twoway ///
  (rarea band_hi band_lo d, color("`GREY'%16") lwidth(none)) ///
  (scatter daily_in d, msymbol(o) msize(vtiny) mcolor("`GREY'%55")) ///
  (line disloc_pp_10d d, lcolor("`RED'") lwidth(medthick)) ///
  , ///
  yline(0, lcolor("`INK'%55") lwidth(thin)) ///
  xline(`EXEMPT' `RULING', lcolor("`INK'%40") lwidth(thin) lpattern(shortdash)) ///
  ylabel(-2(1)4, `GRIDY') ///
  xlabel(`TICKS', format(%tdMon_CCYY) `GRIDX') ///
  xscale(lcolor(none)) ///
  yscale(range(`LOFR' `HIFR') lcolor(none)) ///
  ytitle("Percentage points a year", size(vsmall) color("`SOFT'") margin(r=2)) ///
  xtitle("") ///
  text(4.30 `=mdy(6,20,2024)' "10-day mean", place(e) size(vsmall) ///
      color("`RED'") justification(left)) ///
  text(3.75 `=mdy(6,20,2024)' "daily", place(e) size(vsmall) ///
      color("`GREY'") justification(left)) ///
  text(-2.25 `=mdy(6,20,2024)' "shaded: ±1 s.d. of the calm window," ///
      "Jun-Nov 2024, when arbitrage held", place(e) size(vsmall) ///
      color("`SOFT'") justification(left)) ///
  text(4.05 `=`EXEMPT'+6' "2 Apr 2025" "gold exempted", place(e) ///
      size(vsmall) color("`INK'") justification(left)) ///
  text(4.05 `=`RULING'+6' "31 Jul 2025" "customs ruling", place(e) ///
      size(vsmall) color("`INK'") justification(left)) ///
  `REGION' legend(off) ///
  `TAB' ///
  subtitle("{bf:The price of being on the right side of the border}" ///
      "COMEX gold futures over London spot, 90-day constant maturity," ///
      "in excess of financing and storage. Arbitrage should hold this at zero", ///
      `HEAD') ///
  note("Constant maturity, not the front month: the raw spread carries the roll" ///
      "sawtooth, and the front-month annualised rate divides by days to delivery," ///
      "which sends it to 42% a fortnight before notice. Both are calendar artefacts." ///
      "Daily dots are clipped to the frame: `OFF' of `ALL' sessions fall outside it." ///
      "The New York settlement is struck three hours after the London fix, so a 1%" ///
      "move in between is worth four points annualised - which is why the daily" ///
      "figure is plotted as scattered points and read through a ten-session mean." ///
      "Note also that the premium fell hard at the exemption but never returned to" ///
      "the pre-election band - it settled near half a point for the rest of 2025." ///
      " " ///
      "Sources: CME settlements via Databento; LBMA PM fix; FRED SOFR", `NOTE') ///
  ysize(5.6) xsize(9.2) name(f2, replace)

graph export "$OUT/fig2_dislocation.pdf", replace
graph export "$OUT/fig2_dislocation.png", replace width(2400)
di as txt "wrote $OUT/fig2_dislocation.png"

*==============================================================================
* Figure 3 - the two legs side by side, on the same axes
*==============================================================================
* Estimated on January 2023 to November 2025 only. 2020 and the March 2022
* sanctions shock are location dislocations of a different kind - grounded
* aircraft and shut refineries in one, a payments rupture in the other - and
* folding them into an exercise about a tariff threat widens the scope of the
* claim beyond what the paper is arguing. It costs precision rather than the
* result: the full 2015-2026 series puts the threshold at $2.99 and this window
* puts it at $3.02.
import delimited using "$PROJ/kink_estimates.csv", varnames(1) clear
local G    = g[1]
local GLO  = g_lo[1]
local GHI  = g_hi[1]
local BABV = b_above[1]
di as txt "kink: " as res %5.2f `G' as txt " dollars/oz  90% CI [" ///
    as res %5.2f `GLO' as txt ", " as res %5.2f `GHI' as txt "]"

tempfile hinge
import delimited using "$PROJ/kink_fit.csv", varnames(1) clear
gen byte ishinge = 1
save `hinge'

import delimited using "$PROJ/fig3_monthly.csv", varnames(1) stringcols(1) clear
gen int mdate = monthly(ym, "YM")
format mdate %tmMon_CCYY
tempfile monthly
save `monthly'

keep if on_scatter == 1 & ym >= "2023-01" & ym <= "2025-11"
gen byte grp = episode == 1
append using `hinge'
replace ishinge = 0 if missing(ishinge)

gen byte mlpos = 3
replace mlpos = 9  if inlist(ym, "2025-01", "2025-10")
replace mlpos = 12 if inlist(ym, "2025-04")

gen str8 calloutE = cond(inlist(ym, "2025-10", "2025-04", "2025-09"), callout, "")

* The threshold's bootstrap interval as a vertical strip. rarea across two
* observations is the way to get one: Stata has no vertical-band primitive and
* -xline- cannot carry a width.
gen double bx = .
gen double btop = .
gen double bbot = .
replace bx = `GLO' in 1
replace bx = `GHI' in 2
replace btop = 210 in 1/2
replace bbot = 0   in 1/2

local SCAT  msymbol(O) msize(medsmall)
local MLAB  mlabsize(vsmall) mlabgap(1.6)
* Dollars an ounce, not points a year: freight, insurance and recasting are
* charged on weight, so a physical transfer cost is a dollar figure. See the
* caution in estimate_kink.py - on a window this short the data cannot settle
* the choice, and the reasoning is a prior rather than a fitted result.
local XAX   xscale(range(-9 21) lcolor(none))                                 ///
            xlabel(-5 "-5" 0 "0" 5 "5" 10 "10" 15 "15" 20 "20", `GRIDX')      ///
            xtitle("COMEX premium over London, in excess of carry," ///
                " dollars an ounce over 90 days", ///
                size(vsmall) color("`SOFT'") margin(t=2))
local YAX   yscale(range(0 210) lcolor(none)) ylabel(0(50)200, `GRIDY')
local BAND  (rarea btop bbot bx, color("`INK'%5") lwidth(none))
local GLINE xline(`G', lcolor("`INK'%55") lwidth(thin) lpattern(shortdash))

*------------------------------------------------------- westbound: a threshold
twoway ///
  `BAND' ///
  (scatter che_to_us_t excess_usd if ishinge == 0 & !grp, ///
      `SCAT' mcolor("`GREY'%60")) ///
  (scatter che_to_us_t excess_usd if ishinge == 0 & grp, ///
      `SCAT' mcolor("`RED'") ///
      mlabel(callout) `MLAB' mlabcolor("`INK'") mlabvposition(mlpos)) ///
  (line yhat x if ishinge == 1, ///
      lcolor("`INK'%80") lwidth(medthick) lpattern(solid)) ///
  , ///
  `XAX' `YAX' `GLINE' ///
  ytitle("Tonnes per month", size(vsmall) color("`SOFT'") margin(r=2)) ///
  text(186 `=`G'+0.7' "estimated threshold, {c $|}3.02 an ounce" ///
      "shaded: 90% interval, {c $|}0.77 to {c $|}10.82", ///
      place(e) size(vsmall) color("`INK'%80") justification(left)) ///
  text(74 20.5 "above it, 8.3 tonnes" "a month per extra dollar", ///
      place(w) size(vsmall) color("`INK'%80") justification(right)) ///
  `REGION' legend(off) ///
  title("Westward: Switzerland to New York", size(small) color("`INK'") ///
      position(11) justification(left)) ///
  subtitle("Arbitrage. Nothing moves below the cost of moving", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(f3a, replace) nodraw

*----------------------------------------------------- eastbound: no threshold
* Same axes, same scale, same threshold strip, and deliberately no fitted line.
* A kink fitted to this leg returns g = -1.98 with a steep negative slope below
* it, and that slope is carried by the only two months in the window with a
* premium under -$2. Two observations are not a threshold; drawing one would
* invent the structure this panel exists to show is absent.
twoway ///
  `BAND' ///
  (scatter us_to_che_t excess_usd if ishinge == 0 & !grp, ///
      `SCAT' mcolor("`GREY'%60")) ///
  (scatter us_to_che_t excess_usd if ishinge == 0 & grp, ///
      `SCAT' mcolor("`BLUE'") ///
      mlabel(calloutE) `MLAB' mlabcolor("`INK'") mlabposition(12)) ///
  , ///
  `XAX' `YAX' `GLINE' ///
  ytitle("", size(vsmall)) ///
  text(186 `=`G'+0.7' "the same threshold, and nothing" ///
      "on either side of it", ///
      place(e) size(vsmall) color("`INK'%80") justification(left)) ///
  `REGION' legend(off) ///
  title("Eastward: New York back to Switzerland", size(small) ///
      color("`INK'") position(11) justification(left)) ///
  subtitle("Not arbitrage. No threshold, no slope, no sign", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(f3b, replace) nodraw

graph combine f3a f3b, cols(2) ycommon ///
    graphregion(color(white) lcolor(white)) imargin(small) iscale(*0.95) ///
    `TAB' ///
    subtitle("{bf:One leg is priced. The other is not}" ///
        "Swiss customs gold trade with the United States against the New York" ///
        "premium. Each dot is one month, January 2023 to November 2025", `HEAD') ///
    note("Estimated on the tariff window alone: 2020 and the 2022 sanctions shock" ///
        "are location dislocations of a different kind, and folding them in widens" ///
        "the claim past what this paper argues. It costs precision, not the result" ///
        "- the full 2015-2026 series puts the threshold at {c $|}2.99 against {c $|}3.02 here." ///
        "Method: a continuous kink, tonnes = a + b1(x-g) + b2 max(0, x-g), with g by" ///
        "profile least squares, 15% trimmed from each regime, and a 90% interval from" ///
        "2,000 iid and moving-block bootstrap replications. On 35 months that interval" ///
        "is wide - {c $|}0.77 to {c $|}10.82 - and dropping the three largest months moves the" ///
        "point estimate to {c $|}4.72. The threshold is well located and poorly pinned." ///
        "Westward: R-squared 0.44 against 0.36 for a straight line, slope below the" ///
        "threshold 0.5 tonnes per dollar. Eastward: straight-line R-squared 0.000 and" ///
        "a correlation of +0.02, so no line is fitted." ///
        " " ///
        "Sources: Swiss Federal Customs Administration; CME; LBMA; FRED", `NOTE') ///
    name(f3, replace) ysize(5.8) xsize(11.4)

graph export "$OUT/fig3_two_legs.pdf", replace
graph export "$OUT/fig3_two_legs.png", replace width(2800)
di as txt "wrote $OUT/fig3_two_legs.png"

*==============================================================================
* Figure 4 - the monthly path
*==============================================================================
* Shown to the end of the data rather than to the end of the estimation window.
* This figure estimates nothing, and stopping it in November 2025 would end on a
* 63-tonne outflow, leaving the impression that the episode was still running.
* The window figure 3 is fitted on is shaded instead, so the relationship
* between the two is on the page rather than in a caption.
use `monthly', clear
keep if mdate >= tm(2023m1)
gen double west = che_to_us_t
gen double east = -us_to_che_t

local MT1 = tm(2023m1)
local MT2 = tm(2024m1)
local MT3 = tm(2025m1)
local MT4 = tm(2026m1)
local EXM = tm(2025m4)
local WLO = tm(2024m11)
local WHI = tm(2025m11)

gen double wtop = .
gen double wbot = .
gen double wx = .
replace wx = `WLO' in 1
replace wx = `WHI' in 2
replace wtop = 210 in 1/2
replace wbot = -110 in 1/2

twoway ///
  (rarea wtop wbot wx, color("`INK'%5") lwidth(none)) ///
  (bar west mdate, barwidth(0.8) color("`RED'%85") lwidth(none)) ///
  (bar east mdate, barwidth(0.8) color("`BLUE'%85") lwidth(none)) ///
  , ///
  yline(0, lcolor("`INK'%55") lwidth(thin)) ///
  xline(`EXM', lcolor("`INK'%45") lwidth(thin) lpattern(shortdash)) ///
  ylabel(-100 "100" -50 "50" 0 "0" 50 "50" 100 "100" 150 "150" 200 "200", `GRIDY') ///
  xlabel(`MT1' `MT2' `MT3' `MT4', format(%tmCCYY) `GRIDX') ///
  xscale(range(`=tm(2022m11)' `=tm(2026m9)') lcolor(none)) ///
  yscale(range(-110 210) lcolor(none)) ///
  ytitle("Tonnes per month", size(vsmall) color("`SOFT'") margin(r=2)) ///
  xtitle("") ///
  text(185 `=tm(2023m2)' "to New York", place(e) size(vsmall) ///
      color("`RED'") justification(left)) ///
  text(-95 `=tm(2023m2)' "back to Switzerland", place(e) size(vsmall) ///
      color("`BLUE'") justification(left)) ///
  text(150 `=`EXM'+2' "gold exempted," "2 Apr 2025", place(e) size(vsmall) ///
      color("`INK'") justification(left)) ///
  text(-95 `=tm(2025m5)' "shaded: the window figure 3 is estimated on", ///
      place(e) size(vsmall) color("`SOFT'") justification(left)) ///
  `REGION' legend(off) ///
  `TAB' ///
  subtitle("{bf:In, then out, and then quiet again}" ///
      "Swiss customs gold trade with the United States, tonnes a month." ///
      "535 tonnes went west in four months; 383 came back over the next eight", ///
      `HEAD') ///
  note("The reversal begins in the month gold was exempted, not in the month the" ///
      "premium turned - which is the whole of figure 3's right-hand panel in one" ///
      "picture. July 2025 interrupts it: 54 tonnes went west in a single month as" ///
      "the question briefly reopened. Both legs are Swiss customs figures in net" ///
      "mass, so nothing here depends on the gold price." ///
      " " ///
      "Source: Swiss Federal Customs Administration", `NOTE') ///
  ysize(5.4) xsize(9.6) name(f4, replace)

graph export "$OUT/fig4_monthly_path.pdf", replace
graph export "$OUT/fig4_monthly_path.png", replace width(2400)
di as txt "wrote $OUT/fig4_monthly_path.png"
