*! fig12_what_lasted.do
*!
*! The closing figure: what the 2020 and 2025 gold episodes actually cost.
*!
*! THE ARGUMENT THIS FIGURE HAS TO MAKE is a deflationary one, and it should be
*! made honestly rather than hedged. By the end of this project most of the
*! candidate consequences of the gold anomalies have been ruled out:
*!
*!   TRADE STATISTICS. Ruled out. BEA removes nonmonetary gold from the
*!   national accounts outright, and the ITA-NIPA wedge that results is a
*!   known, documented feature rather than a discovery - fig9 shows the gap
*!   IS gold at a correlation of 0.99, which is a validation of the gold
*!   series, not an indictment of the statistics.
*!
*!   REAL RESOURCES. Negligible. Freight, insurance, recasting and transit
*!   financing came to roughly $243 million, about 0.14% of the value
*!   shuttled. The episode was cheap.
*!
*!   THE NOWCAST. Real but brief, and institutionally fixed. GDPNow fell
*!   3.80pp on 28 February 2025, the largest single-day revision outside the
*!   pandemic quarters, and the Atlanta Fed introduced a gold-adjusted model
*!   on 30 April 2025.
*!
*!   THE DEFLATOR. Small, and the only one still running. About 1.8 index
*!   points on the import side since 2015, one-sided, never reversed.
*!
*! So the honest closing claim is not that gold broke the statistics. It is
*! that everything large about these episodes reversed, and the only thing
*! that lasted was small - and that the reason it lasted is a timing mismatch
*! which is structural rather than accidental.
*!
*! THE TIMING MISMATCH IS THE POINT, AND IT IS THE ONE NUMBER TO TAKE AWAY.
*! The 2025 relocation round-tripped completely: cumulative net gold imports
*! ran to +$80.0bn by March 2025 and were back through zero ELEVEN MONTHS
*! later, standing at -$47.6bn by mid-2026. More metal left than arrived.
*! Meanwhile BLS reweights its price indexes from Census annual trade on a
*! two-year lag, so the 2025 gold share does not enter the index weights until
*! 2027 - by which time the metal has been gone for a year, and the weight
*! that finally arrives is wrong in the opposite direction.
*!
*! The measurement system's correction cycle is slower than the phenomenon it
*! is trying to measure. That is why the physical distortion nets out and the
*! measured one does not, and it is a statement about the design of the rule
*! rather than about gold.
*!
*! WHAT THE PANELS SHOW. Panel a is the distortion: monthly net gold trade,
*! large and two-sided, spiking to +$32.5bn in January 2025 and to -$16.7bn in
*! February 2026, netting out. Panel b is what it left behind: the cumulative
*! deflator drift, stepping up at each episode and never stepping back. Same
*! two episodes shaded in both, so the eye connects the spike to the step.
*!
*! Reads   gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*! Writes  gold_final/figures/what_lasted.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig12_what_lasted.do

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

local LAG    = 2
local BASE_M = tm(2015m1)

* The two episode windows, shaded in both panels.
local E1A = tm(2020m3)
local E1B = tm(2020m9)
local E2A = tm(2024m12)
local E2B = tm(2025m3)

tempfile gold mxpi

*================================================================ 1. gold flows
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (sum) v = value_usd, by(m flow)
reshape wide v, i(m) j(flow) string
rename vimports gold_in
rename vexports gold_out
format m %tm
save `gold'

*=========================================================== 2. the BLS indexes
import delimited using "$RAW/us_mxpi_monthly.csv", varnames(1) clear
destring eiuir eiuir14270, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename eiuir      p_bls
rename eiuir14270 p_gold
keep m p_bls p_gold
save `mxpi'

*============================================================= 3. totals, merge
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(master match) nogen
sort m

replace gold_in  = gold_in  / 1e9
replace gold_out = gold_out / 1e9
gen double net   = gold_in - gold_out          // + = metal arriving, $bn
gen double share = gold_in / (bopgimp / 1000)
gen int yr = year(dofm(m))

*=================================================== 4. the weight BLS carries
preserve
    collapse (sum) gold_in bopgimp, by(yr)
    gen double wbase = gold_in / (bopgimp / 1000)
    replace yr = yr + `LAG'
    keep yr wbase
    tempfile wt
    save `wt'
restore
merge m:1 yr using `wt', keep(master match) nogen
sort m

*================================================= 5. the drift it left behind
gen double dlp = .
gen double dlg = .
local prev = .
local prevg = .
forvalues i = 1/`=_N' {
    if !missing(p_bls[`i']) {
        if !missing(`prev') {
            qui replace dlp = ln(p_bls[`i'])  - `prev'  in `i'
            qui replace dlg = ln(p_gold[`i']) - `prevg' in `i'
        }
        local prev  = ln(p_bls[`i'])
        local prevg = ln(p_gold[`i'])
    }
}
gen double png  = (dlp - wbase * dlg) / (1 - wbase)
gen double bias = (share - wbase) * (dlg - png)
gen double drift = 100 * sum(cond(m > `BASE_M' & !missing(bias), bias, 0))
replace drift = . if m < `BASE_M' | (m > `BASE_M' & missing(bias))

keep if m >= `BASE_M'

*=========================================================== 6. what it says
gen double cum25 = sum(cond(m >= tm(2024m11), net, 0))
qui summarize cum25
local PK = r(max)
gsort -cum25
local PKM : display %tmMon_CCYY m[1]
local PKM = trim("`PKM'")
local PKMV = m[1]
sort m
qui summarize cum25 if !missing(cum25)
local LASTC = cum25[_N]
* First month after the peak at which the cumulative is back through zero.
qui summarize m if m > `PKMV' & cum25 <= 0, meanonly
local ZEROM = r(min)
local ZLAB : display %tmMon_CCYY `ZEROM'
local ZLAB = trim("`ZLAB'")
local MONTHS = `ZEROM' - `PKMV'

qui summarize net
local NMAX = r(max)
local NMIN = r(min)
qui summarize drift if !missing(drift)
local D_END = drift[_N]
local D_MAX = r(max)

di as txt "{hline 76}"
di as txt "THE DISTORTION - large, two-sided, and it netted out"
di as txt "   biggest monthly inflow  " %7.1f `NMAX' " bn"
di as txt "   biggest monthly outflow " %7.1f `NMIN' " bn"
di as txt "   2025 episode: cumulative net imports peaked " %6.1f `PK' ///
    " bn in `PKM',"
di as txt "      back through zero in `ZLAB' - " %2.0f `MONTHS' ///
    " months - and now " %6.1f `LASTC' " bn."
di as txt "      More metal left than arrived."
di as txt ""
di as txt "WHAT IT LEFT BEHIND - small, one-sided, still running"
di as txt "   cumulative deflator drift, import side : " %5.2f `D_END' " points"
di as txt "   peak " %5.2f `D_MAX' " - it has never given anything back."
di as txt ""
di as txt "THE TIMING MISMATCH"
di as txt "   the metal round-tripped in " %2.0f `MONTHS' " months."
di as txt "   BLS reweights on a two-year lag, so the 2025 gold share does not"
di as txt "   reach the index weights until 2027 - a year after the metal left."
di as txt "   The correction cycle is slower than the thing it corrects for."
di as txt "{hline 76}"

*=========================================================== 7. the two panels
qui summarize m, meanonly
local M0 = r(min)
local M1 = r(max)
local XMIN = `M0' - 1
local XMAX = `M1' + 1
local Y0 = year(dofm(`M0'))
local Y1 = year(dofm(`M1'))
local XLAB ""
forvalues y = `Y0'/`Y1' {
    if mod(`y', 2) == 1 {
        local XLAB `XLAB' `=tm(`y'm1)' "`y'"
    }
}
gen double mplot = m + 0.5

* Episode shading, drawn as a full-height band behind everything.
local SHADE1 (rarea lo1 hi1 mplot if inrange(m, `E1A', `E1B'), color("`GREY'%18") lwidth(none))
local SHADE2 (rarea lo2 hi2 mplot if inrange(m, `E2A', `E2B'), color("`GREY'%18") lwidth(none))

* --- panel a: the distortion -------------------------------------------------
gen double lo1 = -20
gen double hi1 = 36
gen double lo2 = -20
gen double hi2 = 36
twoway                                                                      ///
    `SHADE1' `SHADE2'                                                       ///
    (bar net mplot if net >= 0, barwidth(0.9) color("`RED'") lwidth(none))  ///
    (bar net mplot if net <  0, barwidth(0.9) color("`GREY'") lwidth(none)) ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    title("{bf:a.} The distortion: large, two-sided, and it netted out"     ///
          "{it:Net US gold imports, {c $|}bn a month. Shaded: the 2020 and 2025 surges}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-20(10)30, angle(0) labsize(vsmall) tlcolor(none)                ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-21 36) noextend lcolor(none))                             ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(3 "Metal arriving" 4 "Metal leaving") rows(1)              ///
           size(vsmall) region(lcolor(none)) symxsize(6) symysize(2)        ///
           position(11) ring(0) bmargin(zero) color("`SOFT'"))              ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=0))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pa, replace) nodraw

* --- panel b: what it left behind --------------------------------------------
replace lo1 = -0.15
replace hi1 = 2.1
replace lo2 = -0.15
replace hi2 = 2.1
twoway                                                                      ///
    `SHADE1' `SHADE2'                                                       ///
    (line drift mplot, lcolor("`RED'") lwidth(0.75) cmissing(n))            ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    title("{bf:b.} What it left behind: small, one-sided, still running"    ///
          "{it:Cumulative overstatement of real goods imports from gold's weight in the deflator, index points, Jan 2015 = 0}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(0(0.5)2, format(%3.1f) angle(0) labsize(vsmall) tlcolor(none)    ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-0.15 2.1) noextend lcolor(none))                          ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(off)                                                             ///
    graphregion(color(white) margin(l=2 r=3 t=0 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pb, replace) nodraw

graph combine pa pb, cols(1) imargin(zero)                                  ///
    xsize(9.6) ysize(7.4)                                                   ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The metal round-tripped in eleven months. The mismeasurement it caused has not reversed at all}" ///
             "What the 2020 and 2025 gold episodes cost, once the things that corrected themselves are set aside", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "Most of the candidate consequences of these episodes do not survive examination, and the figure is drawn to say so. Trade statistics: BEA removes nonmonetary" ///
         "gold from the national accounts outright, and the resulting ITA-NIPA wedge is a documented feature, not a defect. Real resources: freight, insurance," ///
         "recasting and transit financing came to roughly {c $|}243 million, about 0.14% of the value shuttled - the episode was cheap. The nowcast: GDPNow fell 3.80pp on" ///
         "28 February 2025, the largest single-day revision outside the pandemic quarters, and the Atlanta Fed introduced a gold-adjusted model on 30 April 2025." ///
         "Each of those either reversed or was repaired." ///
         " " ///
         "What did not is the deflator. Cumulative net gold imports ran to {c $|}80.0bn by March 2025 and were back through zero eleven months later, standing at" ///
         "-{c $|}47.6bn by mid-2026 - more metal left than arrived. The drift in panel b has given nothing back. The reason is a timing mismatch that is structural rather" ///
         "than accidental: BLS reweights its price indexes from Census annual trade on a TWO-YEAR LAG, so the 2025 gold share does not reach the index weights until" ///
         "2027, a year after the metal left, and the weight that finally arrives is wrong in the opposite direction. The correction cycle is slower than the" ///
         "phenomenon it corrects for." ///
         " " ///
         "That is the case for treating this as a measurement problem rather than a gold problem. The metal's distortion was large but temporary. The defect in the" ///
         "rule that failed to track it is small but permanent - and it will meet the next volatile component in exactly the same way." ///
         "Source: US Census Bureau; Bureau of Labor Statistics (EIUIR, EIUIR14270); Bureau of Economic Analysis; Federal Reserve Bank of Atlanta.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/what_lasted.pdf", replace
di as txt "wrote $FIG/what_lasted.pdf"

capture graph set window fontface "$RESTORE_FONT"
