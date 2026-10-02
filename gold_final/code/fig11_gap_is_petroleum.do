*! fig11_gap_is_petroleum.do
*!
*! If the gap between the two import price indexes is not gold, what is it?
*! It is petroleum - and the contrast between the two is the point.
*!
*! THE QUESTION THIS ANSWERS. fig10_two_import_deflators.do shows the BLS
*! all-commodities import index running nearly four points above the NIPA goods
*! index since 2015, and shows that gold cannot be the explanation: the gold
*! correction RAISES the BLS index, so correcting for it moves the two further
*! apart rather than closer. That left the gap unexplained. This file explains
*! it.
*!
*! IT IS PETROLEUM. The BLS fuels index (EIUIR10, BEA end use 10) correlates
*! 0.95 with WTI in monthly log changes and swings from 112 to 408 over this
*! window - a 1.9x range, and nothing else in traded goods moves like it.
*! Regressing the NIPA-BLS gap on cumulative fuel inflation gives an R-squared
*! of 0.82 and cuts the gap's standard deviation from 1.42 points to 0.60. The
*! quarters that move the gap most are exactly the oil quarters: the 2015 and
*! 2016 crashes, the 2021 recovery, the 2022 spike to -6.4 points, and the
*! 2022Q3 reversal.
*!
*! THE MECHANISM, WITH ONE HONEST GAP. A Lowe index with two-year-lagged
*! weights diverges from a chain-Fisher index whenever relative prices move,
*! and petroleum is where relative prices move most. The sign is the textbook
*! one: when oil rises the US imports less of it, so its current weight falls,
*! and a stale-weight index keeps overweighting the price that rose. BLS ends
*! up above NIPA, which is what we see.
*!
*! What this file CANNOT separate is substitution bias - Fisher against
*! Laspeyres on the same basket - from a plain weight-level difference, MXPI
*! simply carrying more petroleum than NIPA goods does. The fitted slope
*! implies a weight difference near 4.4 percentage points, which is larger than
*! the known coverage exclusions (military goods, used goods, art) can
*! plausibly produce, so substitution is the better bet. It is a bet, not a
*! result. Settling it needs a chained current-weight index rebuilt from the
*! BLS components and Census end-use values, which is not done here.
*!
*! WHY THIS STRENGTHENS THE GOLD ARGUMENT RATHER THAN DISPLACING IT. Petroleum
*! is the same defect as gold - a lagged weight failing a volatile share - in a
*! much bigger component. So gold is not unique. But the two behave completely
*! differently, and panel b is the whole reason this figure exists:
*!
*!   The fuel-driven part is a function of where the oil price SITS, so it is
*!   TWO-SIDED. It ranges from +2.15 points to -3.57 and crosses zero FIVE
*!   times: positive through the 2015-16 and 2020 oil crashes, deeply negative
*!   through the 2022 spike. It does not unwind so much as oscillate, which is
*!   the same thing for the purpose here - it has no permanent level.
*!
*!   The gold drift is a cumulated COVARIANCE - gold's share spikes together
*!   with gold's price, so the errors do not cancel - and it is ONE-SIDED. It
*!   ranges from -0.01 to +1.81, crosses zero only at the origin, and ends at
*!   99% of its own maximum. It has never given anything back.
*!
*! They also push in OPPOSITE directions on the published index, which is worth
*! knowing on its own: stale petroleum weights make the BLS index too high,
*! stale gold weights make it too low, and the two partly offset.
*!
*! So: the lagged-weight defect is general and petroleum is its largest
*! instance, but petroleum's error oscillates with the oil price while gold's
*! only accumulates. That is why the gold drift, though much the smaller
*! number, is the one that lasts.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/gap_is_petroleum.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig11_gap_is_petroleum.do

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
local BASE_Q = tq(2015q1)

tempfile gold mxpi

*================================================================ 1. gold flows
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
keep if flow == "imports"
gen double m = mofd(date(date, "YMD"))
collapse (sum) gold_usd = value_usd, by(m)
format m %tm
save `gold'

*=========================================================== 2. the BLS indexes
import delimited using "$RAW/us_mxpi_monthly.csv", varnames(1) clear
destring eiuir eiuir14270 eiuir10, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename eiuir      p_bls
rename eiuir14270 p_gold
rename eiuir10    p_fuel
keep m p_bls p_gold p_fuel
save `mxpi'

*====================================================== 3. totals and the NIPA
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp b021rg3q086sbea, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename b021rg3q086sbea p_nipa
keep m bopgimp p_nipa
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(master match) nogen
sort m

gen double share = gold_usd / (bopgimp * 1e6)
gen int yr = year(dofm(m))

*=================================================== 4. the weight BLS carries
preserve
    collapse (sum) gold_usd bopgimp, by(yr)
    gen double wbase = gold_usd / (bopgimp * 1e6)
    replace yr = yr + `LAG'
    keep yr wbase
    tempfile wt
    save `wt'
restore
merge m:1 yr using `wt', keep(master match) nogen
sort m

*======================================= 5. the gold correction to the BLS index
* Interval-aware: differences against the previous non-missing observation, so
* the October 2025 hole is not bridged.
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

*============================================================ 6. to quarterly
gen int q = qofd(dofm(m))
format q %tq
collapse (mean) p_bls p_nipa p_fuel (sum) bias_q = bias, by(q)
sort q
keep if q >= `BASE_Q'
drop if missing(p_bls, p_nipa, p_fuel)

foreach v in p_bls p_nipa {
    qui summarize `v' if q == `BASE_Q', meanonly
    gen double i_`v' = 100 * `v' / r(mean)
}
gen double gap = i_p_nipa - i_p_bls

* Cumulative fuel inflation since the base quarter, in per cent.
qui summarize p_fuel if q == `BASE_Q', meanonly
gen double cumfuel = 100 * ln(p_fuel / r(mean))

* The gold drift, cumulated on the same base, in index points.
gen double goldcum = 100 * sum(cond(q > `BASE_Q', bias_q, 0))

*=============================================== 7. how much of the gap is fuel
regress gap cumfuel
local B1   = _b[cumfuel]
local R2   = e(r2)
predict double fuelfit, xb
predict double fuelres, residuals
* Re-centre the fitted part on the base quarter so it starts at zero alongside
* the gold drift and the two are directly comparable.
qui summarize fuelfit if q == `BASE_Q', meanonly
gen double fuelpart = fuelfit - r(mean)

qui summarize gap
local SD_GAP = r(sd)
qui summarize fuelres
local SD_RES = r(sd)
qui summarize q, meanonly
local QEND = r(max)
local ENDLAB : display %tqCCYY!Qq `QEND'
local ENDLAB = trim("`ENDLAB'")

di as txt "{hline 76}"
di as txt "Regressing the NIPA-BLS gap on cumulative fuel inflation"
di as txt "   slope      " %8.4f `B1' " points per 1% of cumulative fuel inflation"
di as txt "   R-squared  " %8.3f `R2'
di as txt "   gap sd " %5.2f `SD_GAP' " -> residual sd " %5.2f `SD_RES' ///
    "  (" %3.0f 100*(1-`SD_RES'/`SD_GAP') "% of the variation removed)"
di as txt "   implied weight difference on petroleum: " %4.1f 100*abs(`B1') ///
    " percentage points"
di as txt ""
qui summarize fuelpart
local FP_MIN = r(min)
qui summarize fuelpart if q == `QEND', meanonly
local FP_END = r(mean)
qui summarize goldcum
local GC_MAX = r(max)
qui summarize goldcum if q == `QEND', meanonly
local GC_END = r(mean)
* Two-sided versus one-sided is the property that matters, so count zero
* crossings rather than quoting a percentage unwound from a single peak.
foreach v in fuelpart goldcum {
    gen byte sgn_`v' = sign(`v')
    gen byte cross_`v' = sgn_`v' != sgn_`v'[_n-1] & _n > 1 & !missing(`v')
    qui summarize cross_`v'
    local X_`v' = r(sum)
    qui summarize `v'
    local LO_`v' = r(min)
    local HI_`v' = r(max)
}
qui summarize fuelpart if q == `QEND', meanonly
local FP_END = r(mean)
qui summarize goldcum if q == `QEND', meanonly
local GC_END = r(mean)

di as txt "TWO-SIDED vs ONE-SIDED, index points"
di as txt "   petroleum : range " %6.2f `LO_fuelpart' " to " %5.2f `HI_fuelpart' ///
    "   crosses zero " %2.0f `X_fuelpart' " times   ends " %6.2f `FP_END'
di as txt "   gold      : range " %6.2f `LO_goldcum' " to " %5.2f `HI_goldcum' ///
    "   crosses zero " %2.0f `X_goldcum' " time    ends " %6.2f `GC_END'
di as txt "   gold ends at " %3.0f 100*`GC_END'/`HI_goldcum' ///
    "% of its own maximum - it has never given anything back"
di as txt ""
di as txt "   They also push OPPOSITE ways on the published BLS index: stale"
di as txt "   petroleum weights make it too high, stale gold weights too low."
di as txt "{hline 76}"

*=========================================================== 8. the two panels
qui summarize q, meanonly
local Q0 = r(min)
local Q1 = r(max)
local XMIN = `Q0' - 1
local XMAX = `Q1' + 1
local Y0 = year(dofq(`Q0'))
local Y1 = year(dofq(`Q1'))
local XLAB ""
forvalues y = `Y0'/`Y1' {
    if mod(`y', 2) == 1 {
        local XLAB `XLAB' `=tq(`y'q1)' "`y'"
    }
}

local R2TXT : display %4.2f `R2'

twoway                                                                      ///
    (line gap q, lcolor("`INK'") lwidth(0.65) cmissing(n))                  ///
    (line fuelfit q, lcolor("`RED'") lwidth(0.50) lpattern(dash)            ///
        cmissing(n))                                                        ///
    (line fuelres q, lcolor("`GREY'") lwidth(0.40) cmissing(n))             ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    title("{bf:a.} The gap is petroleum"                                    ///
          "{it:NIPA minus BLS, index points, against what cumulative fuel inflation alone predicts. R-squared `R2TXT'}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-8(2)2, angle(0) labsize(vsmall) tlcolor(none)                   ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-8.6 2.6) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "NIPA minus BLS, as published"                           ///
                 2 "Fitted on cumulative fuel inflation alone"              ///
                 3 "What fuel does not explain")                            ///
           rows(3) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(7) ring(0) bmargin(zero) color("`SOFT'"))   ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pfuel, replace) nodraw

twoway                                                                      ///
    (line fuelpart q, lcolor("`INK'") lwidth(0.65) cmissing(n))             ///
    (line goldcum q, lcolor("`RED'") lwidth(0.65) cmissing(n))              ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    title("{bf:b.} One of them is two-sided. The other has never given anything back" ///
          "{it:Index points since 2015Q1. Note they push OPPOSITE ways on the BLS index: petroleum raises it, gold lowers it}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-4(1)2, angle(0) labsize(vsmall) tlcolor(none)                   ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-4.3 2.4) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "Petroleum: two-sided, crosses zero five times, spans +2.2 to -3.6" ///
                 2 "Gold: one-sided, ends at 99% of its own maximum")       ///
           rows(2) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(7) ring(0) bmargin(zero) color("`SOFT'"))   ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pcontrast, replace) nodraw

graph combine pfuel pcontrast, cols(2) imargin(small)                       ///
    xsize(12.4) ysize(5.8)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The gap between the two import price indexes is petroleum - and petroleum's error oscillates, while gold's only accumulates}" ///
             "The same defect, a weight set years late, in two components that behave nothing alike", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "The BLS fuels index (end use 10) correlates 0.95 with WTI in monthly log changes and ranges from 112 to 408 over this window; nothing else in traded goods" ///
         "moves like that. Regressing the NIPA-BLS gap on cumulative fuel inflation alone gives an R-squared of 0.82 and cuts the gap's standard deviation from 1.42" ///
         "points to 0.60. The quarters that move the gap most are the oil quarters: the 2015 and 2016 crashes, the 2021 recovery, the 2022 spike to -6.4, and the" ///
         "2022Q3 reversal." ///
         " " ///
         "The mechanism is a stale weight meeting a volatile price, exactly as with gold. When oil rises the US imports less of it, so its current weight falls, and" ///
         "an index carrying two-year-old weights keeps overweighting the price that rose - which puts BLS above NIPA, the sign observed. One thing this figure cannot" ///
         "do is separate substitution bias, Fisher against Laspeyres on the same basket, from MXPI simply carrying more petroleum than NIPA goods does. The fitted" ///
         "slope implies a weight difference near 4.4 percentage points, larger than the known coverage exclusions - military goods, used goods, art - can plausibly" ///
         "produce, so substitution is the better bet. It is a bet, not a result; settling it needs a chained current-weight index rebuilt from the BLS components." ///
         " " ///
         "Panel b is why this does not displace the gold finding. Petroleum is the same defect in a much larger component, so gold is not unique - but the two behave" ///
         "nothing alike. The fuel-driven part is a function of where the oil price SITS, so it is two-sided: it ranges from +2.15 points to -3.57 and crosses zero five" ///
         "times, positive through the 2015-16 and 2020 crashes and deeply negative through the 2022 spike. It has no permanent level. The gold drift is a cumulated" ///
         "covariance - gold's share spikes together with gold's price, so the errors never cancel - and it is one-sided: it crosses zero only at the origin and ends at" ///
         "99% of its own maximum, having never given anything back. The lagged-weight defect is general and petroleum is its largest instance, but petroleum's error" ///
         "oscillates and gold's accumulates. That is why the gold drift, much the smaller number, is the one that lasts." ///
         "Source: Bureau of Labor Statistics (EIUIR, EIUIR10, EIUIR14270); Bureau of Economic Analysis; US Census Bureau.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/gap_is_petroleum.pdf", replace
di as txt "wrote $FIG/gap_is_petroleum.pdf"

capture graph set window fontface "$RESTORE_FONT"
