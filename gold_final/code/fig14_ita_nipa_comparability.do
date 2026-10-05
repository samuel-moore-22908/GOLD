*! fig14_ita_nipa_comparability.do
*!
*! Gold broke comparability between the two official measures of the US goods
*! balance - to the point where they disagreed about its DIRECTION.
*!
*! THE SETUP. BEA publishes the US goods balance twice. The International
*! Transactions Accounts carry nonmonetary gold; the national accounts remove
*! it outright and replace it with domestic production less industrial use.
*! In normal times the two differ by very little and nobody has to care which
*! one they are reading. Gold is what makes it matter.
*!
*! THE LEVEL BREAK. In 2025Q1 the ITA goods deficit was $1,826bn at an annual
*! rate and the NIPA goods deficit was $1,541bn. The two official measures of
*! the same quarter's trade were $285bn apart - 18.5% of the NIPA figure. Four
*! quarters later the gap had swung the other way to -15.6%. That is a
*! 34-point swing in the relative difference between two series that are
*! supposed to be describing the same thing, and the gap correlates +0.98 with
*! net gold trade.
*!
*! THE DIRECTIONAL BREAK, WHICH IS THE SERIOUS ONE. A level gap can be netted
*! out by anyone who knows it is there. A sign disagreement cannot. In five
*! quarters since 2015 the two measures disagree about whether the deficit
*! widened or narrowed, and they are not evenly spread:
*!
*!     2016Q2   ITA   +11   NIPA    -6     gap    +17bn
*!     2018Q4   ITA   +12   NIPA    -1     gap    +14bn
*!     2025Q3   ITA   +55   NIPA   -71     gap   +126bn
*!     2025Q4   ITA   -77   NIPA   +19     gap    -96bn
*!     2026Q1   ITA   -34   NIPA   +49     gap    -83bn
*!
*! The two pre-2025 disagreements are rounding - $14bn and $17bn on a deficit
*! above $700bn, the kind of thing that happens when a series is flat. The
*! three since are six to nine times larger and they come in consecutive
*! quarters. For three quarters running, one official US measure of the goods
*! balance said the external position was improving while the other said it
*! was deteriorating.
*!
*! WHY IT MATTERS BEYOND TIDINESS. These are not rival estimates from
*! different agencies with different methods. They are the same agency,
*! measuring the same transactions, differing only in whether bullion counts.
*! Anyone splicing the monthly trade release onto the quarterly accounts,
*! comparing a trade figure to a GDP contribution, or reading across the two
*! publications during 2025 was comparing series that had come apart - and
*! during three quarters would have drawn the opposite conclusion depending on
*! which one they opened.
*!
*! WHAT THIS DOES NOT CLAIM. Not that either series is wrong. NIPA's treatment
*! is deliberate and correct for its purpose, and the ITA's is correct for
*! its own. The claim is that gold is large enough and reverses fast enough to
*! drive a wedge between them that users cannot be expected to carry in their
*! heads - and that the fix is for the trade release to publish the balance on
*! both bases, which costs nothing because BEA already computes the adjustment.
*!
*! Reads   gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/ita_nipa_comparability.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig14_ita_nipa_comparability.do

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

tempfile gold

*================================================================ 1. gold flows
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (sum) v = value_usd, by(m flow)
reshape wide v, i(m) j(flow) string
gen double gnet = (vimports - vexports) / 1e9
keep m gnet
format m %tm
save `gold'

*=================================================== 2. the two official series
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp a255rc1q027sbea a253rc1q027sbea, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
merge 1:1 m using `gold', keep(master match) nogen
sort m

* ITA goods deficit, monthly $mn -> annual rate $bn.
gen double ita_m = (bopgimp - bopgexp) / 1000
* NIPA goods deficit, already $bn SAAR, quarterly (first month of each quarter).
gen double nipa_q = a255rc1q027sbea - a253rc1q027sbea

gen int q = qofd(dofm(m))
format q %tq

* Annualise the ITA from monthly means so a quarter with a missing month is
* not understated, and carry the NIPA quarterly value across.
preserve
    collapse (mean) ita_m gnet (max) nipa_q, by(q)
    replace ita_m = 12 * ita_m
    replace gnet  = 12 * gnet
    rename ita_m ita
    rename nipa_q nipa
    tempfile qq
    save `qq'
restore
use `qq', clear
sort q
drop if missing(ita, nipa)
keep if q >= tq(2015q1)

*=========================================================== 3. the two breaks
gen double gap     = ita - nipa
gen double gap_pct = 100 * gap / nipa

gen double d_ita  = ita - ita[_n-1]
gen double d_nipa = nipa - nipa[_n-1]
gen byte disagree = !missing(d_ita, d_nipa) & sign(d_ita) != sign(d_nipa)
gen double d_diff = d_ita - d_nipa

qui correlate gap gnet
local R_GOLD = r(rho)
qui summarize gap_pct
local PMAX = r(max)
local PMIN = r(min)
qui summarize gap
local GMAX = r(max)
gsort -gap
local GMAXQ : display %tqCCYY!Qq q[1]
local GMAXQ = trim("`GMAXQ'")
sort q

di as txt "{hline 76}"
di as txt "THE LEVEL BREAK"
qui summarize ita if q == tq(2025q1), meanonly
local I25 = r(mean)
qui summarize nipa if q == tq(2025q1), meanonly
local N25 = r(mean)
di as txt "   2025Q1: ITA goods deficit " %6.0f `I25' "bn,  NIPA " %6.0f `N25' "bn"
di as txt "           the two official measures " %5.0f `I25'-`N25' ///
    "bn apart - " %4.1f 100*(`I25'-`N25')/`N25' "% of the NIPA figure"
di as txt "   gap as % of the NIPA deficit: max " %5.1f `PMAX' ///
    "%, min " %5.1f `PMIN' "%  (a " %4.0f `PMAX'-`PMIN' " point swing)"
di as txt "   corr(gap, net gold trade) = " %5.3f `R_GOLD'
di as txt ""
di as txt "THE DIRECTIONAL BREAK - quarters where the two DISAGREE on the sign"
qui count if disagree
di as txt "   " r(N) " of " _N " quarters since 2015"
di as txt "   " _col(12) "ITA" _col(22) "NIPA" _col(33) "gap"
forvalues i = 1/`=_N' {
    if disagree[`i'] {
        local lab : display %tqCCYY!Qq q[`i']
        di as txt "   " trim("`lab'") _col(12) %6.0f d_ita[`i'] ///
            _col(22) %6.0f d_nipa[`i'] _col(31) %6.0f d_diff[`i'] "bn"
    }
}
di as txt ""
di as txt "   The two before 2025 are rounding on a deficit above {c $|}700bn."
di as txt "   The three since are six to nine times larger and consecutive."
di as txt "{hline 76}"

*=========================================================== 4. the two panels
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

* Vertical bands on the quarters where the two series disagree on direction.
* One bar per quarter, floor to ceiling, barwidth(1) = exactly one quarter.
gen double band_a = 1880 if disagree
gen double band_b =  540 if disagree

twoway                                                                      ///
    (bar band_a q, barwidth(1) base(700) color("`GREY'%20") lwidth(none))   ///
    (line ita q, lcolor("`RED'") lwidth(0.70) cmissing(n))                  ///
    (line nipa q, lcolor("`INK'") lwidth(0.55) lpattern(dash) cmissing(n))  ///
    ,                                                                       ///
    title("{bf:a.} The same quarter's trade, measured twice"                ///
          "{it:US goods deficit, {c $|}bn at an annual rate. In 2025Q1 the two official measures were {c $|}285bn apart}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(800(200)1800, angle(0) labsize(vsmall) tlcolor(none)             ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(700 1880) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(2 "ITA - the monthly trade release, gold included"         ///
                 3 "NIPA - the national accounts, gold removed")            ///
           rows(2) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(11) ring(0) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pa, replace) nodraw

twoway                                                                      ///
    (bar band_b q, barwidth(1) base(-830) color("`GREY'%20") lwidth(none))  ///
    (line d_ita q, lcolor("`RED'") lwidth(0.70) cmissing(n))                ///
    (line d_nipa q, lcolor("`INK'") lwidth(0.55) lpattern(dash)             ///
        cmissing(n))                                                        ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.30))                                 ///
    title("{bf:b.} And in five quarters they disagree about which way it moved" ///
          "{it:Change in the goods deficit, {c $|}bn. Shaded: quarters where one says widening and the other narrowing}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-800(200)400, angle(0) labsize(vsmall) tlcolor(none)             ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(-830 540) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(off)                                                             ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pb, replace) nodraw

graph combine pa pb, cols(1) imargin(zero)                                  ///
    xsize(9.8) ysize(7.6)                                                   ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:For three quarters running, two official measures of the US goods balance pointed in opposite directions}" ///
             "Same agency, same transactions. The only difference is whether bullion counts as trade", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "BEA publishes the US goods balance twice: the International Transactions Accounts carry nonmonetary gold, the national accounts remove it and replace it" ///
         "with domestic production less industrial use. In normal times the two barely differ and nobody needs to know which they are reading." ///
         " " ///
         "THE LEVEL BREAK. In 2025Q1 the ITA goods deficit was {c $|}1,826bn at an annual rate against NIPA's {c $|}1,541bn - the same quarter's trade, {c $|}285bn apart, or 18.5% of" ///
         "the NIPA figure. Four quarters later the gap had swung to -15.6%. That is a 34-point swing in the relative difference between two series describing the same" ///
         "thing, and it correlates 0.98 with net gold trade." ///
         " " ///
         "THE DIRECTIONAL BREAK IS THE SERIOUS ONE. A level gap can be netted out by anyone who knows it is there; a sign disagreement cannot. Five quarters since" ///
         "2015 disagree about whether the deficit widened or narrowed, and not evenly. The two before 2025 are rounding - {c $|}17bn and {c $|}14bn on a deficit above" ///
         "{c $|}700bn. The three since are six to nine times larger and consecutive: in 2025Q3 the ITA showed the deficit widening {c $|}55bn while NIPA showed it narrowing {c $|}71bn," ///
         "and the next two quarters reversed that. For three quarters running, one official US measure said the external position was improving while the other said it" ///
         "was deteriorating." ///
         " " ///
         "Neither series is wrong. Each treatment is correct for its own purpose. The claim is that gold is large enough, and reverses fast enough, to drive a wedge" ///
         "between them that users cannot be expected to carry in their heads - and that the remedy costs nothing, because BEA already computes the adjustment. Publishing" ///
         "the goods balance on both bases in the monthly release would let a reader see the wedge at the moment they read the headline." ///
         "Source: Bureau of Economic Analysis, International Transactions Accounts and NIPA tables 1.1.5; US Census Bureau.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/ita_nipa_comparability.pdf", replace
di as txt "wrote $FIG/ita_nipa_comparability.pdf"

capture graph set window fontface "$RESTORE_FONT"
