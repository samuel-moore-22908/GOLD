*! fig5_deflator_gold.do
*!
*! Can the import price index see the gold?
*!
*! THE QUESTION. Real monthly trade is nominal trade divided by a price index.
*! The index BLS publishes, and that anyone deflating trade data reaches for, is
*! a modified LASPEYRES: fixed base-period quantities. BLS does sample
*! nonmonetary gold, so gold is in the basket - the naive version of this
*! worry, that gold is missing from the index, is wrong. The problem is the
*! WEIGHT, not the coverage. A fixed-weight index carries gold at roughly its
*! base-period share of trade, and gold's actual share went from about half a
*! percent before 2020 to ten and a half percent in January 2025.
*!
*! THE ARITHMETIC is the standard index-number decomposition. If a component
*! sits at current share s_t but is weighted at w_base, the published inflation
*! rate misses
*!
*!     pi_adjusted - pi_published = (s_t - w_base) * (pi_gold - pi_nongold)
*!
*! with pi_nongold backed out of the published index given w_base. The term is
*! the share gap times the inflation differential, and it is zero whenever
*! either is zero - which is why it did not matter before 2020.
*!
*! WHAT IS AND IS NOT AFFECTED. BEA removes nonmonetary gold from the NATIONAL
*! ACCOUNTS outright, so published GDP is not deflated through this index and
*! is not exposed. What is exposed is anything that deflates gold-inclusive
*! nominal trade: real trade series built from the trade release, and nowcasts
*! bridging from it. That is not hypothetical. The Atlanta Fed's own model
*! documentation says it discards the advance report's industrial supplies and
*! materials category outright because it "does not disentangle either the
*! Census-basis measure of nonmonetary gold or finished metal shapes from the
*! sub aggregate", and forecasts the gap with a separate BVAR instead.
*!
*! w_base IS AN ASSUMPTION. BLS does not publish the gold weight inside the
*! all-commodities index, and it depends on their weight reference period. Two
*! values are run, 0.5% and 1.0%, which bracket gold's pre-2020 trade share.
*! The conclusion does not turn on the choice: the cumulative correction is
*! 2.0% at the first and 1.6% at the second.
*!
*! Reads   gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/lbma_pm.csv
*! Writes  gold_final/figures/deflator_gold.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig5_deflator_gold.do

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
graph set window fontface "Arial Narrow"

local RED  "227 18 11"
local INK  "18 18 18"
local GREY "117 141 153"
local RULE "224 228 231"
local SOFT "112 112 112"

local WBASE  = 0.005        // assumed weight on gold in the published index
local WBASE2 = 0.010        // the alternative, for the sensitivity line
local BASE_M = tm(2020m1)   // indices rebased here, the start of the COVID era

tempfile px gold

*================================================================= 1. the price
import delimited using "$RAW/lbma_pm.csv", varnames(1) clear
destring lbma_pm_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (mean) px = lbma_pm_usd, by(m)
format m %tm
save `px'

*============================================================== 2. gold imports
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
keep if flow == "imports"
gen double m = mofd(date(date, "YMD"))
format m %tm
collapse (sum) gold_usd = value_usd, by(m)
save `gold'

*======================================================= 3. indexes and totals
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring ir iq bopgimp bopgexp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m ir bopgimp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `px', keep(match) nogen
sort m

* BOPGIMP is $ millions; the Census gold pull is dollars.
gen double share = gold_usd / (bopgimp * 1e6)

*=========================================================== 4. the correction
gen double pi_pub  = ln(ir) - ln(ir[_n-1])
gen double pi_gold = ln(px) - ln(px[_n-1])

* Non-gold inflation implied by the published index, then the correction. Done
* twice so the sensitivity to the assumed base weight is visible rather than
* asserted.
foreach w in `WBASE' `WBASE2' {
    local tag = string(`w' * 1000)
    gen double pi_ng`tag'   = (pi_pub - `w' * pi_gold) / (1 - `w')
    gen double corr`tag'    = (share - `w') * (pi_gold - pi_ng`tag')
    gen double pi_adj`tag'  = pi_pub + corr`tag'
}

* Cumulate both into indexes rebased to the common base month.
sort m
foreach v in pub adj5 adj10 {
    local src = cond("`v'" == "pub", "pi_pub", "pi_`v'")
}
gen double c_pub = sum(cond(m > `BASE_M', pi_pub, 0))
gen double c_adj = sum(cond(m > `BASE_M', pi_adj5, 0))
gen double c_ad2 = sum(cond(m > `BASE_M', pi_adj10, 0))
gen double i_pub = 100 * exp(c_pub)
gen double i_adj = 100 * exp(c_adj)
gen double i_ad2 = 100 * exp(c_ad2)

*=========================================================== 5. what it says
qui summarize share if m >= tm(2015m1) & m <= tm(2019m12), meanonly
local S_PRE = 100 * r(mean)
qui summarize share if m >= tm(2020m1), meanonly
local S_POST = 100 * r(mean)
qui summarize share, meanonly
local S_MAX = 100 * r(max)
gsort -share
local S_MAX_M : display %tmMonth_CCYY m[1]
local S_MAX_M = trim("`S_MAX_M'")
sort m

qui summarize corr5 if m <= tm(2019m12)
local C_PRE = 100 * r(mean)
qui summarize corr5 if m >= tm(2024m1)
local C_POST = 100 * r(mean)
qui summarize i_pub if m == `=tm(2026m7)', meanonly
local I_PUB = r(mean)
qui summarize i_adj if m == `=tm(2026m7)', meanonly
local I_ADJ = r(mean)
local WEDGE = `I_ADJ' - `I_PUB'
local SHARE_OF = 100 * `WEDGE' / (`I_PUB' - 100)

* The single clearest month: gold's share times its own price move, against
* what the whole index did.
qui summarize share if m == `=tm(2025m2)', meanonly
local F_S = 100 * r(mean)
qui summarize pi_gold if m == `=tm(2025m2)', meanonly
local F_G = 100 * r(mean)
qui summarize pi_pub if m == `=tm(2025m2)', meanonly
local F_P = 100 * r(mean)
local F_CONTRIB = `F_S' * `F_G' / 100

di as txt "{hline 70}"
di as txt "gold's share of US goods imports"
di as txt "   2015-2019 mean : " %6.2f `S_PRE' "%"
di as txt "   2020 onward    : " %6.2f `S_POST' "%"
di as txt "   peak           : " %6.2f `S_MAX' "% in `S_MAX_M'"
di as txt ""
di as txt "monthly correction to the published index, w_base = " %4.1f 100*`WBASE' "%"
di as txt "   to 2019        : " %6.3f `C_PRE' "% a month"
di as txt "   2024 onward    : " %6.3f `C_POST' "% a month"
di as txt ""
di as txt "index rebased to 100 at Jan 2020, latest reading"
di as txt "   published      : " %6.1f `I_PUB'
di as txt "   gold-reweighted: " %6.1f `I_ADJ'
di as txt "   wedge          : " %6.1f `WEDGE' " points, " %4.0f `SHARE_OF' ///
    "% of the measured rise"
di as txt ""
di as txt "February 2025, the clearest single month:"
di as txt "   gold was " %5.2f `F_S' "% of imports and rose " %5.2f `F_G' "%,"
di as txt "   so it alone should have added " %5.2f `F_CONTRIB' " points."
di as txt "   The whole index moved " %5.2f `F_P' "%."
di as txt "{hline 70}"

*=========================================================== 6. the figure
qui summarize m if !missing(share), meanonly
local M0 = r(min)
local M1 = r(max)
local Y0 = year(dofm(`M0'))
local Y1 = year(dofm(`M1'))
local XLAB `=tm(`Y0'm1)'(24)`=tm(`Y1'm1)'
local XMIN = `M0' - 2
local XMAX = `M1' + 2

gen double share_pct = 100 * share
gen double mplot = m + 0.5          // a month is an interval; centre it

twoway                                                                      ///
    (bar share_pct mplot if m <  tm(2020m1), barwidth(0.85)                 ///
        color("`GREY'") lwidth(none))                                       ///
    (bar share_pct mplot if m >= tm(2020m1), barwidth(0.85)                 ///
        color("`RED'") lwidth(none))                                        ///
    ,                                                                       ///
    yline(`S_PRE', lcolor("`INK'") lwidth(0.22) lpattern(shortdash))        ///
    title("Gold's share of US goods imports", size(medsmall)                ///
          color("`INK'") position(11) justification(left))                  ///
    subtitle("Per cent of the monthly total, by value. The dashed line is the 2015-19 mean, `=string(`S_PRE', "%3.2f")'%", ///
             size(vsmall) color("`SOFT'") position(11) justification(left)) ///
    ytitle("Per cent of goods imports", size(vsmall) color("`SOFT'"))       ///
    ylabel(0(2)10, angle(0) labsize(vsmall) tlcolor(none)                   ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xscale(range(`XMIN' `XMAX') noextend)                                   ///
    legend(off)                                                             ///
    graphregion(color(white) lcolor(white)) plotregion(lstyle(none))        ///
    name(gShare, replace) nodraw

twoway                                                                      ///
    (rarea i_pub i_adj mplot if m >= `BASE_M', color("`RED'%20")            ///
        lwidth(none))                                                       ///
    (line i_pub mplot if m >= `BASE_M', lcolor("`GREY'") lwidth(0.55))      ///
    (line i_ad2 mplot if m >= `BASE_M', lcolor("`INK'") lwidth(0.25)        ///
        lpattern(dot))                                                      ///
    (line i_adj mplot if m >= `BASE_M', lcolor("`RED'") lwidth(0.55))       ///
    ,                                                                       ///
    title("The import price index, as published and reweighted for gold",   ///
          size(medsmall) color("`INK'") position(11) justification(left))   ///
    subtitle("January 2020 = 100. Reweighting puts gold at its actual monthly share instead of its base-period one", ///
             size(vsmall) color("`SOFT'") position(11) justification(left)) ///
    ytitle("Index, Jan 2020 = 100", size(vsmall) color("`SOFT'"))           ///
    ylabel(, angle(0) labsize(vsmall) tlcolor(none) labcolor("`SOFT'")      ///
           grid glcolor("`RULE'") glwidth(0.28))                            ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xscale(range(`XMIN' `XMAX') noextend)                                   ///
    legend(order(2 "As published" 4 "Gold at its current share (w = 0.5%)"  ///
                 3 "Same, w = 1.0%")                                        ///
           position(11) ring(0) cols(1) region(lstyle(none) color(none))    ///
           size(vsmall) symxsize(7) color("`SOFT'"))                        ///
    graphregion(color(white) lcolor(white)) plotregion(lstyle(none))        ///
    name(gIdx, replace) nodraw

graph combine gShare gIdx, cols(1) imargin(small) iscale(*0.95)             ///
    graphregion(color(white) lcolor(white))                                 ///
    title("███", size(vsmall) color("`RED'")                                ///
          position(11) justification(left))                                 ///
    subtitle("{bf:A fixed-weight index cannot see a component whose share moved twentyfold}" ///
             "Gold is in the import price index, but at roughly its base-period weight." ///
             "Its actual share of US goods imports reached `=string(`S_MAX', "%4.1f")'% in `S_MAX_M'. Reweighting it at" ///
             "the share it actually had adds `=string(`WEDGE', "%3.1f")' points to import price inflation since 2020", ///
             size(medsmall) color("`INK'") position(11) justification(left)) ///
    note("The correction is the standard index-number term (s_t - w_base) x (gold inflation - non-gold inflation), with non-gold inflation backed out of the published" ///
         "index given w_base. BLS does not publish the gold weight, so two values bracketing its pre-2020 trade share are shown. This does NOT affect published GDP:" ///
         "BEA removes nonmonetary gold from the national accounts, so they are not deflated through this index. It affects real trade series built from the trade" ///
         "release, and nowcasts bridging from them" ///
         " "                                                                ///
         "Source: Bureau of Labor Statistics; US Census Bureau; Bureau of Economic Analysis; LBMA", ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    name(gPanel, replace) xsize(11) ysize(8.2)

cap mkdir "$FIG"
graph export "$FIG/deflator_gold.pdf", replace name(gPanel)
di as txt "wrote $FIG/deflator_gold.pdf"

if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
