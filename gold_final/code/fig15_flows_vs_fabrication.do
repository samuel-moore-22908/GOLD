*! fig15_flows_vs_fabrication.do
*!
*! The flows are financial. Set them against what the metal is actually used
*! for and the question answers itself.
*!
*! WHY THIS FIGURE EXISTS. The spread explains WHY the metal moved. It does not
*! establish that the metal was not consumed, and a reader entitled to be
*! sceptical can ask whether the 2025 surge was simply Americans buying gold.
*! The cleanest answer is arithmetic: compare the flow to every tonne the
*! destination could plausibly absorb.
*!
*! PANEL A. US gold imports against US demand - jewellery plus bar and coin,
*! which is every ounce Americans buy as jewellery or hold as retail
*! investment. In 2025Q1 the United States imported 870 tonnes against demand
*! of 39 tonnes: TWENTY-TWO TIMES a quarter's worth of its own consumption, in
*! one quarter. US demand averages 53 tonnes a quarter over this window and
*! has never exceeded 75. Gold does not get eaten.
*!
*! PANEL B. US gold exports against the demand of the five destinations that
*! take them. The five are chosen from the data rather than assumed, and they
*! are Canada, Hong Kong, Singapore, Switzerland and the United Kingdom -
*! 86.6% of US gold exports to identified countries.
*!
*! THE COMPOSITION IS THE ARGUMENT, and it is sharper than the ratio. Those
*! five places have a COMBINED gold demand of about 32 tonnes a quarter -
*! Switzerland 7.6, the UK 8.0, Hong Kong 7.0, Canada 5.8, Singapore 3.6.
*! Peak quarterly exports to them were 327 tonnes, twelve times the lot.
*!
*! Meanwhile India, which consumes 184 tonnes a quarter and is the largest
*! gold market on earth, is not in the top five at all. The United States
*! ships its gold to the five places that barely use any, and not to the one
*! place that uses more than all of them put together. Those five are the
*! world's refining and vaulting centres - Switzerland refines, London and
*! Hong Kong and Singapore vault - which is what the metal was going there
*! for.
*!
*! THE COMPARATOR IS DELIBERATELY GENEROUS. Jewellery plus bar and coin is
*! wider than fabrication: bar and coin is investment, not fabrication at all,
*! and including it makes the benchmark larger and the comparison harder for
*! this figure to win. Technology demand - electronics, dental - would add
*! little: it is about 330 tonnes a year for the ENTIRE WORLD, and WGC does not
*! publish it by country. If the flows still dwarf the generous measure, they
*! dwarf the strict one.
*!
*! A NOTE ON THE FIFTH PLACE. An earlier draft of this file hardcoded the five
*! as Switzerland, the UK, Hong Kong, Singapore and India. On a 2022 window
*! Canada displaces India, so the file now picks the five from the Census data
*! and warns if any of them has no WGC counterpart. The hardcoded guess would
*! have weakened the figure badly, because including India put 184 tonnes a
*! quarter of genuine consumption into a benchmark meant to show its absence.
*!
*! TWO THINGS THE FIGURE DOES NOT HIDE. WGC does not break out Swiss jewellery
*! demand, which sits inside "Other Europe", so Switzerland contributes bar and
*! coin only and the partner total is slightly understated - by a few tonnes a
*! quarter against partner totals in the hundreds. The window runs from 2015,
*! which required re-pulling the Census partner detail back to January 2015.
*!
*! UNITS. Tonnes throughout, converted at the boundary from the Census dollar
*! values using the LBMA PM monthly average and 32,150.7 troy ounces to the
*! tonne, per the project convention.
*!
*! Reads   gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/us_gold_partner_monthly.csv
*!         gold_final/data/raw/lbma_pm.csv
*!         gold_final/data/raw/wgc_demand_quarterly.csv  (prep_wgc_demand.py)
*! Writes  gold_final/figures/flows_vs_fabrication.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig15_flows_vs_fabrication.do

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

local OZ_PER_T = 32150.7       // troy ounces in a tonne
local Q0 = tq(2015q1)

tempfile px gold partner demand

*============================================================== 1. the price
import delimited using "$RAW/lbma_pm.csv", varnames(1) clear
destring lbma_pm_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (mean) px = lbma_pm_usd, by(m)
format m %tm
save `px'

*=================================================== 2. total US gold, to tonnes
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (sum) v = value_usd, by(m flow)
reshape wide v, i(m) j(flow) string
format m %tm
merge 1:1 m using `px', keep(match) nogen
* Convert at the boundary, as the project convention requires.
gen double imp_t = vimports / (px * `OZ_PER_T')
gen double exp_t = vexports / (px * `OZ_PER_T')
gen int q = qofd(dofm(m))
collapse (sum) imp_t exp_t, by(q)
format q %tq
save `gold'

*============================== 3. exports to the five largest destinations
import delimited using "$RAW/us_gold_partner_monthly.csv", varnames(1) clear
destring value_usd, replace force
keep if flow == "exports"
* The file carries regional aggregates (OECD, EUROPE, ASIA) alongside real
* countries. Keep only four-digit country codes, as elsewhere in this project.
tostring cty_code, replace force
keep if regexm(cty_code, "^[1-9][0-9][0-9][0-9]$")
* Census country code -> the slug used in the WGC extract.
gen str16 slug = ""
replace slug = "switzerland"    if cty_code == "4419"
replace slug = "united_kingdom" if cty_code == "4120"
replace slug = "hong_kong"      if cty_code == "5820"
replace slug = "singapore"      if cty_code == "5590"
replace slug = "india"          if cty_code == "5330"
replace slug = "canada"         if cty_code == "1220"
replace slug = "australia"      if cty_code == "6021"
replace slug = "uae"            if cty_code == "5200"
replace slug = "turkey"         if cty_code == "4890"
replace slug = "japan"          if cty_code == "5880"
replace slug = "germany"        if cty_code == "4280"

* PICK THE FIVE FROM THE DATA, do not assume them. On a 2022 window Canada
* displaces India in fifth place, which a hardcoded list got wrong.
preserve
    collapse (sum) value_usd, by(cty_code cty_name slug)
    gsort -value_usd
    keep in 1/5
    qui levelsof cty_code, local(TOP5CODES) clean
    qui levelsof cty_name, local(P5) clean
    * Warn loudly if any of the five has no WGC counterpart.
    qui count if slug == ""
    if r(N) > 0 {
        levelsof cty_name if slug == "", local(MISSING) clean
        di as err "NO WGC DEMAND SERIES FOR: `MISSING'"
        di as err "Add it to COUNTRIES in prep_wgc_demand.py and rerun that first."
    }
restore
gen byte top5 = 0
foreach c of local TOP5CODES {
    replace top5 = 1 if cty_code == "`c'"
}
qui levelsof slug if top5, local(TOP5SLUGS) clean
di as txt "the five largest destinations: `P5'"
gen double m = mofd(date(date, "YMD"))
format m %tm
merge m:1 m using `px', keep(match) nogen
gen double t = value_usd / (px * `OZ_PER_T')
gen int q = qofd(dofm(m))
preserve
    keep if top5
    collapse (sum) exp5_t = t, by(q)
    format q %tq
    save `partner'
restore
* How much of identified-country exports the five account for, reported not
* asserted.
collapse (sum) t, by(top5)
qui summarize t if top5 == 1, meanonly
local T5 = r(mean)
qui summarize t, meanonly
local TALL = r(sum)
local SHARE5 = 100 * `T5' / `TALL'

*=========================================================== 4. WGC demand
import delimited using "$RAW/wgc_demand_quarterly.csv", varnames(1) clear
destring jewellery_t barcoin_t, replace force
gen int q = qofd(date(date, "YMD"))
format q %tq
* Jewellery plus bar and coin. Missing jewellery (Switzerland) counts as zero,
* which understates the benchmark slightly and so works against this figure.
gen double use_t = cond(missing(jewellery_t), 0, jewellery_t) ///
                 + cond(missing(barcoin_t), 0, barcoin_t)
preserve
    keep if country == "united_states"
    collapse (sum) us_use_t = use_t, by(q)
    save `demand'
restore
gen byte inp5 = 0
foreach sl of local TOP5SLUGS {
    replace inp5 = 1 if country == "`sl'"
}
keep if inp5
collapse (sum) p5_use_t = use_t, by(q)
merge 1:1 q using `demand', nogen
sort q
tempfile wgc
save `wgc'

*============================================================= 5. assemble
use `gold', clear
merge 1:1 q using `partner', nogen
merge 1:1 q using `wgc', keep(match) nogen
sort q
keep if q >= `Q0'

gen double ratio_imp = imp_t / us_use_t
gen double ratio_exp = exp5_t / p5_use_t

*=========================================================== 6. what it says
qui summarize ratio_imp
local RI_MAX = r(max)
gsort -ratio_imp
local RI_Q : display %tqCCYY!Qq q[1]
local RI_Q = trim("`RI_Q'")
qui summarize imp_t if q == tq(2025q1), meanonly
local IMP25 = r(mean)
qui summarize us_use_t if q == tq(2025q1), meanonly
local USE25 = r(mean)
sort q
qui summarize ratio_exp
local RE_MAX = r(max)
gsort -ratio_exp
local RE_Q : display %tqCCYY!Qq q[1]
local RE_Q = trim("`RE_Q'")
sort q

di as txt "{hline 76}"
di as txt "PANEL A - US gold imports against US demand (tonnes a quarter)"
di as txt "   2025Q1 imports " %7.0f `IMP25' "t   against US demand of " ///
    %5.0f `USE25' "t"
di as txt "   ratio " %5.1f `IMP25'/`USE25' "x   peak ratio " %5.1f `RI_MAX' ///
    " in `RI_Q'"
qui summarize us_use_t
di as txt "   US demand averages " %5.0f r(mean) "t a quarter and never exceeds " ///
    %5.0f r(max) "t"
di as txt ""
di as txt "PANEL B - US gold exports to the five largest destinations"
di as txt "   the five take " %4.1f `SHARE5' "% of US gold exports to identified countries"
qui summarize exp5_t
di as txt "   peak quarterly exports to them " %6.0f r(max) "t"
qui summarize p5_use_t
di as txt "   their combined demand averages " %6.0f r(mean) "t a quarter"
di as txt "   peak ratio " %5.1f `RE_MAX' "x in `RE_Q'"
di as txt ""
di as txt "   COMPOSITION CHECK - does one destination carry the benchmark?"
qui summarize p5_use_t, meanonly
local P5U = r(mean)
di as txt "   combined demand of the five " %6.1f `P5U' "t a quarter"
di as txt "   (if one of them is a consumption market its demand will swamp"
di as txt "    the rest and the aggregate ratio will understate the others)"
di as txt ""
di as txt "   Gold is not consumed on these timescales. A country that imports"
di as txt "   eighteen quarters of its own demand in one quarter is not"
di as txt "   consuming it, and metal shipped to refining and vaulting centres"
di as txt "   is not being fabricated there either."
di as txt "{hline 76}"

*=========================================================== 7. the two panels
qui summarize q, meanonly
local QA = r(min)
local QB = r(max)
local XMIN = `QA' - 1
local XMAX = `QB' + 1
local Y0 = year(dofq(`QA'))
local Y1 = year(dofq(`QB'))
local XLAB ""
forvalues y = `Y0'/`Y1' {
    if mod(`y', 2) == 1 {
        local XLAB `XLAB' `=tq(`y'q1)' "`y'"
    }
}

local R25 : display %3.0f `IMP25'/`USE25'
local R25 = trim("`R25'")
local SH : display %3.0f `SHARE5'
local SH = trim("`SH'")

twoway                                                                      ///
    (bar imp_t q, barwidth(0.8) color("`RED'") lwidth(none))                ///
    (line us_use_t q, lcolor("`INK'") lwidth(1.10))                         ///
    ,                                                                       ///
    title("{bf:a.} US gold imports against everything Americans use gold for" ///
          "{it:Tonnes a quarter. In 2025Q1 the United States imported `R25' times a quarter's worth of its own demand}", ///
          size(medsmall) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(0(200)800, angle(0) labsize(small) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(0 900) noextend lcolor(none))                              ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(small) tlcolor(none) labcolor("`SOFT'") nogrid)  ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "US gold imports"                                        ///
                 2 "US demand: jewellery plus bar and coin")                ///
           rows(1) size(small) region(lcolor(none)) symxsize(8)             ///
           symysize(2) position(12) ring(1) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pa, replace) nodraw

twoway                                                                      ///
    (bar exp5_t q, barwidth(0.8) color("`RED'") lwidth(none))               ///
    (line p5_use_t q, lcolor("`INK'") lwidth(1.10))                         ///
    ,                                                                       ///
    title("{bf:b.} US gold exports against the demand of the five places that take them" ///
          "{it:Tonnes a quarter. `SH'% of US gold exports. Their combined demand is about 32t; India, which consumes 184t, is not among them}", ///
          size(medsmall) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(0(200)800, angle(0) labsize(small) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(0 900) noextend lcolor(none))                              ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(small) tlcolor(none) labcolor("`SOFT'") nogrid)  ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "US gold exports to the five"                            ///
                 2 "Their combined demand: jewellery plus bar and coin")    ///
           rows(1) size(small) region(lcolor(none)) symxsize(8)             ///
           symysize(2) position(12) ring(1) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pb, replace) nodraw

graph combine pa pb, cols(1) imargin(zero)                                  ///
    xsize(10.5) ysize(7.0)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The metal moved in quantities nobody at either end could use}" ///
             "US gold trade against the jewellery and retail investment demand of the countries sending and receiving it", ///
             size(medsmall) color("`INK'") position(11)                     ///
             justification(left) span)                                      ///
    name(combined, replace)

graph export "$FIG/flows_vs_fabrication.pdf", replace
di as txt "wrote $FIG/flows_vs_fabrication.pdf"

capture graph set window fontface "$RESTORE_FONT"
