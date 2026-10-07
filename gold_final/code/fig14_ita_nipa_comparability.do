*! fig14_ita_nipa_comparability.do
*!
*! The same trade, measured twice - imports in one panel, exports in the other.
*!
*! THE SETUP. BEA publishes US goods trade twice. The International
*! Transactions Accounts, which underlie the monthly trade release, count
*! nonmonetary gold as a good - correctly, under BPM6. The national accounts
*! remove it outright and replace it with domestic production less industrial
*! use. In ordinary times the two barely differ and nobody needs to know which
*! they are reading. Gold is what makes it matter.
*!
*! Splitting the two sides rather than netting them is the more informative
*! cut, because the episode is one-sided twice over: metal arrived through
*! 2024Q4-2025Q1 and left again from 2025Q2, so the import panel and the
*! export panel break in different quarters.
*!
*!     IMPORTS   largest ITA-NIPA gap  328.5bn   ->  35.7bn after adjusting
*!               mean absolute gap      22.7bn   ->  18.5bn
*!     EXPORTS   largest gap           202.3bn   ->  24.2bn
*!               mean absolute gap      27.7bn   ->  10.1bn
*!
*! WHAT IS DONE TO EACH SERIES. The console prints this in full on every run,
*! because the two sources arrive on different footings and the comparison is
*! only honest if the transformation is visible.
*!
*!   ITA    BOPGIMP / BOPGEXP. BEA International Transactions Accounts, goods,
*!          balance-of-payments basis. Native: MONTHLY, $ MILLIONS, seasonally
*!          adjusted, NOT annualised. Divided by 1,000 to $bn, collapsed to
*!          quarters by the MEAN of the months present, multiplied by 12.
*!          Mean x 12 rather than sum x 4 so a quarter missing a month is not
*!          understated by a third - a trap that produced a spurious 34%
*!          tracking error elsewhere in this project.
*!
*!   NIPA   A255RC1Q027SBEA / A253RC1Q027SBEA. NIPA table 1.1.5, goods.
*!          Native: QUARTERLY, $ BILLIONS, SEASONALLY ADJUSTED AT ANNUAL
*!          RATES. NOTHING IS DONE TO IT. In the monthly input file the
*!          quarterly figure sits on the first month of each quarter, and
*!          firstnm carries that single value across.
*!
*!   GOLD   US Census monthly HS 7108 and 7115, imports and exports kept
*!          separate. Same divide-and-annualise treatment as the ITA. The
*!          adjusted line is each ITA side less its OWN gold flow - imports
*!          less gold imports, exports less gold exports.
*!
*! BOTH SOURCES ARE SEASONALLY ADJUSTED, checked rather than assumed: BOPGIMP's
*! average deviation from a centred 13-month mean spans 1.4 percentage points
*! across months of the year. An unadjusted trade series would span roughly ten
*! times that, so the quarter-to-quarter disagreements are not a seasonality
*! artefact.
*!
*! WHAT THE ADJUSTMENT DOES NOT CLOSE. Ten to nineteen billion of mean absolute
*! gap survives on each side. That is not gold. NIPA goods and ITA goods also
*! differ by smaller reconciliation items, and the two annualisations are not
*! the same procedure - BEA applies its own seasonal factors and quarterly
*! conventions where this file applies mean x 12.
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
gen double gold_imp = vimports / 1e9
gen double gold_exp = vexports / 1e9
keep m gold_imp gold_exp
format m %tm
save `gold'

*=================================================== 2. the two official series
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp a255rc1q027sbea a253rc1q027sbea, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
merge 1:1 m using `gold', keep(master match) nogen
sort m

* ITA: monthly $mn -> monthly $bn. Annualised at the collapse below.
gen double ita_imp_m = bopgimp / 1000
gen double ita_exp_m = bopgexp / 1000
* NIPA: already $bn SAAR, quarterly, carried on the quarter's first month.
rename a255rc1q027sbea nipa_imp_q
rename a253rc1q027sbea nipa_exp_q

gen int q = qofd(dofm(m))
format q %tq

* Mean of the months present x 12, so a quarter missing a month is not
* understated. firstnm for NIPA, which has exactly one value per quarter;
* (max) would also work but would silently take the larger if that changed.
collapse (mean) ita_imp_m ita_exp_m gold_imp gold_exp                       ///
         (firstnm) nipa_imp_q nipa_exp_q, by(q)
foreach v in ita_imp_m ita_exp_m gold_imp gold_exp {
    replace `v' = 12 * `v'
}
rename ita_imp_m  ita_imp
rename ita_exp_m  ita_exp
rename nipa_imp_q nipa_imp
rename nipa_exp_q nipa_exp
sort q
drop if missing(ita_imp, nipa_imp, ita_exp, nipa_exp)
keep if q >= tq(2015q1)

* The adjusted series: each side less its own gold flow.
gen double adj_imp = ita_imp - gold_imp
gen double adj_exp = ita_exp - gold_exp

*=========================================================== 3. what it says
di as txt "{hline 78}"
di as txt "TRANSFORMATIONS APPLIED"
di as txt "{hline 78}"
di as txt "  ITA   BOPGIMP / BOPGEXP, BEA International Transactions Accounts,"
di as txt "        goods, balance-of-payments basis"
di as txt "        native : monthly, {c $|} millions, seasonally adjusted, NOT annualised"
di as txt "        applied: / 1000 -> {c $|}bn, then collapse to quarter by MEAN of the"
di as txt "                 months present, then x 12 for an annual rate"
di as txt "        why mean x 12 and not sum x 4: a quarter missing a month would"
di as txt "                 otherwise be understated by a third"
di as txt ""
di as txt "  NIPA  A255RC1Q027SBEA / A253RC1Q027SBEA, NIPA table 1.1.5, goods"
di as txt "        native : quarterly, {c $|} billions, SEASONALLY ADJUSTED AT ANNUAL RATES"
di as txt "        applied: NOTHING. firstnm carries the quarter's single value."
di as txt ""
di as txt "  GOLD  US Census monthly HS 7108 + 7115, imports and exports separately"
di as txt "        applied: / 1e9 -> {c $|}bn, same mean x 12 annualisation as the ITA"
di as txt "        adjusted line = each ITA side less that side's OWN gold flow"
di as txt ""
di as txt "  Both sources are seasonally adjusted. Checked, not assumed: BOPGIMP's"
di as txt "  month-of-year deviation from a centred 13-month mean spans 1.4pp,"
di as txt "  where an unadjusted trade series would span roughly ten times that."
di as txt "{hline 78}"
di as txt ""

foreach s in imp exp {
    local WHAT = cond("`s'" == "imp", "IMPORTS", "EXPORTS")
    gen double gap_`s'    = ita_`s' - nipa_`s'
    gen double gapadj_`s' = adj_`s' - nipa_`s'
    gen double agap_`s'   = abs(gap_`s')
    gen double aadj_`s'   = abs(gapadj_`s')

    qui summarize agap_`s'
    local MR = r(mean)
    local XR = r(max)
    qui summarize aadj_`s'
    local MA = r(mean)
    local XA = r(max)
    gsort -agap_`s'
    local WQ : display %tqCCYY!Qq q[1]
    local WQ = trim("`WQ'")
    sort q
    qui correlate gap_`s' gold_`s'
    local RG = r(rho)

    di as txt "`WHAT'  ({c $|}bn at an annual rate, 2015Q1 onward)"
    di as txt "   mean |ITA - NIPA|       " %7.1f `MR' "    largest " %7.1f `XR' ///
        "  in `WQ'"
    di as txt "   mean |adjusted - NIPA|  " %7.1f `MA' "    largest " %7.1f `XA'
    di as txt "   corr(raw gap, gold flow on this side) = " %6.3f `RG'
    di as txt ""
}

*=========================== 3b. the balance, which the panels deliberately
*                                 do NOT plot
* The figure shows the two flows separately because a net balance lets an
* import error and an export error of the same sign cancel - exactly the case
* the figure exists to rule out. But the balance is what a reader of the
* monthly trade release actually sees, so its diagnostics are reported here
* even though no panel draws them. Everything below comes from the same three
* series the panels use, so the numbers are reproducible from this file alone.
gen double bal_ita  = ita_imp - ita_exp        // deficit, positive
gen double bal_nipa = nipa_imp - nipa_exp
gen double bal_adj  = adj_imp - adj_exp
gen double net_gold = gold_imp - gold_exp
gen double bgap     = bal_ita - bal_nipa
gen double bgapadj  = bal_adj - bal_nipa
gen double bgappct  = 100 * bgap / bal_nipa
gen double abgap    = abs(bgap)
gen double abgapadj = abs(bgapadj)

tsset q
gen double d_ita  = D.bal_ita
gen double d_nipa = D.bal_nipa
gen double d_adj  = D.bal_adj
* A directional disagreement: the two measures say the deficit moved opposite
* ways in the same quarter. A level gap can be netted out by a reader who
* knows it is there; this cannot.
gen byte disagree    = (sign(d_ita) != sign(d_nipa)) if !missing(d_ita, d_nipa)
gen byte disagreeadj = (sign(d_adj) != sign(d_nipa)) if !missing(d_adj, d_nipa)

di as txt "{hline 78}"
di as txt "THE BALANCE ({c $|}bn at an annual rate, deficit positive, 2015Q1 onward)"
di as txt "  not plotted - reported here because it is what the monthly release shows"
di as txt "{hline 78}"
qui summarize bgappct
local PMAX = r(max)
local PMIN = r(min)
gsort -bgappct
local PMAXQ : display %tqCCYY!Qq q[1]
gsort bgappct
local PMINQ : display %tqCCYY!Qq q[1]
sort q
qui summarize bal_ita if q == tq(2025q1), meanonly
local BI = r(mean)
qui summarize bal_nipa if q == tq(2025q1), meanonly
local BN = r(mean)
qui summarize bgapadj if q == tq(2025q1), meanonly
local BA = r(mean)
di as txt "   2025Q1  ITA deficit " %7.0f `BI' "   NIPA deficit " %7.0f `BN'
di as txt "           gap " %7.0f `BI'-`BN' "  = " %5.1f 100*(`BI'-`BN')/`BN' ///
    "% of NIPA;  after adjustment " %6.0f `BA'
di as txt "   widest gap  " %6.1f `PMAX' "% in " trim("`PMAXQ'") ///
    "    most negative " %6.1f `PMIN' "% in " trim("`PMINQ'")
qui correlate bgap net_gold
di as txt "   corr(gap, net gold) = " %6.3f r(rho)
* The MEAN OF THE ABSOLUTE gap, not the absolute value of the mean gap - the
* latter nets a positive quarter against a negative one and understates badly.
qui summarize abgap
local M1 = r(mean)
qui summarize abgapadj
di as txt "   mean |gap| raw vs adjusted: " %6.1f `M1' " -> " %6.1f r(mean)
qui correlate d_ita d_nipa
local C1 = r(rho)
qui correlate d_adj d_nipa
di as txt "   corr of quarterly CHANGES, raw " %5.3f `C1' " -> adjusted " %5.3f r(rho)
qui count if disagree == 1
local ND = r(N)
qui count if disagreeadj == 1
local NA = r(N)
qui count if !missing(disagree)
di as txt "   directional disagreements: " %2.0f `ND' " of " %3.0f r(N) ///
    " quarterly changes; after adjustment " %2.0f `NA'
* Name them, and say which survive the adjustment. The adjustment is not
* claimed to fix every disagreement - only the ones gold caused - so the
* survivors are the honest part of this diagnostic.
foreach v in disagree disagreeadj {
    local WHICH = cond("`v'" == "disagree", "raw     ", "adjusted")
    qui count if `v' == 1
    if r(N) > 0 {
        levelsof q if `v' == 1, local(DQ)
        di as txt "     `WHICH':" _continue
        foreach x of local DQ {
            local LBL : display %tqCCYY!Qq `x'
            di as txt " " trim("`LBL'") _continue
        }
        di as txt ""
    }
}
* Gold's weight in the quarters that disagree, because the recommendation in
* the memo is conditional on it: an adjustment made when gold is a rounding
* error can only add noise, and 2016 is where that shows.
gen double gshare = 100 * gold_imp / ita_imp
* A LEVEL share is the wrong trigger and this is where that becomes visible.
* What flips the direction of the balance is the CHANGE in net gold, not its
* level, so the diagnostic that matters is how much of the quarter's change in
* the deficit is net gold moving.
gen double d_gold = D.net_gold
gen double gcontrib = 100 * abs(d_gold) / abs(d_ita)
di as txt "   the disagreeing quarters, with gold's weight two ways:"
di as txt "     quarter   gold as % of    net gold change as    survives"
di as txt "               goods imports   % of deficit change   adjustment?"
forvalues i = 1/`=_N' {
    if disagree[`i'] == 1 | disagreeadj[`i'] == 1 {
        local LBL : display %tqCCYY!Qq q[`i']
        local TAG = cond(disagree[`i'] != 1, "created BY it", ///
                    cond(disagreeadj[`i'] == 1, "yes, survives", "no, removed "))
        di as txt "     " trim("`LBL'") _col(26) %5.1f gshare[`i'] "%" ///
            _col(44) %7.0f gcontrib[`i'] "%" _col(60) "   `TAG'"
    }
}

* And the ones gold explains: present raw, gone after adjustment.
qui count if disagree == 1 & disagreeadj == 0
if r(N) > 0 {
    levelsof q if disagree == 1 & disagreeadj == 0, local(DQ)
    di as txt "     gold explains:" _continue
    foreach x of local DQ {
        local LBL : display %tqCCYY!Qq `x'
        di as txt " " trim("`LBL'") _continue
    }
    di as txt ""
}
di as txt "{hline 78}"
di as txt ""

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

foreach s in imp exp {
    if "`s'" == "imp" {
        local TTL1 "{bf:a.} US goods imports, {c $|}bn at an annual rate"
        local TTL2 "{it:The ITA counts nonmonetary gold; the national accounts do not. In 2025Q1 the two were {c $|}329bn apart}"
        local YLAB 2000(500)4000
        local YRNG 1850 4150
        local LEG legend(order(1 "ITA, gold included"                        ///
                     2 "ITA, gold removed (HS 7108 and 7115)"                ///
                     3 "NIPA, gold already removed")                         ///
               rows(1) size(small) region(lcolor(none)) symxsize(8)          ///
               symysize(2) position(12) ring(1) bmargin(zero) color("`SOFT'"))
    }
    else {
        local TTL1 "{bf:b.} US goods exports, {c $|}bn at an annual rate"
        local TTL2 "{it:The export side breaks later, when the metal went back out. The largest gap is {c $|}202bn}"
        local YLAB 1200(300)2400
        local YRNG 1100 2650
        local LEG legend(off)
    }
    twoway                                                                  ///
        (line ita_`s'  q, lcolor("`RED'")  lwidth(1.00) cmissing(n))        ///
        (line adj_`s'  q, lcolor("`GREY'") lwidth(1.25) cmissing(n))        ///
        (line nipa_`s' q, lcolor("`INK'")  lwidth(0.55) lpattern(dash)      ///
            cmissing(n))                                                    ///
        ,                                                                   ///
        title("`TTL1'" "`TTL2'", size(medsmall) color("`INK'")              ///
              position(11) justification(left) span)                        ///
        ytitle("")                                                          ///
        ylabel(`YLAB', angle(0) labsize(small) tlcolor(none)                ///
               labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))     ///
        yscale(range(`YRNG') noextend lcolor(none))                         ///
        xtitle("")                                                          ///
        xlabel(`XLAB', labsize(small) tlcolor(none) labcolor("`SOFT'")      ///
               nogrid)                                                      ///
        xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))              ///
        `LEG'                                                               ///
        graphregion(color(white) margin(l=2 r=3 t=1 b=1))                   ///
        plotregion(color(white) margin(zero) lcolor(none))                  ///
        name(p_`s', replace) nodraw
}

graph combine p_imp p_exp, cols(1) imargin(zero)                            ///
    xsize(10.5) ysize(6.4)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:The same trade, measured twice - and the two sides break in different quarters}" ///
             "Same agency, same transactions. The only difference is whether bullion counts as trade", ///
             size(medsmall) color("`INK'") position(11)                     ///
             justification(left) span)                                      ///
    name(combined, replace)

graph export "$FIG/ita_nipa_comparability.pdf", replace
di as txt "wrote $FIG/ita_nipa_comparability.pdf"

capture graph set window fontface "$RESTORE_FONT"
