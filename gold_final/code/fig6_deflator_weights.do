*! fig6_deflator_weights.do
*!
*! The weight the price index carries, against the share trade actually has.
*! Both sides of the goods account.
*!
*! THE CORRECTION THIS FIGURE MAKES. An earlier version of this work assumed
*! the BLS import price index carries gold at a fixed base-period weight of
*! roughly 0.5%, and said so while admitting the number was an assumption
*! because "BLS does not publish the gold weight". That framing was wrong in a
*! way that matters. BLS does publish enough to compute it. From the Handbook
*! of Methods: the import and export price indexes use a LOWE (modified
*! fixed-quantity Laspeyres) formula, chained monthly, and the trade weights
*! are "reported by the Census Bureau", with "updates to classification
*! structures and trade weights ... made every year in January" on a two-year
*! lag - BLS's own worked example being that "the weights for the indexes in
*! 2025 are based on the import and export trade weights from the 2023
*! calendar year."
*!
*! So the weight is not fixed and it is not unknown. It is last-but-one year's
*! annual share, which this file computes from the same Census pull that gives
*! the monthly share. Nothing here is assumed any more.
*!
*! COVERAGE IS NOT THE PROBLEM, AND THIS SETTLES IT. BLS publishes a dedicated
*! nonmonetary gold index for each side - EIUIR14270 for imports, EIUIQ12260
*! for exports. Gold is sampled, and the sampled price tracks the metal (the
*! regression of each index on the LBMA price in monthly log changes gives a
*! slope near 0.9). The index is not blind to gold. It is carrying the wrong
*! amount of it.
*!
*! WHAT THE FIGURE SHOWS. Two panels, imports above and exports below. In each,
*! the red line is gold's actual monthly share of that side of the goods
*! account and the dark step is the weight the index carries that year. A
*! reweighting rule exists precisely to keep those two together. For gold it
*! does not: the correlation between the two is NEGATIVE on both sides, -0.11
*! for imports and -0.05 for exports. The rule is no better than a constant.
*!
*! The mechanism is the lag. Gold's share spikes and reverts inside a year,
*! so by the time a surge reaches the weights the flow has already turned. The
*! index under-weighted gold through the 2020 surge, then OVER-weighted it in
*! 2022 when that surge finally entered the weights and the metal had gone
*! home; it under-weighted the 2025 tariff episode, and by 2026 is
*! over-weighting imports again for the same reason. Each panel crosses.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/deflator_weights.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig6_deflator_weights.do

version 18
clear all
set more off
graph drop _all

*============================================================== paths and style
* EDIT THIS IF YOU MOVE THE PROJECT ------------------------------------------
global ROOT "C:/Users/smoor/GitHub/GOLD"
* ----------------------------------------------------------------------------
global RAW  "$ROOT/gold_final/data/raw"
global FIG  "$ROOT/gold_final/figures"

global RESTORE_FONT "Times New Roman"
capture graph set window fontface "Arial Narrow"

local RED  "227 18 11"
local INK  "18 18 18"
local GREY "117 141 153"
local RULE "224 228 231"
local SOFT "112 112 112"

local LAG = 2               // BLS weight lag, in years. Their rule, not ours.

tempfile gold

*================================================================ 1. gold flows
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (sum) v = value_usd, by(m flow)
reshape wide v, i(m) j(flow) string
rename vimports gold_m
rename vexports gold_x
format m %tm
save `gold'

*======================================================== 2. totals and indexes
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp bopgexp
merge 1:1 m using `gold', keep(match) nogen
sort m

* BOPGIMP/BOPGEXP are $ millions; the Census gold pull is dollars.
gen double s_m = 100 * gold_m / (bopgimp * 1e6)
gen double s_x = 100 * gold_x / (bopgexp * 1e6)
gen int yr = year(dofm(m))

*=================================================== 3. the weight BLS carries
* Gold's share of each side in each CALENDAR YEAR, which is the Census annual
* figure BLS reweights from. Then lag it by two years and attach it to every
* month of the receiving year - that is the step the index actually walks.
preserve
    collapse (sum) gold_m gold_x bopgimp bopgexp, by(yr)
    gen double w_m = 100 * gold_m / (bopgimp * 1e6)
    gen double w_x = 100 * gold_x / (bopgexp * 1e6)
    * The weight YEAR+LAG will be given, so shift the label forward.
    replace yr = yr + `LAG'
    keep yr w_m w_x
    tempfile wt
    save `wt'
restore
merge m:1 yr using `wt', keep(master match) nogen
sort m

*=========================================================== 4. what it says
* Does the reweighting rule track the share it exists to track?
qui correlate s_m w_m if yr >= 2019
local R_M = r(rho)
qui correlate s_x w_x if yr >= 2019
local R_X = r(rho)

gen double gap_m = s_m - w_m
gen double gap_x = s_x - w_x

di as txt "{hline 70}"
di as txt "Does the annual reweighting track gold's share? (2019 onward)"
di as txt "   imports  corr(share, carried weight) = " %6.3f `R_M'
di as txt "   exports  corr(share, carried weight) = " %6.3f `R_X'
di as txt ""
di as txt "Mean gap by year, percentage points (+ = index under-weights gold)"
di as txt "   year     imports     exports"
forvalues y = 2020/2026 {
    qui summarize gap_m if yr == `y', meanonly
    local GM = r(mean)
    qui summarize gap_x if yr == `y', meanonly
    local GX = r(mean)
    di as txt "   `y'   " %9.2f `GM' "   " %9.2f `GX'
}
di as txt ""
qui summarize s_m, meanonly
local SM_MAX = r(max)
gsort -s_m
local SM_MAX_M : display %tmMon_CCYY m[1]
qui summarize s_x, meanonly
local SX_MAX = r(max)
gsort -s_x
local SX_MAX_M : display %tmMon_CCYY m[1]
sort m
di as txt "Peak monthly share: imports " %5.2f `SM_MAX' "% (" trim("`SM_MAX_M'") ///
    "), exports " %5.2f `SX_MAX' "% (" trim("`SX_MAX_M'") ")"
di as txt "{hline 70}"

*=========================================================== 5. the two panels
qui summarize m if !missing(s_m, w_m), meanonly
local M0 = r(min)
local M1 = r(max)
local Y0 = year(dofm(`M0'))
local Y1 = year(dofm(`M1'))
local XMIN = `M0' - 1
local XMAX = `M1' + 1

* Enumerate the year ticks rather than relying on a step, so every label is a
* real January and none is invented past the end of the data.
local XLAB ""
forvalues y = `Y0'/`Y1' {
    local XLAB `XLAB' `=tm(`y'm1)' "`y'"
}

gen double mplot = m + 0.5          // a month is an interval; centre it

foreach side in m x {
    if "`side'" == "m" {
        local WHAT "imports"
        local TTL  "{bf:a.} Imports: gold's share of US goods imports, and the weight the import price index carries"
        local YMAX = 11
        local YLAB 0(2)10
        local RHO  = `R_M'
        local LEGEND order(2 "Gold's actual monthly share"                  ///
                     3 "Weight the index carries (previous-but-one year)")  ///
               rows(1) size(vsmall) region(lcolor(none)) symxsize(6)        ///
               symysize(2) position(12) ring(1) bmargin(zero)               ///
               color("`SOFT'")
    }
    else {
        local WHAT "exports"
        local TTL  "{bf:b.} Exports: gold's share of US goods exports, and the weight the export price index carries"
        local YMAX = 11
        local YLAB 0(2)10
        local RHO  = `R_X'
        local LEGEND off
    }

    twoway                                                                  ///
        (rarea s_`side' w_`side' mplot, color("`RED'%18") lwidth(none)      ///
            cmissing(n))                                                    ///
        (line s_`side' mplot, lcolor("`RED'") lwidth(0.50) cmissing(n))     ///
        (line w_`side' mplot, lcolor("`INK'") lwidth(0.45)                  ///
            connect(stairstep) cmissing(n))                                 ///
        ,                                                                   ///
        title("`TTL'", size(small) color("`INK'") position(11)              ///
              justification(left) span)                                     ///
        ytitle("% of goods `WHAT'", size(vsmall) color("`SOFT'"))           ///
        ylabel(`YLAB', labsize(vsmall) labcolor("`SOFT'") angle(0)          ///
               grid glcolor("`RULE'") glwidth(0.18) gmin gmax)              ///
        yscale(range(0 `YMAX') noextend lcolor(none))                       ///
        xlabel(`XLAB', labsize(vsmall) labcolor("`SOFT'") nogrid)           ///
        xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))              ///
        xtitle("")                                                          ///
        legend(`LEGEND')                                                    ///
        graphregion(color(white) margin(l=2 r=4 t=1 b=1))                   ///
        plotregion(color(white) margin(zero) lcolor(none))                  ///
        name(p_`side', replace) nodraw
}

graph combine p_m p_x, cols(1) imargin(zero) ysize(7.2) xsize(9.6)          ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The deflator's basket and the trade it deflates have come apart}" ///
             "Gold is sampled in both price indexes. The question is how much of it they carry, and the answer is set two years late", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "BLS reweights the import and export price indexes every January from Census annual trade values on a two-year lag, so the 2025 indexes carry 2023 weights" ///
         "(BLS Handbook of Methods). The dark step is that rule applied to gold; the red line is what gold's share actually did. A reweighting rule exists to keep the" ///
         "two together, and for gold it fails: the correlation between them is NEGATIVE on both sides, -0.11 for imports and -0.05 for exports - no better than a" ///
         "constant. The lag is why. Gold's share spikes and reverts inside a year, so a surge reaches the weights only after the metal has gone home. The index" ///
         "under-weighted gold through 2020, over-weighted it in 2022 once that surge entered the weights, under-weighted the 2025 tariff episode, and by 2026 is" ///
         "over-weighting imports again. Shaded area is the gap. Share is nonmonetary gold (HS 7108 and 7115) over goods trade on a BOP basis." ///
         "Source: Bureau of Labor Statistics (EIUIR, EIUIQ, EIUIR14270, EIUIQ12260); US Census Bureau; Bureau of Economic Analysis.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/deflator_weights.pdf", replace
di as txt "wrote $FIG/deflator_weights.pdf"

capture graph set window fontface "$RESTORE_FONT"
