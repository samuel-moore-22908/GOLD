*==============================================================================
* The gold aggregate at monthly resolution
*
* 05_gold_aggregate.do reports the same scope annually. Everything there that
* was a yearly number is re-derived here as a monthly series, and three things
* are added that only exist at this resolution.
*
* SCOPE, unchanged: GOLD = 710811 + 710812 + 710813 + 711590, both legs.
* 7115.90 carries silver and platinum that HS6 cannot remove, so levels are an
* upper bound on gold. Shape is unaffected.
*
* WHAT IS NEW HERE
*
*  1. Rolling twelve-month reversal index. R was annual, which meant five
*     numbers and a calendar boundary doing analytical work it should not do:
*     the 2025 build and the 2026 drain are one episode split by 31 December.
*     A trailing window removes the boundary and makes R a series.
*
*  2. Which leg moved. NX falling can mean imports surged or exports collapsed,
*     and those are different events with different causes. Each leg is scaled
*     by its own trailing twelve-month mean, EXCLUDING the current month, so a
*     surge cannot deflate its own baseline.
*
*  3. Which code moved. The aggregate hides that 710812, 710813 and 711590 do
*     not move together at all -- the 2026 outflow is a different commodity
*     line from the 2025 inflow. Monthly per-code net flow makes that visible,
*     and it is the sharpest evidence in this file that what is being measured
*     is re-classification of the same metal rather than distinct trades.
*==============================================================================

clear all
set more off
version 18
set linesize 120

* Directories are globals, never locals.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/monthly_resolution.log", replace text

*------------------------------------------------------------------ code level
use "$out/gl_panel.dta", clear
keep if inlist(hs6, "710811", "710812", "710813", "711590")
gen double x_tot_c = x_dom + x_re
gen double net_c = x_tot_c - m_gen
keep hs6 mdate x_dom x_re x_tot_c m_gen net_c
format mdate %tm
tempfile bycode
save `bycode'

*------------------------------------------------------------------ aggregate
use `bycode', clear
collapse (sum) x_dom x_re x_tot_c m_gen, by(mdate)
rename x_tot_c x_tot
isid mdate
tsset mdate

gen double net_x = x_tot - m_gen
gen double trade = x_tot + m_gen
gen double nx = net_x / trade
gen double gl = 1 - abs(nx)
gen double re_sh = x_re / x_tot if x_tot > 0
gen year = year(dofm(mdate))

*------------------------------------------------------------------ rolling
* Rolling sums via differenced cumulative sums: csum(t) - csum(t-12) is the
* total over t-11..t. Cheaper and clearer than twelve lag terms.
sort mdate
gen double c_net = sum(net_x)
gen double c_abs = sum(abs(net_x))
gen double c_x   = sum(x_tot)
gen double c_m   = sum(m_gen)

gen double r_net = c_net - L12.c_net
gen double r_abs = c_abs - L12.c_abs
gen double r_x   = c_x - L12.c_x
gen double r_m   = c_m - L12.c_m

gen double R12 = 1 - abs(r_net) / r_abs
gen double nx12 = r_net / (r_x + r_m)
label var R12  "rolling 12m reversal index, 0 directional .. 1 round-tripping"
label var nx12 "rolling 12m signed position"

* Baselines exclude the current month: months t-12..t-1.
gen double base_m = (L1.c_m - L13.c_m) / 12
gen double base_x = (L1.c_x - L13.c_x) / 12
gen double surge_m = m_gen / base_m
gen double surge_x = x_tot / base_x
label var surge_m "imports vs own trailing 12m mean"
label var surge_x "exports vs own trailing 12m mean"

gen double cum = sum(m_gen - x_tot) / 1e9

*------------------------------------------------------------------ regime
* Two dimensions, so four cells, but only three occur. Thresholds are round
* numbers chosen to be legible, not estimated -- they are a reading aid on top
* of R12 and nx12, which are the actual statistics.
gen byte regime = .
replace regime = 1 if R12 > 0.70 & abs(nx12) < 0.15          // round-tripping
replace regime = 2 if R12 < 0.40 & abs(nx12) >= 0.15         // directional
replace regime = 3 if missing(regime) & !missing(R12)        // mixed
label define reg 1 "round-trip" 2 "directional" 3 "mixed"
label values regime reg

save "$out/monthly_resolution.dta", replace

*==============================================================================
* 1. THE MONTHLY MASTER TABLE
*==============================================================================
display _n(2) "{hline 118}"
display "1. GOLD AGGREGATE, MONTHLY -- flows in USD bn"
display "{hline 118}"
preserve
    gen double xd_bn = x_dom / 1e9
    gen double xr_bn = x_re / 1e9
    gen double x_bn = x_tot / 1e9
    gen double m_bn = m_gen / 1e9
    gen double net_bn = net_x / 1e9
    gen str7 dir = cond(net_bn > 0, "EXPORT", "import")
    format xd_bn xr_bn x_bn m_bn net_bn cum %8.2f
    format nx gl re_sh %6.3f
    list mdate xd_bn xr_bn x_bn m_bn net_bn cum nx gl re_sh dir, ///
         noobs abbrev(7) separator(12)
restore

*==============================================================================
* 2. ROLLING TWELVE-MONTH BEHAVIOUR
*    R12 and nx12 together are the taxonomy. Neither alone is enough:
*      high R12, nx12 near zero   metal in and out within the window
*      low  R12, nx12 away from 0 metal moving one way and staying
*==============================================================================
display _n(2) "{hline 118}"
display "2. ROLLING 12-MONTH REVERSAL INDEX AND SIGNED POSITION"
display "   First reading is 2022m12; a trailing window needs twelve months."
display "{hline 118}"
preserve
    keep if !missing(R12)
    gen double rnet_bn = r_net / 1e9
    gen double rabs_bn = r_abs / 1e9
    format R12 nx12 %7.3f
    format rnet_bn rabs_bn %9.1f
    list mdate R12 nx12 rnet_bn rabs_bn regime, noobs abbrev(8) separator(12)
restore

*==============================================================================
* 3. WHICH LEG MOVED
*    Ratio of each leg to its own trailing twelve-month mean, current month
*    excluded from the baseline. A month can have both legs elevated, which is
*    churn, or one leg only, which is a genuine directional shock.
*==============================================================================
display _n(2) "{hline 118}"
display "3. LEG SURGE FACTORS  (1.0 = at trailing 12m mean, current month excluded)"
display "   Listed for months where either leg is at least double its baseline."
display "{hline 118}"
preserve
    keep if (surge_m >= 2 | surge_x >= 2) & !missing(surge_m)
    gen double m_bn = m_gen / 1e9
    gen double x_bn = x_tot / 1e9
    gen str9 which = cond(surge_m >= 2 & surge_x >= 2, "BOTH", ///
                     cond(surge_m >= 2, "imports", "exports"))
    format surge_m surge_x %7.2f
    format m_bn x_bn %8.2f
    format nx %6.3f
    list mdate m_bn surge_m x_bn surge_x nx which, noobs abbrev(8) separator(0)
restore

*==============================================================================
* 4. WHICH CODE MOVED
*    Monthly net flow by HS6. The aggregate conceals that these lines do not
*    move together.
*==============================================================================
display _n(2) "{hline 118}"
display "4. MONTHLY NET FLOW BY CODE, USD bn   (positive = net export)"
display "{hline 118}"
preserve
    use `bycode', clear
    keep hs6 mdate net_c
    replace net_c = net_c / 1e9
    reshape wide net_c, i(mdate) j(hs6) string
    rename net_c710811 n_powder
    rename net_c710812 n_unwrgt
    rename net_c710813 n_semimf
    rename net_c711590 n_artpm
    gen double n_total = n_powder + n_unwrgt + n_semimf + n_artpm
    format n_* %8.2f
    label var n_powder "710811"
    label var n_unwrgt "710812"
    label var n_semimf "710813"
    label var n_artpm  "711590"
    list mdate n_powder n_unwrgt n_semimf n_artpm n_total, ///
         noobs abbrev(8) separator(12)

    display _n "  correlation of monthly net flows between codes:"
    correlate n_unwrgt n_semimf n_artpm
restore

*==============================================================================
* 5. EPISODES
*    Contiguous runs of one direction, with the stock each moved. This is the
*    narrative spine: the story is a small number of episodes, not 54 months.
*==============================================================================
display _n(2) "{hline 118}"
display "5. DIRECTIONAL EPISODES  (contiguous months of the same sign)"
display "{hline 118}"
preserve
    gen byte pos = net_x > 0
    gen long run = 1 if _n == 1
    replace run = cond(pos != pos[_n-1], run[_n-1] + 1, run[_n-1]) if _n > 1
    collapse (min) start = mdate (max) end = mdate (count) months = mdate ///
             (sum) total = net_x (mean) pos, by(run)
    gen double total_bn = total / 1e9
    gen str9 dir = cond(pos > 0.5, "EXPORT", "import")
    * collapse(count) inherits mdate's %tm format, which would print a count of
    * 7 as 1960m8. Reset it.
    format months %6.0g
    format start end %tm
    format total_bn %9.1f
    * Single-month episodes are kept. 2025m7 is one of them and it is the Swiss
    * shipment; dropping short runs would delete the sharpest event in the file.
    list start end months dir total_bn, noobs abbrev(8) separator(0)
restore

*------------------------------------------------------------------ charts
use "$out/monthly_resolution.dta", clear

twoway (line R12 mdate, lcolor(navy) lwidth(thick)) ///
       (line nx12 mdate, lcolor(cranberry) lpattern(dash) lwidth(medthick)), ///
    yline(0, lcolor(gs10)) ///
    ytitle("index") xtitle("") ylabel(-0.4(0.2)1, grid) ///
    title("Round-tripping versus directional flow, rolling 12 months", size(medium)) ///
    subtitle("R near 1: metal in and out within the window. R near 0: one way.", size(small)) ///
    legend(order(1 "reversal index R12" 2 "signed position NX12") rows(1) ///
           size(small) position(6) ring(1) region(lstyle(none))) ///
    xlabel(, format(%tmCY) angle(45)) ///
    graphregion(color(white)) plotregion(color(white)) xsize(9) ysize(5)
graph export "$out/gold_rolling_regime.png", replace width(1800)

preserve
    use `bycode', clear
    gen double net_bn = net_c / 1e9
    keep if inlist(hs6, "710812", "710813", "711590")
    twoway (line net_bn mdate if hs6 == "710812", lcolor(navy) lwidth(medthick)) ///
           (line net_bn mdate if hs6 == "710813", lcolor(dkgreen) lwidth(medthick)) ///
           (line net_bn mdate if hs6 == "711590", lcolor(cranberry) lwidth(medthick)), ///
        yline(0, lcolor(gs10)) ///
        ytitle("monthly net export, USD bn") xtitle("") ///
        title("The three codes do not move together", size(medium)) ///
        subtitle("monthly net flow by HS6, positive = net export", size(small)) ///
        legend(order(1 "710812 unwrought" 2 "710813 semi-manufactured" ///
                     3 "711590 articles of precious metal") rows(1) size(vsmall) ///
               position(6) ring(1) region(lstyle(none))) ///
        xlabel(, format(%tmCY) angle(45)) ///
        graphregion(color(white)) plotregion(color(white)) xsize(9) ysize(5)
    graph export "$out/gold_net_by_code.png", replace width(1800)
restore

*------------------------------------------------------------------ artefacts
keep mdate year x_dom x_re x_tot m_gen net_x trade nx gl re_sh cum ///
     R12 nx12 surge_m surge_x regime
export delimited using "$out/monthly_resolution.csv", replace

display _n(2) "wrote monthly_resolution.csv, gold_rolling_regime.png, gold_net_by_code.png"
log close
