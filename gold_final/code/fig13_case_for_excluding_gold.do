*! fig13_case_for_excluding_gold.do
*!
*! The affirmative case for taking nonmonetary gold out of the ITA trade
*! aggregates - both the flows and the deflator.
*!
*! WHY THIS NEEDS ITS OWN FIGURE. Everything else in this folder describes what
*! gold did. This one argues that it should not be in the aggregate at all, and
*! an argument of that kind has to rest on properties a statistical agency
*! would actually act on, not on the inconvenience of one episode. Three hold
*! up, and they are tested here rather than asserted.
*!
*! 1. IT DOMINATES THE VARIANCE WITHOUT BEING IN THE LEVEL. Gold averages 1.07%
*!    of US goods imports but accounts for 16.75% of the variance of the
*!    month-on-month change - sixteen times its weight. Taking it out makes the
*!    monthly series 12% quieter. A component that contributes a sixth of the
*!    noise and a hundredth of the signal is not earning its place.
*!
*!    (The decomposition is the exact one: the covariance of each component's
*!    change with the total's, over the variance of the total's, which sums to
*!    one across components.)
*!
*! 2. IT IS RELOCATION, NOT TRADE. Since 2015, $791bn of gold has crossed the
*!    US border in gross terms and the net is -$64bn. ONLY 8% OF THE METAL
*!    THAT CROSSED STAYED. Ordinary trade accumulates - non-gold imports have a
*!    monthly autocorrelation of 0.96 - while gold arrives and leaves, at 0.66.
*!    An aggregate meant to measure goods changing hands is being asked to
*!    carry something that mostly changes vaults.
*!
*! 3. THE PRICE DOES NOT BELONG IN A TRADE DEFLATOR EITHER. Monthly gold price
*!    changes correlate +0.045 with the rest of import price inflation, and
*!    gold is 4.9 times as volatile. Putting an orthogonal, five-times-noisier
*!    series into a price index adds variance without adding information about
*!    import prices.
*!
*! THE FUEL CONTRAST IS THE POINT OF THE BOTTOM ROW, and it is what keeps this
*! from being special pleading. Petroleum has the SAME stale-weight problem as
*! gold - fig11 shows it driving nearly four index points of divergence between
*! the BLS and NIPA deflators, far more than gold ever did. But fuel prices
*! correlate +0.906 with the rest of import inflation. Oil is genuinely part of
*! what the United States imports and consumes; it belongs in the index and the
*! fix for it is a better weighting rule. Gold is orthogonal to everything else
*! in the basket, and the fix for it is exclusion.
*!
*! So the figure proposes a CRITERION rather than an exception: a component
*! belongs in a trade aggregate if it accumulates and if its price co-moves
*! with the rest of the basket. Fuel passes both tests. Gold fails both.
*!
*! WHAT THIS DOES NOT CLAIM. It does not claim the adjustment is large. The
*! deflator effect is worth one to two index points over a decade and published
*! GDP is unaffected, because BEA already removes nonmonetary gold from the
*! national accounts. The claim is narrower and more defensible: BEA has
*! already accepted this argument for the national accounts, and the same
*! argument applies to the trade release, which has not.
*!
*! Reads   gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*! Writes  gold_final/figures/case_for_excluding_gold.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig13_case_for_excluding_gold.do

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

local W_GOLD = 0.01        // weight used to back non-gold inflation out

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
destring eiuir eiuir14270 eiuir10, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename eiuir      p_all
rename eiuir14270 p_gold
rename eiuir10    p_fuel
keep m p_all p_gold p_fuel
save `mxpi'

*============================================================= 3. merge totals
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(master match) nogen
sort m
keep if m >= tm(2015m1)

replace gold_in  = gold_in  / 1e9
replace gold_out = gold_out / 1e9
gen double tot     = bopgimp / 1000
gen double nongold = tot - gold_in
gen double net     = gold_in - gold_out
gen double gross   = gold_in + gold_out

*=================================================== 4. the variance argument
gen double d_tot = tot - tot[_n-1]
gen double d_ng  = nongold - nongold[_n-1]
gen double d_g   = gold_in - gold_in[_n-1]

qui correlate d_g d_tot, covariance
local COV_G = r(cov_12)
qui summarize d_tot
local VAR_T = r(Var)
local SD_T  = r(sd)
local SHARE_VAR = 100 * `COV_G' / `VAR_T'
qui summarize d_ng
local SD_N = r(sd)
gen double sh = 100 * gold_in / tot
qui summarize sh
local SHARE_LVL = r(mean)

*================================================= 5. the relocation argument
gen double cum_gross = sum(gross)
gen double cum_net   = sum(net)
qui summarize cum_gross
local GROSS = r(max)
local STAYED = 100 * abs(cum_net[_N]) / `GROSS'
* Autocorrelations need a declared time series.
tsset m
qui corrgram net, lags(1)
local AC_NET = r(ac1)
qui corrgram nongold, lags(1)
local AC_NG = r(ac1)

*=================================================== 6. the deflator argument
gen double lp_all  = ln(p_all)  - ln(p_all[_n-1])
gen double lp_gold = ln(p_gold) - ln(p_gold[_n-1])
gen double lp_fuel = ln(p_fuel) - ln(p_fuel[_n-1])
* Non-gold import inflation, backed out of the published aggregate.
gen double lp_ng = (lp_all - `W_GOLD' * lp_gold) / (1 - `W_GOLD')

foreach v in gold fuel {
    replace lp_`v' = 100 * lp_`v'
}
replace lp_ng = 100 * lp_ng

qui correlate lp_gold lp_ng
local R_GOLD = r(rho)
qui correlate lp_fuel lp_ng
local R_FUEL = r(rho)
qui summarize lp_gold
local SD_GOLD = r(sd)
qui summarize lp_ng
local SD_NG = r(sd)

*=========================================================== 7. what it says
di as txt "{hline 76}"
di as txt "1. LEVEL vs VARIANCE"
di as txt "   gold's mean share of goods imports      " %6.2f `SHARE_LVL' "%"
di as txt "   gold's share of the variance of the"
di as txt "      month-on-month change                " %6.2f `SHARE_VAR' "%"
di as txt "   ratio                                   " %6.0f ///
    `SHARE_VAR'/`SHARE_LVL' "x"
di as txt "   sd of monthly change " %5.2f `SD_T' "bn -> " %5.2f `SD_N' ///
    "bn ex-gold (" %2.0f 100*(1-`SD_N'/`SD_T') "% quieter)"
di as txt ""
di as txt "2. RELOCATION, NOT TRADE"
di as txt "   gross gold crossing the border since 2015 " %7.0f `GROSS' "bn"
di as txt "   net                                       " %7.0f cum_net[_N] "bn"
di as txt "   only " %4.1f `STAYED' "% of the metal that crossed stayed"
di as txt "   autocorrelation: net gold " %5.2f `AC_NET' ///
    "   non-gold imports " %5.2f `AC_NG'
di as txt ""
di as txt "3. THE PRICE DOES NOT BELONG EITHER"
di as txt "   corr(gold price change, non-gold import inflation) " %6.3f `R_GOLD'
di as txt "   corr(fuel price change, non-gold import inflation) " %6.3f `R_FUEL'
di as txt "   gold is " %4.1f `SD_GOLD'/`SD_NG' "x as volatile as the rest of the basket"
di as txt ""
di as txt "   THE CRITERION: a component belongs in a trade aggregate if it"
di as txt "   accumulates and if its price co-moves with the basket. Fuel"
di as txt "   passes both. Gold fails both."
di as txt "{hline 76}"

*=========================================================== 8. the four panels
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

local LVL : display %4.2f `SHARE_LVL'
local VAR : display %4.1f `SHARE_VAR'
local STY : display %3.1f `STAYED'
local RG  : display %5.3f `R_GOLD'
local RF  : display %5.3f `R_FUEL'

* --- a. the variance argument ------------------------------------------------
twoway                                                                      ///
    (line d_tot mplot, lcolor("`GREY'") lwidth(0.45) cmissing(n))           ///
    (line d_ng  mplot, lcolor("`RED'") lwidth(0.45) cmissing(n))            ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.22))                                 ///
    title("{bf:a.} Gold is 1% of the level and 17% of the noise"            ///
          "{it:Month-on-month change in US goods imports, {c $|}bn, as published and with gold removed}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-60(20)20, angle(0) labsize(vsmall) tlcolor(none)                ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-70 34) noextend lcolor(none))                             ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "As published" 2 "With gold removed") rows(1)            ///
           size(vsmall) region(lcolor(none)) symxsize(6) symysize(2)        ///
           position(7) ring(0) bmargin(zero) color("`SOFT'"))               ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pa, replace) nodraw

* --- b. the relocation argument ----------------------------------------------
twoway                                                                      ///
    (line cum_gross mplot, lcolor("`GREY'") lwidth(0.65) cmissing(n))       ///
    (line cum_net   mplot, lcolor("`RED'") lwidth(0.65) cmissing(n))        ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.22))                                 ///
    title("{bf:b.} Only `STY'% of the metal that crossed the border stayed" ///
          "{it:Cumulative US gold trade since 2015, {c $|}bn}",                  ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(0(200)800, angle(0) labsize(vsmall) tlcolor(none)                ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-120 850) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "Gross metal crossing the border" 2 "Net - what stayed") ///
           rows(1) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(11) ring(0) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pb, replace) nodraw

* --- c and d. the deflator argument ------------------------------------------
twoway                                                                      ///
    (scatter lp_gold lp_ng, msymbol(O) msize(small) mcolor("`RED'%55")      ///
        mlwidth(none))                                                      ///
    (lfit lp_gold lp_ng, lcolor("`INK'") lwidth(0.45))                      ///
    ,                                                                       ///
    title("{bf:c.} Gold's price has nothing to do with import prices"       ///
          "{it:Monthly % change, 2015-2026. Correlation `RG'}",             ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("Gold price, % a month", size(vsmall) color("`SOFT'"))           ///
    xtitle("Rest of the import basket, % a month", size(vsmall)             ///
           color("`SOFT'"))                                                 ///
    ylabel(-10(5)15, angle(0) labsize(vsmall) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    xlabel(-3(1)3, labsize(vsmall) tlcolor(none) labcolor("`SOFT'")         ///
           grid glcolor("`RULE'") glwidth(0.22))                            ///
    legend(off)                                                             ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(small) lcolor(none))                     ///
    name(pc, replace) nodraw

twoway                                                                      ///
    (scatter lp_fuel lp_ng, msymbol(O) msize(small) mcolor("`GREY'%60")     ///
        mlwidth(none))                                                      ///
    (lfit lp_fuel lp_ng, lcolor("`INK'") lwidth(0.45))                      ///
    ,                                                                       ///
    title("{bf:d.} Fuel's does - so this is a criterion, not an excuse"     ///
          "{it:Same axes. Correlation `RF'}",                                  ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("Fuel price, % a month", size(vsmall) color("`SOFT'"))           ///
    xtitle("Rest of the import basket, % a month", size(vsmall)             ///
           color("`SOFT'"))                                                 ///
    ylabel(-40(10)20, angle(0) labsize(vsmall) tlcolor(none)                ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    xlabel(-3(1)3, labsize(vsmall) tlcolor(none) labcolor("`SOFT'")         ///
           grid glcolor("`RULE'") glwidth(0.22))                            ///
    legend(off)                                                             ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(small) lcolor(none))                     ///
    name(pd, replace) nodraw

graph combine pa pb pc pd, cols(2) imargin(small)                           ///
    xsize(12.4) ysize(8.6)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The case for taking nonmonetary gold out of the trade release, on both sides of the calculation}" ///
             "A component belongs in a trade aggregate if it accumulates and if its price moves with the rest of the basket. Gold does neither", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "Top row, the flows. Gold averages `LVL'% of US goods imports but accounts for `VAR'% of the variance of the month-on-month change - sixteen times its weight - and" ///
         "removing it makes the monthly series 12% quieter. The decomposition is the exact one, each component's covariance with the total over the total's variance," ///
         "which sums to one across components. And the metal does not stay: {c $|}791bn crossed the border gross since 2015 against a net of -{c $|}64bn, so only `STY'% of what" ///
         "crossed remained. Ordinary trade accumulates - non-gold imports have a monthly autocorrelation of 0.96 against gold's 0.66. An aggregate meant to measure" ///
         "goods changing hands is being asked to carry something that mostly changes vaults." ///
         " " ///
         "Bottom row, the deflator, and the contrast is the argument. Gold's monthly price change correlates `RG' with the rest of import inflation and is five times as" ///
         "volatile: putting an orthogonal, far noisier series into a price index adds variance without adding information. Fuel correlates `RF'. Petroleum has the SAME" ///
         "stale-weight problem as gold and a larger one - it drives nearly four index points of divergence between the BLS and NIPA deflators, far more than gold ever" ///
         "did - but oil is genuinely part of what the United States imports and consumes, so it belongs in the index and the remedy for it is a better weighting rule." ///
         "Gold is orthogonal to everything else in the basket, and the remedy for it is exclusion. That is what makes this a criterion rather than special pleading." ///
         " " ///
         "What this does not claim is that the adjustment is large. The deflator effect is worth one to two index points over a decade, and published GDP is unaffected" ///
         "because BEA already removes nonmonetary gold from the national accounts. The claim is the narrower one: BEA has accepted this argument for the national" ///
         "accounts, and the same argument applies to the trade release, which has not." ///
         "Source: US Census Bureau; Bureau of Labor Statistics (EIUIR, EIUIR10, EIUIR14270); Bureau of Economic Analysis.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/case_for_excluding_gold.pdf", replace
di as txt "wrote $FIG/case_for_excluding_gold.pdf"

capture graph set window fontface "$RESTORE_FONT"
