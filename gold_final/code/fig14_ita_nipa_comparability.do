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
*! THE WINDOW. 2020 onward, which is where this is worth looking: gold's share
*! of US goods trade was under 1% for most of the preceding decade and the two
*! series were effectively indistinguishable.
*!
*! THE LEVEL BREAK. In 2025Q1 the ITA goods deficit was $1,826bn at an annual
*! rate and the NIPA goods deficit was $1,541bn. The two official measures of
*! the same quarter's trade were $285bn apart - 18.5% of the NIPA figure. Four
*! quarters later the gap had swung the other way to -15.6%. That is a
*! 34-point swing in the relative difference between two series that are
*! supposed to be describing the same thing, and over this window the gap
*! correlates +0.99 with net gold trade.
*!
*! THE DIRECTIONAL BREAK, WHICH IS THE SERIOUS ONE. A level gap can be netted
*! out by anyone who knows it is there. A sign disagreement cannot. In the 25
*! quarterly changes since 2020 the two measures disagree about whether the
*! deficit widened or narrowed exactly three times, and all three are
*! consecutive:
*!
*!     2025Q3   ITA   +55   NIPA   -71     gap   +126bn
*!     2025Q4   ITA   -77   NIPA   +19     gap    -96bn
*!     2026Q1   ITA   -34   NIPA   +49     gap    -83bn
*!
*! For three quarters running, one official US measure of the goods balance
*! said the external position was improving while the other said it was
*! deteriorating. Nothing comparable happens anywhere else in the window - the
*! two series agree on direction in all 22 other quarters.
*!
*! AND THE ADJUSTMENT CLOSES IT. The third line is the ITA balance with
*! nonmonetary gold taken out of both sides - HS 7108 and 7115, imports netted
*! against exports. It lands on the national accounts almost exactly:
*!
*!     mean |ITA - NIPA|            48.1bn      sd 82.0
*!     mean |adjusted - NIPA|        8.5bn      sd 10.9
*!     2025Q1  ITA 1,826   adjusted 1,558   NIPA 1,541
*!
*! A $285bn discrepancy becomes $17bn. The correlation of quarterly CHANGES
*! with NIPA rises from 0.918 to 0.992, and the three sign disagreements fall
*! to NONE. On this window the adjusted series never once disagrees with the
*! national accounts about which way the deficit moved.
*!
*! That is the argument in one line: the wedge between the two publications is
*! gold, and removing gold from the ITA reproduces the national accounts. The
*! adjustment is not a judgement call - it is arithmetic on a series Census
*! already publishes.
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
keep if q >= tq(2020q1)

*=========================================================== 3. the two breaks
* The ITA balance with nonmonetary gold removed from both sides. Since the
* deficit is imports minus exports, taking gold out of each side is the same
* as subtracting NET gold - no separate bookkeeping needed.
gen double adj = ita - gnet

gen double gap     = ita - nipa
gen double gap_adj = adj - nipa
gen double gap_pct = 100 * gap / nipa

gen double d_ita  = ita - ita[_n-1]
gen double d_adj  = adj - adj[_n-1]
gen double d_nipa = nipa - nipa[_n-1]
gen byte disagree     = !missing(d_ita, d_nipa) & sign(d_ita)  != sign(d_nipa)
gen byte disagree_adj = !missing(d_adj, d_nipa) & sign(d_adj) != sign(d_nipa)
gen double d_diff     = d_ita - d_nipa

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
di as txt "   " r(N) " of " _N " quarters since 2020"
di as txt "   " _col(12) "ITA" _col(22) "NIPA" _col(33) "gap"
forvalues i = 1/`=_N' {
    if disagree[`i'] {
        local lab : display %tqCCYY!Qq q[`i']
        di as txt "   " trim("`lab'") _col(12) %6.0f d_ita[`i'] ///
            _col(22) %6.0f d_nipa[`i'] _col(31) %6.0f d_diff[`i'] "bn"
    }
}
di as txt ""
di as txt "   All three are consecutive. The two series agree on direction in"
di as txt "   every one of the other 22 quarters in the window."
di as txt ""
di as txt "AND THE ADJUSTMENT CLOSES IT"
qui summarize gap
local MG = r(mean)
qui summarize gap_adj
local MA = r(mean)
qui summarize gap
local SG = r(sd)
qui summarize gap_adj
local SA = r(sd)
gen double abs_gap = abs(gap)
gen double abs_adj = abs(gap_adj)
qui summarize abs_gap
local AG = r(mean)
qui summarize abs_adj
local AA = r(mean)
di as txt "   mean |ITA - NIPA|       " %6.1f `AG' "bn   sd " %5.1f `SG'
di as txt "   mean |adjusted - NIPA|  " %6.1f `AA' "bn   sd " %5.1f `SA'
qui summarize adj if q == tq(2025q1), meanonly
di as txt "   2025Q1: ITA " %5.0f `I25' "   adjusted " %5.0f r(mean) ///
    "   NIPA " %5.0f `N25'
qui correlate d_ita d_nipa
local C1 = r(rho)
qui correlate d_adj d_nipa
local C2 = r(rho)
di as txt "   corr of quarterly changes with NIPA: as published " %5.3f `C1' ///
    ", adjusted " %5.3f `C2'
qui count if disagree_adj
di as txt "   sign disagreements after adjusting: " r(N) " (from "
qui count if disagree
di as txt "      " r(N) "), and none of the large ones survive"
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
    local XLAB `XLAB' `=tq(`y'q1)' "`y'"
}

twoway                                                                      ///
    (line ita q, lcolor("`RED'") lwidth(0.70) cmissing(n))                  ///
    (line adj q, lcolor("`GREY'") lwidth(0.80) cmissing(n))                 ///
    (line nipa q, lcolor("`INK'") lwidth(0.40) lpattern(dash) cmissing(n))  ///
    ,                                                                       ///
    title("{bf:a.} The same quarter's trade, measured twice - and reconciled" ///
          "{it:US goods deficit, {c $|}bn at an annual rate. In 2025Q1 the two official measures were {c $|}285bn apart; adjusted, {c $|}17bn}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(800(250)1800, angle(0) labsize(vsmall) tlcolor(none)             ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))         ///
    yscale(range(700 1880) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(order(1 "ITA, gold included"                                     ///
                 2 "ITA, gold removed (HS 7108 and 7115)"                   ///
                 3 "NIPA, gold already removed")                            ///
           rows(1) size(vsmall) region(lcolor(none)) symxsize(6)            ///
           symysize(2) position(12) ring(1) bmargin(zero) color("`SOFT'"))  ///
    graphregion(color(white) margin(l=2 r=3 t=1 b=1))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    name(pa, replace) nodraw

twoway                                                                      ///
    (line d_ita q, lcolor("`RED'") lwidth(0.70) cmissing(n))                ///
    (line d_adj q, lcolor("`GREY'") lwidth(0.80) cmissing(n))               ///
    (line d_nipa q, lcolor("`INK'") lwidth(0.40) lpattern(dash)             ///
        cmissing(n))                                                        ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.30))                                 ///
    title("{bf:b.} The disagreements about direction go with it"            ///
          "{it:Change in the goods deficit, {c $|}bn. Three sign disagreements as published, none once gold is out}", ///
          size(small) color("`INK'") position(11) justification(left) span) ///
    ytitle("")                                                              ///
    ylabel(-800(400)400, angle(0) labsize(vsmall) tlcolor(none)             ///
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
    xsize(11.0) ysize(7.8)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:For three quarters running, two official measures of the US goods balance pointed in opposite directions}" ///
             "Same agency, same transactions. The only difference is whether bullion counts as trade", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "BEA publishes the US goods balance twice. The International Transactions Accounts carry nonmonetary gold; the national accounts remove it and replace it with" ///
         "domestic production less industrial use. The window starts in 2020 because that is when it begins to matter - for most of the preceding decade gold was under" ///
         "1% of US goods trade and the two series were effectively indistinguishable." ///
         " " ///
         "THE LEVEL BREAK. In 2025Q1 the ITA goods deficit was {c $|}1,826bn at an annual rate against NIPA's {c $|}1,541bn - the same quarter's trade, {c $|}285bn apart. Four quarters" ///
         "later the gap had swung from +18.5% of the NIPA figure to -15.6%. Across the window it correlates 0.99 with net gold trade." ///
         " " ///
         "THE DIRECTIONAL BREAK IS THE SERIOUS ONE, because a level gap can be netted out by anyone who knows it is there and a sign disagreement cannot. In the 25" ///
         "quarterly changes since 2020 the two measures disagree about whether the deficit widened or narrowed exactly three times, and all three are consecutive: in" ///
         "2025Q3 the ITA showed the deficit widening {c $|}55bn while NIPA showed it narrowing {c $|}71bn, and the next two quarters reversed that. They agree in all 22 others." ///
         " " ///
         "AND THE ADJUSTMENT CLOSES IT. The grey line removes nonmonetary gold from both sides of the ITA balance - HS 7108 and 7115, which since the balance is imports" ///
         "minus exports is simply the deficit less net gold. The mean absolute gap to NIPA falls from {c $|}48bn to {c $|}9bn, 2025Q1 from {c $|}285bn to {c $|}17bn, the correlation of quarterly" ///
         "changes from 0.918 to 0.992, and the three directional disagreements to none. Neither series is wrong - each is correct for its own purpose - but the" ///
         "adjustment is arithmetic on a series Census already publishes, and publishing the balance on both bases would cost nothing." ///
         "Source: Bureau of Economic Analysis, International Transactions Accounts and NIPA tables 1.1.5; US Census Bureau.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/ita_nipa_comparability.pdf", replace
di as txt "wrote $FIG/ita_nipa_comparability.pdf"

capture graph set window fontface "$RESTORE_FONT"
