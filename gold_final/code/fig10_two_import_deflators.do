*! fig10_two_import_deflators.do
*!
*! The two import price indexes side by side: the one the trade release is
*! deflated with, and the one the national accounts use.
*!
*! WHAT THE TWO ARE.
*!   BLS MXPI (EIUIR)  all-commodities import price index. A Lowe index,
*!                     chained monthly, reweighted each January from Census
*!                     annual trade on a two-year lag. INCLUDES nonmonetary
*!                     gold, at that lagged weight. This is what anyone
*!                     deflating the monthly trade release reaches for.
*!   NIPA (B021RG3)    chain-type price index for imports of GOODS. Fisher,
*!                     reweighted every period. EXCLUDES nonmonetary gold,
*!                     because BEA removes it from the national accounts.
*!
*! THE HEADLINE NUMBER. Since 2015Q1 the BLS index has risen 19.2% and the
*! NIPA index 15.5%. The gap reaches 6.4 index points and stands at 3.7.
*!
*! DO NOT READ THAT GAP AS GOLD. This is the whole reason the second panel
*! exists. The temptation is obvious - one index has gold in it and the other
*! does not, so the difference must be gold - and it is wrong twice over.
*!
*!   THE SIGN IS BACKWARDS. BLS sits ABOVE NIPA. But the gold correction says
*!   the BLS index UNDERSTATES inflation, by about 1.7 points since 2020,
*!   because it carries gold below the share trade actually had. Correcting
*!   BLS for gold pushes it HIGHER still and moves the two indexes FURTHER
*!   APART. Gold cannot be what closes this gap; it widens it.
*!
*!   AND THE CORRELATION IS NOT THERE. Tested directly in
*!   fig5_deflator_gold.do, the quarterly NIPA-BLS gap correlates -0.15 with
*!   the predicted gold term.
*!
*! WHAT THE GAP ACTUALLY IS. Formula and coverage. Lowe with two-year-lagged
*! weights against chain-Fisher will diverge on any basket whose composition
*! moves, and MXPI does not price military goods, used goods or art at all.
*! A useful scale check: BEA's own two measures of the same concept - the
*! published chain-type index and the deflator implied by dividing nominal
*! goods imports by chained goods imports - differ from each other by up to
*! 4.2 points over this window. The NIPA-BLS gap is the same order of
*! magnitude as the internal spread between two NIPA constructions, which is
*! why no single-cause story about it is safe.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/two_import_deflators.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig10_two_import_deflators.do

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
destring eiuir eiuir14270, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename eiuir      p_bls
rename eiuir14270 p_gold
keep m p_bls p_gold
save `mxpi'

*====================================================== 3. totals and the NIPA
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp b021rg3q086sbea a255rc1q027sbea a255rx1q020sbea, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename b021rg3q086sbea p_nipa
* BEA's OWN second measure of the same concept: nominal goods imports divided
* by chained goods imports. Carried only as a scale check on the gap.
gen double p_nipa_imp = 100 * a255rc1q027sbea / a255rx1q020sbea
keep m bopgimp p_nipa p_nipa_imp
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
* Interval-aware, as elsewhere: differences against the previous non-missing
* observation, so the October 2025 hole is not bridged.
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
collapse (mean) p_bls p_nipa p_nipa_imp (sum) bias_q = bias, by(q)
sort q
keep if q >= `BASE_Q'
drop if missing(p_bls, p_nipa)

* Rebase everything on the first common quarter, and cumulate the gold
* correction from the same point so the three are on one footing.
foreach v in p_bls p_nipa p_nipa_imp {
    qui summarize `v' if q == `BASE_Q', meanonly
    gen double i_`v' = 100 * `v' / r(mean)
}
gen double cum_bias = 100 * sum(cond(q > `BASE_Q', bias_q, 0))
* What the BLS index would read if gold were carried at its actual share.
gen double i_bls_adj = i_p_bls * exp(cum_bias / 100)

gen double gap      = i_p_nipa - i_p_bls          // NIPA minus BLS
gen double gap_adj  = i_p_nipa - i_bls_adj        // after correcting BLS
gen double nipa_spread = i_p_nipa - i_p_nipa_imp  // BEA against BEA

*=========================================================== 7. what it says
qui summarize q, meanonly
local QEND = r(max)
local ENDLAB : display %tqCCYY!Qq `QEND'
local ENDLAB = trim("`ENDLAB'")

di as txt "{hline 76}"
di as txt "Import price indexes, 2015Q1 = 100, at `ENDLAB'"
foreach v in i_p_bls i_p_nipa i_p_nipa_imp {
    qui summarize `v' if q == `QEND', meanonly
    local L`v' = r(mean)
}
di as txt "   BLS MXPI, all commodities (gold in, lagged weight) : " %6.1f `Li_p_bls'
di as txt "   NIPA chain-type, goods (gold out)                  : " %6.1f `Li_p_nipa'
di as txt "   NIPA implied by nominal / chained goods            : " %6.1f `Li_p_nipa_imp'
di as txt ""
qui summarize gap
di as txt "NIPA minus BLS: min " %6.2f r(min) "  max " %6.2f r(max)
qui summarize gap if q == `QEND', meanonly
local G_END = r(mean)
qui summarize gap_adj if q == `QEND', meanonly
local GA_END = r(mean)
di as txt "   at `ENDLAB'                      : " %6.2f `G_END' " points"
di as txt "   after correcting BLS for gold    : " %6.2f `GA_END' " points"
di as txt "   -> the correction WIDENS the gap by " %5.2f `G_END' - `GA_END' ///
    " points. Gold is not what separates these two."
di as txt ""
qui summarize nipa_spread
di as txt "Scale check - BEA's own two measures of the same concept differ by"
di as txt "   up to " %5.2f max(abs(r(min)), abs(r(max))) " points over this window, which is the same"
di as txt "   order as the NIPA-BLS gap itself."
qui correlate gap cum_bias
di as txt ""
di as txt "corr(NIPA-BLS gap, cumulated gold correction) = " %6.3f r(rho)
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

twoway                                                                      ///
    (rarea i_p_bls i_p_nipa q, color("`RED'%18") lwidth(none) cmissing(n))  ///
    (line i_p_bls q, lcolor("`RED'") lwidth(0.60) cmissing(n))              ///
    (line i_p_nipa q, lcolor("`INK'") lwidth(0.50) lpattern(dash)           ///
        cmissing(n))                                                        ///
    ,                                                                       ///
    title("{bf:a.} The two indexes, 2015Q1 = 100"                           ///
          "{it:The trade release is deflated with the first; the national accounts use the second}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(95(5)120, angle(0) labsize(vsmall) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(92 123) noextend lcolor(none))                             ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(2 "BLS import price index (gold in, at a two-year-old weight)" ///
                 3 "NIPA goods import price index (gold excluded)")         ///
           rows(2) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(11) ring(0) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(levels, replace) nodraw

twoway                                                                      ///
    (line gap q, lcolor("`INK'") lwidth(0.60) cmissing(n))                  ///
    (line gap_adj q, lcolor("`GREY'") lwidth(0.45) lpattern(dash)           ///
        cmissing(n))                                                        ///
    (line cum_bias q, lcolor("`RED'") lwidth(0.50) cmissing(n))             ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    title("{bf:b.} The gap, and why it is not gold"                         ///
          "{it:Index points. Correcting the BLS index for gold moves it AWAY from NIPA, because the correction raises it}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-8(2)2, angle(0) labsize(vsmall) tlcolor(none)                   ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-9 3) noextend lcolor(none))                               ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "NIPA minus BLS, as published"                           ///
                 2 "NIPA minus BLS, after correcting BLS for gold"          ///
                 3 "The gold correction itself")                            ///
           rows(3) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(7) ring(0) bmargin(zero) color("`SOFT'"))   ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(gappanel, replace) nodraw

graph combine levels gappanel, cols(2) imargin(small)                       ///
    xsize(12.4) ysize(5.6)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:Two import price indexes for the same imports, and the gap between them is not gold}" ///
             "BLS all-commodities against the national accounts' goods index. Since 2015 they have diverged by nearly four index points", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "The BLS index is a Lowe index, chained monthly and reweighted each January from Census annual trade on a two-year lag, and it includes nonmonetary gold at" ///
         "that lagged weight. The NIPA index is chain-Fisher over goods and excludes nonmonetary gold outright. Since 2015Q1 the BLS index has risen 19.2% and the" ///
         "NIPA index 15.5%." ///
         " " ///
         "THE GAP IS NOT GOLD, AND PANEL b IS THERE TO STOP THAT INFERENCE. One index contains gold and the other does not, so the difference looks like it must be" ///
         "gold. It is not, for two independent reasons. First the sign: BLS sits ABOVE NIPA, but the gold correction RAISES the BLS index - it carries gold below the" ///
         "share trade actually had - so correcting for gold moves the two further apart rather than closer. Second the shape: tested directly, the quarterly gap" ///
         "correlates -0.15 with the predicted gold term." ///
         " " ///
         "What the gap is instead is formula and coverage. Lowe with two-year-lagged weights against chain-Fisher will diverge on any basket whose composition moves," ///
         "and MXPI does not price military goods, used goods or art at all. For scale: BEA's own two measures of the same concept - the published chain-type index and" ///
         "the deflator implied by dividing nominal goods imports by chained goods imports - differ from each other by up to 4.2 points over this window, which is the" ///
         "same order as the NIPA-BLS gap. No single-cause story about this gap is safe." ///
         "Source: Bureau of Labor Statistics (EIUIR, EIUIR14270); Bureau of Economic Analysis; US Census Bureau.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/two_import_deflators.pdf", replace
di as txt "wrote $FIG/two_import_deflators.pdf"

capture graph set window fontface "$RESTORE_FONT"
