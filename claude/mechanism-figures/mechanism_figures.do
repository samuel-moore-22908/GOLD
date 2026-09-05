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
*! Reads   claude/mechanism-figures/fig2_dislocation.csv
*!         claude/mechanism-figures/fig3_monthly.csv
*!         claude/mechanism-figures/fig3_hinge.csv
*!         (all three written by build_figure_data.py)
*! Writes  claude/mechanism-figures/figures/fig2_dislocation.pdf and .png
*!         claude/mechanism-figures/figures/fig3_hinge.pdf and .png
*!         claude/mechanism-figures/figures/fig4_return_leg.pdf and .png
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
* Figures 3 and 4 - the hinge, and the leg that has none
*==============================================================================
tempfile hinge
import delimited using "$PROJ/fig3_hinge.csv", varnames(1) clear
gen byte ishinge = 1
save `hinge'

import delimited using "$PROJ/fig3_monthly.csv", varnames(1) stringcols(1) clear
gen int mdate = monthly(ym, "YM")
format mdate %tmMon_CCYY
tempfile monthly
save `monthly'

keep if on_scatter == 1
* covid and the sanctions shock are one visual category: "this happened before,
* for reasons that had nothing to do with tariffs".
gen byte grp = cond(episode == 1, 1, cond(episode > 1, 2, 0))
append using `hinge'
replace ishinge = 0 if missing(ishinge)

* Label placement. Left of the marker for anything near the right-hand edge or
* the ceiling, otherwise right.
gen byte mlpos = 3
replace mlpos = 9  if inlist(ym, "2020-04", "2020-05", "2025-01", "2025-10")
replace mlpos = 12 if inlist(ym, "2022-03", "2025-04")

local SCAT  msymbol(O) msize(small)
local MLAB  mlabsize(vsmall) mlabgap(1.6)
local XAX   xscale(range(-1.3 6.1) lcolor(none))                              ///
            xlabel(-1(1)6, `GRIDX')                                           ///
            xtitle("COMEX premium over London, in excess of carry," ///
                " percentage points a year, monthly mean", ///
                size(vsmall) color("`SOFT'") margin(t=2))
local YAX   yscale(range(0 210) lcolor(none)) ylabel(0(50)200, `GRIDY')

*------------------------------------------------------------------- figure 3
twoway ///
  (scatter che_to_us_t disloc_pp if ishinge == 0 & grp == 0, ///
      `SCAT' mcolor("`GREY'%55")) ///
  (scatter che_to_us_t disloc_pp if ishinge == 0 & grp == 2, ///
      `SCAT' mcolor("`BLUE'%85") msize(medsmall)) ///
  (scatter che_to_us_t disloc_pp if ishinge == 0 & grp == 1, ///
      `SCAT' mcolor("`RED'") msize(medsmall) ///
      mlabel(callout) `MLAB' mlabcolor("`INK'") mlabvposition(mlpos)) ///
  (scatter che_to_us_t disloc_pp if ishinge == 0 & grp == 2 & callout != "", ///
      msymbol(none) mlabel(callout) `MLAB' mlabcolor("`INK'") ///
      mlabvposition(mlpos)) ///
  (connected med_west x if ishinge == 1, ///
      lcolor("`INK'%70") lwidth(medium) lpattern(solid) ///
      msymbol(D) msize(vsmall) mcolor("`INK'%70")) ///
  , ///
  `XAX' `YAX' ///
  ytitle("Tonnes per month", size(vsmall) color("`SOFT'") margin(r=2)) ///
  text(52 1.80 "median of each" "spread bucket", place(e) size(vsmall) ///
      color("`INK'%75") justification(left)) ///
  `REGION' ///
  legend(order(3 "the tariff scare, Nov 2024-Nov 2025" ///
               2 "covid 2020 and the 2022 sanctions shock" ///
               1 "every other month") ///
      cols(1) size(vsmall) region(lcolor(none) color(white)) ///
      symxsize(4) position(2) ring(0) bmargin(l=10 t=4)) ///
  `TAB' ///
  subtitle("{bf:Nothing moves until the premium clears the cost of moving}" ///
      "Swiss customs gold exports to the United States against the New York" ///
      "premium. Each dot is one month, January 2015 to July 2026", `HEAD') ///
  note("The step sits between +0.5 and +1.0 points a year - roughly 3 to 7 dollars" ///
      "an ounce over ninety days, which is an estimate of the all-in cost of moving" ///
      "metal across the Atlantic obtained from behaviour rather than freight invoices." ///
      " " ///
      "Sources: Swiss Federal Customs Administration; CME; LBMA; FRED", `NOTE') ///
  ysize(6.0) xsize(8.6) name(f3, replace)

graph export "$OUT/fig3_hinge.pdf", replace
graph export "$OUT/fig3_hinge.png", replace width(2400)
di as txt "wrote $OUT/fig3_hinge.png"

*------------------------------------------------- figure 4, left: no hinge
* Deliberately the same frame and the same vertical scale as figure 3. The
* contrast is the finding, so it has to be structural rather than argued.
twoway ///
  (scatter us_to_che_t disloc_pp if ishinge == 0 & grp == 0, ///
      `SCAT' mcolor("`GREY'%55")) ///
  (scatter us_to_che_t disloc_pp if ishinge == 0 & grp == 2, ///
      `SCAT' mcolor("`BLUE'%85") msize(medsmall)) ///
  (scatter us_to_che_t disloc_pp if ishinge == 0 & grp == 1, ///
      `SCAT' mcolor("`RED'") msize(medsmall)) ///
  (connected med_east x if ishinge == 1, ///
      lcolor("`INK'%70") lwidth(medium) lpattern(solid) ///
      msymbol(D) msize(vsmall) mcolor("`INK'%70")) ///
  , ///
  `XAX' `YAX' ///
  ytitle("Tonnes per month", size(vsmall) color("`SOFT'") margin(r=2)) ///
  `REGION' legend(off) ///
  title("Eastward: the return leg", size(small) color("`INK'") ///
      position(11) justification(left)) ///
  subtitle("US exports to Switzerland. Same axes as the panel opposite", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(f4a, replace) nodraw

*------------------------------------------ figure 4, right: the monthly path
use `monthly', clear
keep if mdate >= tm(2023m1)
gen double west = che_to_us_t
gen double east = -us_to_che_t

local MT1 = tm(2023m1)
local MT2 = tm(2024m1)
local MT3 = tm(2025m1)
local MT4 = tm(2026m1)
local EXM = tm(2025m4)

twoway ///
  (bar west mdate, barwidth(0.85) color("`RED'%85") lwidth(none)) ///
  (bar east mdate, barwidth(0.85) color("`BLUE'%85") lwidth(none)) ///
  , ///
  yline(0, lcolor("`INK'%55") lwidth(thin)) ///
  xline(`EXM', lcolor("`INK'%40") lwidth(thin) lpattern(shortdash)) ///
  ylabel(-100 "100" -50 "50" 0 "0" 50 "50" 100 "100" 150 "150" 200 "200", `GRIDY') ///
  xlabel(`MT1' `MT2' `MT3' `MT4', format(%tmCCYY) `GRIDX') ///
  xscale(lcolor(none)) yscale(lcolor(none)) ///
  ytitle("Tonnes per month", size(vsmall) color("`SOFT'") margin(r=2)) ///
  xtitle("") ///
  text(170 `=tm(2023m3)' "to New York", place(e) size(vsmall) ///
      color("`RED'") justification(left)) ///
  text(-88 `=tm(2023m3)' "back to Switzerland", place(e) size(vsmall) ///
      color("`BLUE'") justification(left)) ///
  text(120 `=`EXM'+1' "gold exempted," "2 Apr 2025", place(e) size(vsmall) ///
      color("`INK'") justification(left)) ///
  `REGION' legend(off) ///
  title("The monthly path", size(small) color("`INK'") ///
      position(11) justification(left)) ///
  subtitle("Swiss customs, gold trade with the United States", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(f4b, replace) nodraw

graph combine f4a f4b, cols(2) ///
    graphregion(color(white) lcolor(white)) imargin(small) iscale(*0.95) ///
    `TAB' ///
    subtitle("{bf:The metal came back, but not because it was paid to}" ///
        "The westward leg is arbitrage and has a threshold. The return east has" ///
        "neither: it began when the premium disappeared, not when it inverted", ///
        `HEAD') ///
    note("Correlation between the premium and the return flow is -0.08, and -0.04" ///
        "against a six-month inventory overhang. This contradicts the project's" ///
        "standing assumption that the sign of the spread sets the direction of travel." ///
        " " ///
        "Sources: Swiss Federal Customs Administration; CME; LBMA; FRED", `NOTE') ///
    name(f4, replace) ysize(5.8) xsize(11.4)

graph export "$OUT/fig4_return_leg.pdf", replace
graph export "$OUT/fig4_return_leg.png", replace width(2800)
di as txt "wrote $OUT/fig4_return_leg.png"
