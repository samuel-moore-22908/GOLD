*==============================================================================
* Signed trade position and cumulative net flow, US non-monetary gold
*
* Replaces Grubel-Lloyd as the headline statistic, for a simple reason:
*
*     GL = 1 - |NX|      where  NX = (X - M) / (X + M)
*
* GL is a strictly lossy transform of NX. It discards the sign and nothing
* else. Reporting GL as primary throws away the one thing this project most
* needs -- whether metal is arriving or leaving -- for no gain. NX runs -1
* (pure import) to +1 (pure export), and GL is recoverable from it at any time.
*
* Section 2 then cumulates the signed net flow. Sum(M - X) from a base date is
* the trade-implied stock of metal accumulated inside the US. Unlike any ratio,
* it is in dollars, it is directional, and it is externally checkable: CME
* warehouse stocks measure the same quantity by a different route.
*
*------------------------------------------------------------------------------
* THREE SCOPES, and why more than one is reported
*
*   A  7108 only            710811 + 710812 + 710813, both legs
*   B  symmetric composite  A + 711590 on both legs
*   C  asymmetric           imports A + 711590, exports A only        <- primary
*
* C is the requested scope and the reasoning behind it is good. HTSUS carries
* three dedicated bullion-bar lines under 7115.90 (7115900530/0560/0590,
* "rectangular shapes, 99.5% or more"); Schedule B carries none, only two
* generic "other articles of precious metal" lines. A bar therefore has a
* 7115.90 home on the import side and does not on the export side, so bars
* plausibly enter as 711590 and leave as 7108. Counting 711590 on both legs
* adds non-bar articles -- silverware, platinum items -- to exports only.
*
* THE CAVEAT, which is why C is not reported alone. A cumulative sum of
* (M - X) is a stock identity, and a stock identity requires both legs to
* cover the same physical goods. Scope C deliberately breaks that: it counts
* 711590 arriving and does not count it leaving. If any part of 711590 exports
* is in fact bars -- and at HS6 there is no way to tell, because Schedule B
* 7115900010/0090 are undifferentiated -- scope C manufactures accumulation
* that did not happen. The exposure is $28.3bn of 711590 exports across the
* window against a cumulative total near $62bn, so this is a ~45% swing in the
* headline number, not a rounding concern.
*
* Reporting all three costs nothing and makes the scope sensitivity visible
* instead of hidden. Resolving it needs a 10-digit pull on the import leg,
* which would also purge 7115.90.40 silver and 7115.90.60 platinum from the
* composite -- currently inside it, and unmeasured.
*==============================================================================

clear all
set more off
version 18
set linesize 110

* Directories are globals, never locals.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/signed_cumulative.log", replace text

use "$out/gl_panel.dta", clear
keep if inlist(hs6, "710811", "710812", "710813", "711590")

* gl_panel.dta already carries is7108 and ch71 from 01_grubel_lloyd.do.
capture drop is7108
capture drop ch71
gen byte is7108 = inlist(hs6, "710811", "710812", "710813")

*------------------------------------------------------------------ scopes
* Build each scope's monthly X and M separately, because scope C treats the
* two legs differently and a single collapse cannot express that.
preserve
    collapse (sum) x_dom x_re m_gen, by(mdate is7108)
    gen double x_tot = x_dom + x_re

    * Per-month totals for the two ingredient groups.
    bysort mdate: egen double x7108 = total(cond(is7108, x_tot, 0))
    bysort mdate: egen double m7108 = total(cond(is7108, m_gen, 0))
    bysort mdate: egen double xall  = total(x_tot)
    bysort mdate: egen double mall  = total(m_gen)

    keep mdate x7108 m7108 xall mall
    duplicates drop
    isid mdate

    * Long by scope. Built with expand rather than reshape: the stub "m" would
    * collide with mdate, and scope C mixes one leg from each group, which
    * reshape has no way to express.
    *   A  7108 both legs
    *   B  everything both legs
    *   C  imports from both, exports from 7108 only
    expand 3
    bysort mdate: gen byte sc = _n
    gen double x = cond(sc == 2, xall, x7108)
    gen double m = cond(sc == 1, m7108, mall)
    drop x7108 m7108 xall mall

    label define sclab 1 "A: 7108 both legs" 2 "B: +711590 both legs" ///
                       3 "C: +711590 imports only"
    label values sc sclab

    gen double nx = (x - m) / (x + m) if (x + m) > 0
    gen double gl = 1 - abs(nx)
    gen double net_imp = m - x
    gen double trade = x + m
    gen year = year(dofm(mdate))
    format mdate %tm
    label var nx "signed trade position, -1 pure import .. +1 pure export"
    save "$out/signed_scopes.dta", replace
restore

*==============================================================================
* 1. NX -- THE SIGNED POSITION
*==============================================================================
use "$out/signed_scopes.dta", clear

display _n(2) "{hline 100}"
display "1a. ANNUAL SIGNED POSITION, THREE SCOPES"
display "    NX < 0 net importer, NX > 0 net exporter. GL = 1 - |NX|, shown for"
display "    comparison so the sign that GL discards is visible beside it."
display "{hline 100}"
display "  year     scope                        X_bn      M_bn        NX        GL"
display "  {hline 96}"
quietly levelsof year, local(yrs)
foreach y of local yrs {
    forvalues s = 1/3 {
        quietly {
            summarize x if year == `y' & sc == `s', meanonly
            local X = r(sum)
            summarize m if year == `y' & sc == `s', meanonly
            local M = r(sum)
        }
        local nxv = (`X' - `M') / (`X' + `M')
        local lbl : label sclab `s'
        display "  `y'     " %-26s "`lbl'" %9.1f `=`X'/1e9' " " %9.1f `=`M'/1e9' ///
                "  " %8.3f `nxv' "  " %8.3f `=1-abs(`nxv')'
    }
    display "  {hline 96}"
}

display _n(2) "{hline 100}"
display "1b. MONTHLY SIGNED POSITION, PRIMARY SCOPE C -- all 54 months"
display "{hline 100}"
preserve
    keep if sc == 3
    gen double x_bn = x / 1e9
    gen double m_bn = m / 1e9
    gen double net_bn = (x - m) / 1e9
    gen str9 dir = cond(net_bn > 0, "EXPORT", "import")
    format x_bn m_bn net_bn %8.2f
    format nx gl %7.3f
    list mdate x_bn m_bn net_bn nx gl dir, noobs abbrev(9) separator(12)
restore

display _n(2) "{hline 100}"
display "1c. WHAT THE SIGN ADDS -- months GL cannot tell apart"
display "    Pairs of months with near-identical GL and opposite direction."
display "{hline 100}"
preserve
    keep if sc == 3
    gen double x_bn = x / 1e9
    gen double m_bn = m / 1e9
    format nx gl %7.3f
    format x_bn m_bn %8.2f
    gsort gl
    list mdate x_bn m_bn gl nx in 1/8, noobs abbrev(9) separator(0)
restore

*==============================================================================
* 2. CUMULATIVE NET IMPORT -- the trade-implied US stock position
*==============================================================================
display _n(2) "{hline 100}"
display "2a. CUMULATIVE SUM OF (M - X) FROM 2022m1, USD bn"
display "    Positive = metal accumulated in the US since the base date."
display "    Negative = the US has shipped out more than it took in."
display "{hline 100}"
bysort sc (mdate): gen double cum = sum(m - x) / 1e9
label var cum "cumulative net import since 2022m1, USD bn"

preserve
    keep mdate sc cum
    reshape wide cum, i(mdate) j(sc)
    rename cum1 cum_A
    rename cum2 cum_B
    rename cum3 cum_C
    format cum_A cum_B cum_C %9.1f
    label var cum_A "A: 7108"
    label var cum_B "B: symmetric"
    label var cum_C "C: primary"
    list mdate cum_C cum_B cum_A, noobs abbrev(9) separator(12)
restore

display _n(2) "{hline 100}"
display "2b. TURNING POINTS AND THE SCOPE SPREAD"
display "{hline 100}"
forvalues s = 1/3 {
    quietly {
        summarize cum if sc == `s'
        local mx = r(max)
        local mn = r(min)
        summarize mdate if sc == `s' & cum == `mx'
        local tmx = r(mean)
        summarize mdate if sc == `s' & cum == `mn'
        local tmn = r(mean)
        summarize cum if sc == `s' & mdate == tm(2026m6)
        local last = r(mean)
    }
    local lbl : label sclab `s'
    display "  " %-26s "`lbl'" "  peak " %8.1f `mx' " (" %tm `tmx' ")" ///
            "   trough " %8.1f `mn' " (" %tm `tmn' ")   ends " %8.1f `last'
}

display _n "  The spread between scopes at 2026m6 is the measurement uncertainty"
display "  that the HS6 classification asymmetry imposes. It is not sampling"
display "  error and it does not shrink with more months -- only a 10-digit"
display "  pull on the import leg resolves it."

*------------------------------------------------------------------ chart
preserve
    keep if inlist(sc, 1, 2, 3)
    twoway (line cum mdate if sc == 3, lcolor(navy) lwidth(thick)) ///
           (line cum mdate if sc == 2, lcolor(cranberry) lpattern(dash)) ///
           (line cum mdate if sc == 1, lcolor(gs8) lpattern(shortdash)), ///
        yline(0, lcolor(black) lwidth(thin)) ///
        ytitle("Cumulative net import since 2022m1, USD bn") xtitle("") ///
        title("Trade-implied US gold stock position", size(medium)) ///
        subtitle("cumulative sum of (imports - exports), three HS scopes", size(small)) ///
        legend(order(1 "C: 711590 imports only (primary)" ///
                     2 "B: 711590 both legs" ///
                     3 "A: HS 7108 only") rows(1) size(vsmall) ///
               position(6) ring(1) region(lstyle(none))) ///
        ylabel(, grid format(%9.0f)) xlabel(, format(%tmCY) angle(45)) ///
        graphregion(color(white)) plotregion(color(white)) xsize(9) ysize(5) ///
        note("Scope C counts 711590 arriving and not leaving, so it overstates" ///
             "accumulation by however much of the $28.3bn of 711590 exports is bars.", ///
             size(vsmall))
    graph export "$out/gold_cumulative_position.png", replace width(1800)
restore

*------------------------------------------------------------------ artefacts
keep mdate year sc x m nx gl net_imp trade cum
export delimited using "$out/signed_cumulative.csv", replace

display _n(2) "wrote signed_cumulative.csv and gold_cumulative_position.png"
log close
