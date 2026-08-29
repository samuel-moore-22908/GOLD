*==============================================================================
* One GOLD category. Symmetric scope, signed position, cumulative stock.
*
* SCOPE. A single aggregate, built the same way on both legs:
*
*     GOLD = 710811 + 710812 + 710813 + 711590        imports AND exports
*
* This is scope B from 04_signed_and_cumulative.do, adopted here as the only
* scope rather than one of three. The asymmetric variant is dropped.
*
* The trade-off, stated once and then not repeated:
*
*   WHAT IT COSTS. 7115.90 is "articles of precious metal", not of gold. Of its
*   six HTSUS lines, three are rectangular bars of 99.5%+ ANY precious metal,
*   and the other three are gold, silver and platinum "NESOI" respectively. At
*   HS6 the silver and platinum cannot be removed. Silver bullion alone
*   (710691) runs $46bn over the window on its own separate code, so silver
*   flows are not small and some unmeasured share of 711590 is not gold. Every
*   level below is therefore an upper bound on gold.
*
*   WHAT IT BUYS. The stock identity holds. Cumulative sum(M - X) is only a
*   stock of metal if both legs cover the same goods, and a symmetric scope is
*   the only way to guarantee that. The asymmetric scope bought a cleaner
*   bar definition at the cost of manufacturing accumulation -- it counted
*   711590 arriving and not leaving. Between a known contamination and a broken
*   identity, the contamination is the better problem: it biases the level in a
*   direction that is at least signable, and it does not distort the shape.
*
* The 7108-only scope remains the wrong answer for a different reason,
* documented in 03_gold_composite.do: it omits $98.9bn of 2025 imports and the
* tariff-episode stock build is entirely invisible in it.
*
* HEADLINE STATISTIC is NX, not GL:
*
*     NX = (X - M) / (X + M)        -1 pure import .. +1 pure export
*     GL = 1 - |NX|
*
* GL is a strictly lossy transform of NX -- it discards the sign and nothing
* else -- so NX leads and GL is shown beside it for continuity with the
* earlier files.
*==============================================================================

clear all
set more off
version 18
set linesize 110

* Directories are globals, never locals.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/gold_aggregate.log", replace text

*------------------------------------------------------------------ build
use "$out/gl_panel.dta", clear
keep if inlist(hs6, "710811", "710812", "710813", "711590")

quietly levelsof hs6, local(members) clean
display "GOLD aggregate members: `members'"
quietly count
display "rows: " r(N) " (4 codes x 54 months)"

collapse (sum) x_dom x_re m_gen m_con, by(mdate)
isid mdate

gen double x_tot = x_dom + x_re
gen double net_x = x_tot - m_gen
gen double trade = x_tot + m_gen
gen double nx = net_x / trade
gen double gl = 1 - abs(nx)
gen double nx_dom = (x_dom - m_gen) / (x_dom + m_gen)
gen double re_sh = x_re / x_tot if x_tot > 0
gen year = year(dofm(mdate))
format mdate %tm

label var nx     "signed position, -1 pure import .. +1 pure export"
label var nx_dom "same, domestic exports only"
label var gl     "Grubel-Lloyd, = 1 - |nx|"

*==============================================================================
* 1. ANNUAL
*==============================================================================
display _n(2) "{hline 100}"
display "1. GOLD AGGREGATE, ANNUAL"
display "{hline 100}"
preserve
    collapse (sum) x_dom x_re m_gen, by(year)
    gen double x_tot = x_dom + x_re
    gen double nx = (x_tot - m_gen) / (x_tot + m_gen)
    gen double gl = 1 - abs(nx)
    gen double net_bn = (x_tot - m_gen) / 1e9
    gen double xd_bn = x_dom / 1e9
    gen double xr_bn = x_re / 1e9
    gen double x_bn = x_tot / 1e9
    gen double m_bn = m_gen / 1e9
    gen str9 dir = cond(net_bn > 0, "EXPORT", "import")
    format xd_bn xr_bn x_bn m_bn net_bn %8.1f
    format nx gl %7.3f
    list year xd_bn xr_bn x_bn m_bn net_bn nx gl dir, noobs abbrev(9)
restore

*==============================================================================
* 2. MONTHLY, all 54
*==============================================================================
display _n(2) "{hline 100}"
display "2. GOLD AGGREGATE, MONTHLY"
display "{hline 100}"
preserve
    gen double xd_bn = x_dom / 1e9
    gen double xr_bn = x_re / 1e9
    gen double x_bn = x_tot / 1e9
    gen double m_bn = m_gen / 1e9
    gen double net_bn = net_x / 1e9
    gen str9 dir = cond(net_bn > 0, "EXPORT", "import")
    format xd_bn xr_bn x_bn m_bn net_bn %8.2f
    format nx gl re_sh %7.3f
    list mdate xd_bn xr_bn x_bn m_bn net_bn nx gl re_sh dir, ///
         noobs abbrev(8) separator(12)
restore

*==============================================================================
* 3. CUMULATIVE NET IMPORT -- the trade-implied US stock position
*==============================================================================
display _n(2) "{hline 100}"
display "3. CUMULATIVE SUM OF (M - X) FROM 2022m1, USD bn"
display "   Positive = metal accumulated in the US since the base date."
display "{hline 100}"
sort mdate
gen double cum = sum(m_gen - x_tot) / 1e9
label var cum "cumulative net import since 2022m1, USD bn"

preserve
    gen double net_bn = -net_x / 1e9
    format cum net_bn %9.1f
    list mdate net_bn cum, noobs abbrev(9) separator(12)
restore

quietly summarize cum
local peak = r(max)
local trough = r(min)
quietly summarize mdate if cum == `peak'
local tpk = r(mean)
quietly summarize mdate if cum == `trough'
local ttr = r(mean)
display _n "  peak    " %8.1f `peak' "  at " %tm `tpk'
display "  trough  " %8.1f `trough' "  at " %tm `ttr'
display "  swing   " %8.1f `=`peak' - `trough'' "  peak to trough"

*==============================================================================
* 4. DIRECTIONAL PERSISTENCE
*    R = 1 - |sum net| / sum |net| over the months of a year.
*    R = 0  every month the same direction -- directional flow.
*    R = 1  monthly nets cancel exactly -- round-tripping.
*    This is what separates relocation from absorption, and it is the reading
*    GL cannot give because GL has already discarded the monthly signs.
*==============================================================================
display _n(2) "{hline 100}"
display "4. REVERSAL INDEX BY YEAR"
display "{hline 100}"
display "  year         R    gross |net| bn    net bn    months net export"
display "  {hline 70}"
quietly levelsof year, local(yrs)
foreach y of local yrs {
    quietly {
        summarize net_x if year == `y', meanonly
        local net = r(sum)
        generate double _a = abs(net_x) if year == `y'
        summarize _a, meanonly
        local gross = r(sum)
        drop _a
        count if year == `y' & net_x > 0
        local nexp = r(N)
        count if year == `y'
        local nall = r(N)
    }
    display "  `y'      " %7.3f `=1 - abs(`net')/`gross'' "       " ///
            %9.1f `=`gross'/1e9' "  " %9.1f `=`net'/1e9' "        `nexp' of `nall'"
}

*------------------------------------------------------------------ chart
* barwidth is in x-axis units, and x is a monthly date, so 0.8 is one month.
* Bars are drawn in USD bn on the same scale as the cumulative line: the two
* series share units, and forcing them onto one axis makes the relationship
* between a month's flow and the stock it moves readable.
gen double net_bn_p = net_x / 1e9
twoway (bar net_bn_p mdate if net_bn_p < 0, barwidth(0.8) color(navy%60)) ///
       (bar net_bn_p mdate if net_bn_p >= 0, barwidth(0.8) color(cranberry%60)) ///
       (line cum mdate, lcolor(black) lwidth(thick)), ///
    yline(0, lcolor(gs8) lwidth(thin)) ///
    ytitle("USD bn") ///
    xtitle("") ///
    title("US gold: monthly direction and the stock it accumulates", size(medium)) ///
    subtitle("HS 710811 + 710812 + 710813 + 711590, both legs", size(small)) ///
    legend(order(1 "monthly net import (bar)" 2 "monthly net export (bar)" ///
                 3 "cumulative position (line)") rows(1) size(vsmall) ///
           position(6) ring(1) region(lstyle(none))) ///
    xlabel(, format(%tmCY) angle(45)) ///
    graphregion(color(white)) plotregion(color(white)) xsize(9) ysize(5) ///
    note("711590 is 'articles of precious metal', so silver and platinum are" ///
         "inside this aggregate and cannot be removed at HS6. Levels are an" ///
         "upper bound on gold.", size(vsmall))
graph export "$out/gold_aggregate_position.png", replace width(1800)

*------------------------------------------------------------------ artefacts
keep mdate year x_dom x_re x_tot m_gen m_con net_x trade nx nx_dom gl re_sh cum
order mdate year
export delimited using "$out/gold_aggregate.csv", replace

display _n(2) "wrote gold_aggregate.csv and gold_aggregate_position.png"
log close
