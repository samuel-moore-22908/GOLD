*! fig9_nipa_reconciliation.do
*!
*! An external check on the whole gold story: reconciling BEA's International
*! Transactions Accounts with BEA's own national accounts.
*!
*! WHY THIS IS THE RIGHT REFERENCE. Everything else in this folder measures the
*! gold distortion against a counterfactual that this project constructed. That
*! is an argument, not a verification. But BEA publishes the SAME trade twice,
*! on two bases that differ in exactly the way that matters:
*!
*!   ITA  (International Transactions Accounts, the monthly trade release)
*!        INCLUDES nonmonetary gold.
*!   NIPA (the national accounts)
*!        EXCLUDES it outright - nonmonetary gold is removed and replaced by
*!        domestic production less industrial use.
*!
*! So if the gold series used throughout this project is right, subtracting it
*! from the ITA goods total should land on the NIPA goods total. Nothing is
*! fitted; the two aggregates are independent publications and the gold figure
*! is a third source, Census customs data.
*!
*! IT WORKS, AND BETTER THAN EXPECTED. On the nominal side the ITA-NIPA gap is
*! gold almost exactly: the two move together at a correlation of 0.99, and
*! taking gold out collapses the standard deviation of the gap from $54bn to
*! $9bn on imports and from $39bn to $7bn on exports. In 2025Q1 the raw gap was
*! $329bn at an annual rate and the residual after removing gold is $12bn, on a
*! base above $3,600bn. That is a hard external validation of the gold series.
*!
*! THE SECOND ADJUSTMENT DOES ALMOST NOTHING, AND THAT IS WORTH SAYING. The
*! obvious next step is to deflate the gold-free total with a gold-free price
*! index rather than the published one. On quarter-on-quarter real growth
*! against NIPA:
*!
*!     imports   naive 2.07pp RMSE -> gold out of totals 0.86 -> also ex-gold
*!               deflator 0.86   (corr with NIPA 0.901 -> 0.983 -> 0.982)
*!     exports   naive 1.28pp RMSE -> 0.65 -> 0.63
*!               (corr 0.975 -> 0.995 -> 0.995)
*!
*! The first adjustment does essentially all the work; the second is within
*! noise on imports and a sliver on exports. The reason is a matter of scale
*! and it calibrates the rest of this folder. Gold reached 10.5% of the goods
*! import TOTAL, but it sits in the price index at about 1%. Mis-stating a 1%
*! weight is a second-order problem next to carrying a 10% item you did not
*! want at all. Both effects are real - fig7 and fig8 measure the deflator one
*! and it is worth about two index points over six years - but this says
*! plainly which of the two dominates, and it is not the deflator.
*!
*! WHAT THE RESIDUAL IS. The series still differ by about 2-3% in level and
*! 0.6pp in quarterly growth after both adjustments. That is not gold. The ITA
*! real series here is a Lowe index deflation and NIPA is chain-Fisher over a
*! different basket, and MXPI does not price military goods, used goods or art.
*! Those differences are permanent and are not meant to close.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/nipa_reconciliation.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig9_nipa_reconciliation.do

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

local LAG = 2

tempfile gold mxpi nipa

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

*=========================================================== 2. the BLS indexes
import delimited using "$RAW/us_mxpi_monthly.csv", varnames(1) clear
destring eiuir eiuiq eiuir14270 eiuiq12260, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
rename eiuir p_m
rename eiuiq p_x
rename eiuir14270 pg_m
rename eiuiq12260 pg_x
keep m p_m p_x pg_m pg_x
save `mxpi'

*============================================== 3. the NIPA quarterly reference
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring a255rc1q027sbea a253rc1q027sbea a255rx1q020sbea a253rx1q020sbea, ///
    replace force
gen double m = mofd(date(date, "YMD"))
gen int q = qofd(dofm(m))
rename a255rc1q027sbea nipa_nom_m      // imports of goods, nominal, $bn SAAR
rename a253rc1q027sbea nipa_nom_x      // exports of goods, nominal, $bn SAAR
rename a255rx1q020sbea nipa_real_m     // imports of goods, chained 2017$, SAAR
rename a253rx1q020sbea nipa_real_x
keep q nipa_*
drop if missing(nipa_nom_m)
collapse (mean) nipa_*, by(q)
format q %tq
save `nipa'

*======================================================== 4. the ITA monthly
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp bopgexp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(master match) nogen
sort m

gen double nom_m = bopgimp / 1000              // $bn a month
gen double nom_x = bopgexp / 1000
replace gold_m = gold_m / 1e9
replace gold_x = gold_x / 1e9
gen int yr = year(dofm(m))

*=================================================== 5. the weight BLS carries
preserve
    collapse (sum) gold_m gold_x nom_m nom_x, by(yr)
    gen double w_m = gold_m / nom_m
    gen double w_x = gold_x / nom_x
    replace yr = yr + `LAG'
    keep yr w_m w_x
    tempfile wt
    save `wt'
restore
merge m:1 yr using `wt', keep(master match) nogen
sort m

*============================== 6. three real series, interval-aware deflators
* As in fig8: differences against the previous NON-MISSING index observation,
* so the October 2025 hole is handled rather than bridged.
foreach side in m x {
    gen double dlp_`side' = .
    gen double dlg_`side' = .
    local prev = .
    local prevg = .
    forvalues i = 1/`=_N' {
        if !missing(p_`side'[`i']) {
            if !missing(`prev') {
                qui replace dlp_`side' = ln(p_`side'[`i'])  - `prev'  in `i'
                qui replace dlg_`side' = ln(pg_`side'[`i']) - `prevg' in `i'
            }
            local prev  = ln(p_`side'[`i'])
            local prevg = ln(pg_`side'[`i'])
        }
    }
    * Ex-gold inflation: what the index would have done with gold taken out at
    * the weight it actually carries.
    gen double dlng_`side' = (dlp_`side' - w_`side' * dlg_`side') / (1 - w_`side')

    gen double ip_`side' = 100 * exp(sum(cond(missing(dlp_`side'),  0, dlp_`side')))
    gen double ie_`side' = 100 * exp(sum(cond(missing(dlng_`side'), 0, dlng_`side')))
    replace ip_`side' = . if missing(p_`side')
    replace ie_`side' = . if missing(p_`side')

    * naive  : the ITA total, deflated by the published index - what a user of
    *          the trade release gets.
    * step1  : gold taken out of the total, published index.
    * step2  : gold taken out of the total AND out of the index.
    gen double naive_`side' = 100 * nom_`side' / ip_`side'
    gen double step1_`side' = 100 * (nom_`side' - gold_`side') / ip_`side'
    gen double step2_`side' = 100 * (nom_`side' - gold_`side') / ie_`side'
    gen double exg_`side'   = nom_`side' - gold_`side'
}

*============================================================ 7. to quarterly
* ANNUALISED FROM MONTHLY MEANS, not summed. 2025Q4 holds only two months,
* because BLS published no October index, and summing it would understate the
* quarter by a third - which showed up as a spurious 34% tracking error on a
* first pass and has nothing to do with gold.
gen int q = qofd(dofm(m))
format q %tq
collapse (mean) nom_m nom_x exg_m exg_x gold_m gold_x                       ///
         naive_m naive_x step1_m step1_x step2_m step2_x, by(q)
foreach v in nom_m nom_x exg_m exg_x gold_m gold_x naive_m naive_x          ///
             step1_m step1_x step2_m step2_x {
    replace `v' = 12 * `v'
}
merge 1:1 q using `nipa', keep(match) nogen
sort q
keep if q >= tq(2015q1)

*=========================================================== 8. what it says
di as txt "{hline 76}"
di as txt "NOMINAL: is the ITA-NIPA gap gold?  ({c $|}bn SAAR)"
foreach side in m x {
    local WHAT = cond("`side'" == "m", "imports", "exports")
    gen double graw_`side' = nom_`side' - nipa_nom_`side'
    gen double gexg_`side' = exg_`side' - nipa_nom_`side'
    qui correlate graw_`side' gold_`side'
    local R1 = r(rho)
    qui summarize graw_`side'
    local S1 = r(sd)
    qui summarize gexg_`side'
    local S2 = r(sd)
    di as txt "   `WHAT' : corr(gap, gold) = " %6.3f `R1' ///
        "   sd of gap " %6.1f `S1' " -> " %5.1f `S2' " after removing gold"
}
di as txt ""
di as txt "REAL: quarter-on-quarter growth against NIPA, percentage points"
di as txt "   series                              RMSE    corr with NIPA"
foreach side in m x {
    local WHAT = cond("`side'" == "m", "imports", "exports")
    gen double g_nipa_`side' = 100 * (ln(nipa_real_`side') - ln(nipa_real_`side'[_n-1]))
    foreach v in naive step1 step2 {
        gen double g_`v'_`side' = 100 * (ln(`v'_`side') - ln(`v'_`side'[_n-1]))
        gen double e_`v'_`side' = g_`v'_`side' - g_nipa_`side'
        qui summarize e_`v'_`side'
        local RMSE = sqrt(r(Var) * (r(N)-1)/r(N) + r(mean)^2)
        qui correlate g_`v'_`side' g_nipa_`side'
        di as txt "   `WHAT' `v'" _col(40) %6.2f `RMSE' "pp" _col(52) %8.4f r(rho)
    }
}
di as txt ""
di as txt "   Adjustment 1 does nearly all the work. Gold reached 10.5% of the"
di as txt "   import TOTAL but sits in the price index at about 1%, so taking a"
di as txt "   10% item out of the numerator dominates re-weighting a 1% one."
di as txt "{hline 76}"

*=========================================================== 9. the four panels
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

* ---- nominal panels ---------------------------------------------------------
foreach side in m x {
    * PLOT THE GAP, NOT THE LEVELS. On a $3,300bn base the wedge is under 1%
    * for most of the sample, so two level lines sit on top of each other and
    * the shaded area is invisible except briefly in 2025. Drawn as the gap
    * against gold, the claim is testable by eye: if the ITA-NIPA difference
    * really is gold, the two lines coincide and the residual is flat.
    if "`side'" == "m" {
        local TTL1 "{bf:a.} Goods imports: the ITA-NIPA gap, and nonmonetary gold"
        local TTL2 "{it:{c $|}bn, annual rate. If the gap is gold, the two lines coincide and the residual sits on zero}"
        local YLAB 0(100)300
        local YRNG -60 350
        local LEG legend(order(1 "ITA minus NIPA"                            ///
                               2 "Nonmonetary gold (Census)"                ///
                               3 "Residual: gap minus gold")                ///
                  rows(1) size(vsmall) region(lcolor(none)) symxsize(6)      ///
                  symysize(2) position(11) ring(0) bmargin(zero)             ///
                  color("`SOFT'"))
    }
    else {
        local TTL1 "{bf:c.} Goods exports: the same test"
        local TTL2 "{it:{c $|}bn, annual rate}"
        local YLAB 0(100)200
        local YRNG -50 240
        local LEG legend(off)
    }
    twoway                                                                  ///
        (line graw_`side' q, lcolor("`GREY'") lwidth(0.85) cmissing(n))     ///
        (line gold_`side' q, lcolor("`RED'") lwidth(0.45)                   ///
            lpattern(shortdash) cmissing(n))                                ///
        (line gexg_`side' q, lcolor("`INK'") lwidth(0.35) cmissing(n))      ///
        ,                                                                   ///
        yline(0, lcolor("`SOFT'") lwidth(0.22))                             ///
        title("`TTL1'" "`TTL2'", size(small) color("`INK'") position(11)    ///
              justification(left) span)                                     ///
        ytitle("")                                                          ///
        ylabel(`YLAB', angle(0) labsize(vsmall) tlcolor(none)               ///
               labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))     ///
        yscale(range(`YRNG') noextend lcolor(none))                         ///
        xtitle("")                                                          ///
        xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'")     ///
               nogrid)                                                      ///
        xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))              ///
        `LEG'                                                               ///
        graphregion(color(white) margin(l=2 r=3 t=1 b=1))                   ///
        plotregion(color(white) margin(zero) lcolor(none))                  ///
        name(nom_`side', replace) nodraw
}

* ---- real tracking-error panels ---------------------------------------------
foreach side in m x {
    if "`side'" == "m" {
        local TTL1 "{bf:b.} Real goods imports: error against NIPA growth, percentage points"
        local TTL2 "{it:Quarter-on-quarter. Taking gold out of the total closes almost all of it; re-weighting the deflator adds nothing}"
        local LEG legend(order(1 "ITA as published, deflated"                ///
                               2 "Gold out of the total"                    ///
                               3 "Gold out of the total and the deflator")  ///
                  rows(1) size(vsmall) region(lcolor(none)) symxsize(6)      ///
                  symysize(2) position(11) ring(0) bmargin(zero)             ///
                  color("`SOFT'"))
    }
    else {
        local TTL1 "{bf:d.} Real goods exports: error against NIPA growth, percentage points"
        local TTL2 "{it:Quarter-on-quarter}"
        local LEG legend(off)
    }
    twoway                                                                  ///
        (line e_naive_`side' q, lcolor("`GREY'") lwidth(0.50) cmissing(n))  ///
        (line e_step1_`side' q, lcolor("`RED'") lwidth(0.50) cmissing(n))   ///
        (line e_step2_`side' q, lcolor("`INK'") lwidth(0.35)                ///
            lpattern(shortdash) cmissing(n))                                ///
        ,                                                                   ///
        yline(0, lcolor("`SOFT'") lwidth(0.25))                             ///
        title("`TTL1'" "`TTL2'", size(small) color("`INK'") position(11)    ///
              justification(left) span)                                     ///
        ytitle("")                                                          ///
        ylabel(-8(2)4, angle(0) labsize(vsmall) tlcolor(none)               ///
               labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.22))     ///
        yscale(range(-9.5 5) noextend lcolor(none))                         ///
        xtitle("")                                                          ///
        xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'")     ///
               nogrid)                                                      ///
        xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))              ///
        `LEG'                                                               ///
        graphregion(color(white) margin(l=2 r=3 t=1 b=1))                   ///
        plotregion(color(white) margin(zero) lcolor(none))                  ///
        name(err_`side', replace) nodraw
}

graph combine nom_m err_m nom_x err_x, cols(2) imargin(small)               ///
    xsize(13.2) ysize(8.0)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:BEA publishes the same trade twice, and the difference between the two is gold}" ///
             "The International Transactions Accounts include nonmonetary gold; the national accounts exclude it. Nothing here is fitted", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "This is the one check in this project that does not rest on a counterfactual of our own construction. BEA publishes goods trade on two bases that differ in" ///
         "exactly the way that matters, and the gold figure subtracted from the ITA total is a third source - Census customs data. Left: the ITA goods total minus the" ///
         "NIPA goods total, drawn against nonmonetary gold itself. The gap IS gold - the two lines coincide at a correlation of 0.99 and the residual stays flat -" ///
         "and removing gold cuts the gap's standard deviation from {c $|}54bn to {c $|}9bn on imports and from {c $|}39bn to {c $|}7bn on exports. In 2025Q1 the raw gap was {c $|}329bn at an annual" ///
         "rate and {c $|}12bn remained after removing gold, on a base above {c $|}3,600bn. The levels are not plotted: on a {c $|}3,300bn base the wedge is under 1% for most of the" ///
         "sample and two level lines would sit on top of each other." ///
         " " ///
         "Right: the error against NIPA's own real growth. The first adjustment does nearly all the work - import RMSE falls from 2.07pp to 0.86pp and the correlation with" ///
         "NIPA rises from 0.90 to 0.98 - and re-weighting the deflator on top adds nothing on imports and a sliver on exports. That ordering is worth stating plainly: gold" ///
         "reached 10.5% of the goods import TOTAL but sits in the price index at about 1%, so removing a 10% item from the numerator dominates re-weighting a 1% one. The" ///
         "deflator bias measured elsewhere in this folder is real and worth about two index points over six years, but it is the smaller of the two channels." ///
         " " ///
         "The residual - roughly 2-3% in level and 0.6pp in quarterly growth - is NOT gold. The ITA series here is deflated with a Lowe index and NIPA is chain-Fisher over" ///
         "a different basket, and MXPI does not price military goods, used goods or art. Those gaps are permanent and are not meant to close. Quarters are annualised from" ///
         "monthly means rather than summed, because BLS published no October 2025 index and summing would understate that quarter by a third." ///
         "Source: Bureau of Economic Analysis (ITA and NIPA); Bureau of Labor Statistics; US Census Bureau.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/nipa_reconciliation.pdf", replace
di as txt "wrote $FIG/nipa_reconciliation.pdf"

capture graph set window fontface "$RESTORE_FONT"
