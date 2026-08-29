*==============================================================================
* The composite non-monetary gold category, and its GL over time
*
* MEMBERSHIP, confirmed with the user 2026-08-29:
*
*   710811   gold powder, non-monetary
*   710812   gold bullion, unwrought, not less than 99.95 percent
*   710813   gold, semi-manufactured forms ("gold leaf" in the Census label)
*   711590   other articles of precious metal, in rectangular form
*
* 711590 is in because of a finding recorded in RESEARCH_DOSSIER.md: a US
* Census pull scoped to 7108 alone came back 5-180x below what Swiss-Impex
* tonnage implied for the same months, and adding 7115.90 brought every
* spot-checked month back within ~15%. The dossier states it as a requirement --
* "any future US-side pull for this project must include HS 7115.90 alongside
* 7108, or it will systematically undercount the relocation-heavy months."
* 01_grubel_lloyd.do and 02_gl_summary.do both have that defect; this file is
* the correction, and section 2 measures how large it was.
*
* CBP's CROSS rulings give it a legal basis rather than leaving it an empirical
* oddity: investment-grade bar classification has moved between 7108.13 and
* 7115.90.05 repeatedly since 1989, and the operative distinction is "cast"
* versus "minted" manufacturing language, not gold content or bar size.
*
* CAVEAT THAT MUST TRAVEL WITH EVERY NUMBER BELOW. 7115.90 is "articles of
* PRECIOUS METAL", not of gold. At HS6 the gold bars cannot be separated from
* silver and platinum articles in the same heading -- the 10-digit line
* (7115.90.05) can, but this panel is HS6. The dossier's tonnage reconciliation
* is the evidence the heading is gold-dominated in these corridors; it is not
* proof, and the composite is therefore an upper bound on gold in 711590.
*
* EXCLUDED, deliberately:
*   710820   monetary gold -- BPM6 convention. Confirmed absent from the pull
*            entirely rather than assumed; central bank flows need IMF IFS.
*   7113     jewellery. 711319 alone is $96.5bn over the window, so this is not
*            a rounding decision, but it is fabricated product, not metal.
*   2616     ores and concentrates.
*   711890   gold coin ($18.2bn) and 711291 gold scrap ($18.4bn) are held out
*            of the core and reported as sensitivity checks in section 5.
*==============================================================================

clear all
set more off
version 18
set linesize 110

* Directories are globals, never locals.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/gold_composite.log", replace text

use "$out/gl_panel.dta", clear

*------------------------------------------------------------------ definitions
gen byte core  = inlist(hs6, "710811", "710812", "710813", "711590")
gen byte only7108 = inlist(hs6, "710811", "710812", "710813")
gen byte coin  = hs6 == "711890"
gen byte scrap = hs6 == "711291"

label var core "composite non-monetary gold"

quietly count if core
display "composite rows: " r(N)
quietly levelsof hs6 if core, local(members) clean
display "composite members: `members'"

*------------------------------------------------------------------ collapse
* A composite category is built by summing the FLOWS and then forming the
* index once. Averaging the four member GLs would be a different and wrong
* object -- it would weight a $0.4bn powder line equally with $100bn of bullion.
preserve
    keep if core | coin | scrap | only7108
    gen byte grp = .
    replace grp = 1 if core
    replace grp = 2 if only7108
    replace grp = 3 if core | coin
    replace grp = 4 if core | scrap

    * grp is not exclusive, so expand rather than assign: each row contributes
    * to every definition it belongs to.
    expand 4
    bysort hs6 mdate: gen byte defn = _n
    keep if (defn == 1 & core) | (defn == 2 & only7108) | ///
            (defn == 3 & (core | coin)) | (defn == 4 & (core | scrap))

    collapse (sum) x_dom x_re m_gen m_con, by(defn mdate)
    gen double x_tot = x_dom + x_re
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen) if (x_tot + m_gen) > 0
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen) if (x_dom + m_gen) > 0
    gen double wedge = gl_total - gl_dom
    gen double re_sh = x_re / x_tot if x_tot > 0
    gen double trade_bn = (x_tot + m_gen) / 1e9
    gen year = year(dofm(mdate))
    format mdate %tm
    label define defnlab 1 "composite" 2 "7108 only" 3 "+ coin" 4 "+ scrap"
    label values defn defnlab
    save "$out/gold_composite_monthly.dta", replace
restore

*==============================================================================
* 1. THE COMPOSITE OVER TIME -- annual
*==============================================================================
use "$out/gold_composite_monthly.dta", clear
display _n(2) "{hline 95}"
display "1. COMPOSITE NON-MONETARY GOLD, ANNUAL"
display "{hline 95}"
preserve
    keep if defn == 1
    collapse (sum) x_dom x_re m_gen, by(year)
    gen double x_tot = x_dom + x_re
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen)
    gen double wedge = gl_total - gl_dom
    gen double re_sh = x_re / x_tot
    gen double x_bn = x_tot / 1e9
    gen double xd_bn = x_dom / 1e9
    gen double xr_bn = x_re / 1e9
    gen double m_bn = m_gen / 1e9
    format x_bn xd_bn xr_bn m_bn %8.1f
    format gl_total gl_dom wedge re_sh %7.3f
    list year xd_bn xr_bn x_bn m_bn gl_total gl_dom wedge re_sh, noobs abbrev(9)
restore

*==============================================================================
* 2. WHAT 711590 CHANGES
*    The size of the defect in 01_grubel_lloyd.do and 02_gl_summary.do.
*==============================================================================
display _n(2) "{hline 95}"
display "2. COMPOSITE vs HS 7108 ONLY -- the size of the 711590 omission"
display "{hline 95}"
display "         trade_bn composite   trade_bn 7108   understated by   GL comp   GL 7108"
display "  {hline 91}"
quietly levelsof year, local(yrs)
foreach y of local yrs {
    quietly {
        summarize trade_bn if defn == 1 & year == `y', meanonly
        local tc = r(sum)
        summarize trade_bn if defn == 2 & year == `y', meanonly
        local t8 = r(sum)
        preserve
        keep if defn == 1 & year == `y'
        collapse (sum) x_tot m_gen
        local gc = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
        restore
        preserve
        keep if defn == 2 & year == `y'
        collapse (sum) x_tot m_gen
        local g8 = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
        restore
    }
    display "  `y'      " %10.1f `tc' "      " %10.1f `t8' "        " ///
            %6.1f `=100*(`tc'-`t8')/`tc'' "%    " %7.3f `gc' "   " %7.3f `g8'
}

*==============================================================================
* 3. THE MONTHLY EVOLUTION
*==============================================================================
display _n(2) "{hline 95}"
display "3. COMPOSITE GOLD GL, MONTHLY"
display "{hline 95}"
preserve
    keep if defn == 1
    gen double xd_bn = x_dom / 1e9
    gen double xr_bn = x_re / 1e9
    gen double m_bn = m_gen / 1e9
    format xd_bn xr_bn m_bn %7.2f
    format gl_total gl_dom wedge re_sh %7.3f
    list mdate m_bn xd_bn xr_bn gl_total gl_dom wedge re_sh, ///
         noobs abbrev(9) separator(12)
restore

*==============================================================================
* 4. ROLLING BEHAVIOUR
*    Twelve-month rolling GL of summed flows -- not a rolling mean of the
*    monthly index, which would be a different object.
*==============================================================================
display _n(2) "{hline 95}"
display "4. TWELVE-MONTH ROLLING GL (of summed flows), COMPOSITE"
display "{hline 95}"
preserve
    keep if defn == 1
    tsset mdate
    gen double rx = x_tot + L1.x_tot + L2.x_tot + L3.x_tot + L4.x_tot + L5.x_tot + ///
                    L6.x_tot + L7.x_tot + L8.x_tot + L9.x_tot + L10.x_tot + L11.x_tot
    gen double rxd = x_dom + L1.x_dom + L2.x_dom + L3.x_dom + L4.x_dom + L5.x_dom + ///
                     L6.x_dom + L7.x_dom + L8.x_dom + L9.x_dom + L10.x_dom + L11.x_dom
    gen double rm = m_gen + L1.m_gen + L2.m_gen + L3.m_gen + L4.m_gen + L5.m_gen + ///
                    L6.m_gen + L7.m_gen + L8.m_gen + L9.m_gen + L10.m_gen + L11.m_gen
    gen double gl_roll = 1 - abs(rx - rm) / (rx + rm)
    gen double gld_roll = 1 - abs(rxd - rm) / (rxd + rm)
    format gl_roll gld_roll %7.3f
    list mdate gl_roll gld_roll if !missing(gl_roll), noobs abbrev(9) separator(12)

    twoway (line gl_total mdate, lcolor(navy) lwidth(medthick)) ///
           (line gl_dom mdate, lcolor(cranberry) lpattern(dash) lwidth(medthick)) ///
           (line gl_roll mdate, lcolor(black) lwidth(thick)), ///
        ytitle("Grubel-Lloyd index") xtitle("") ///
        title("US composite non-monetary gold: intra-industry trade", size(medium)) ///
        subtitle("HS 710811 + 710812 + 710813 + 711590, monthly", size(small)) ///
        legend(order(1 "GL, all exports" 2 "GL, domestic exports only" ///
                     3 "GL, 12-month rolling") rows(1) size(small) ///
               position(6) ring(1) region(lstyle(none))) ///
        ylabel(0(0.2)1, grid) xlabel(, format(%tmCY) angle(45)) ///
        graphregion(color(white)) plotregion(color(white)) xsize(9) ysize(5) ///
        note("Source: US Census intltrade HS6. 711590 is 'articles of precious metal'," ///
             "so the composite is an upper bound on gold in that heading.", size(vsmall))
    graph export "$out/gold_composite_gl.png", replace width(1800)
restore

*==============================================================================
* 5. SENSITIVITY -- coin and scrap
*==============================================================================
display _n(2) "{hline 95}"
display "5. SENSITIVITY: ADDING GOLD COIN (711890) OR GOLD SCRAP (711291)"
display "{hline 95}"
display "  year    GL composite     + coin     + scrap     max shift"
display "  {hline 60}"
foreach y of local yrs {
    quietly {
        foreach d in 1 3 4 {
            preserve
            keep if defn == `d' & year == `y'
            collapse (sum) x_tot m_gen
            local g`d' = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
            restore
        }
    }
    local mx = max(abs(`g3' - `g1'), abs(`g4' - `g1'))
    display "  `y'       " %7.3f `g1' "    " %7.3f `g3' "    " %7.3f `g4' ///
            "      " %7.3f `mx'
}

*==============================================================================
* 6. THE FREQUENCY GAP -- the measurement that matters
*
* Annual GL and monthly GL answer different questions, and for gold they give
* opposite answers. The gap between them is not a nuisance: it is a signature.
*
*   high annual GL + low monthly GL  ->  metal in one month, out another.
*                                        ROUND-TRIPPING. Relocation.
*   low annual  GL + low monthly GL  ->  persistently one-way. ABSORPTION.
*   high annual GL + high monthly GL ->  genuine simultaneous two-way trade.
*
* This is the cleanest form of the CLAUDE.md point about frequency. It is
* stronger than "annual aggregation erases the phenomenon", which the earlier
* 01_grubel_lloyd.do test found too strong: annual aggregation does not erase
* the signal, it INVERTS it, and the inversion is measurable.
*==============================================================================
display _n(2) "{hline 95}"
display "6. FREQUENCY GAP: ANNUAL GL vs MEAN MONTHLY GL, COMPOSITE"
display "{hline 95}"
display "  year   GL of annual totals   mean monthly GL   gap   reading"
display "  {hline 91}"
foreach y of local yrs {
    quietly {
        preserve
        keep if defn == 1 & year == `y'
        summarize gl_total, meanonly
        local mm = r(mean)
        collapse (sum) x_tot m_gen
        local ga = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
        restore
    }
    local gap = `ga' - `mm'
    local read = cond(`gap' > 0.25, "round-tripping", ///
                 cond(`gap' > 0.10, "partial round-trip", "directional"))
    display "  `y'          " %7.3f `ga' "           " %7.3f `mm' ///
            "     " %6.3f `gap' "   `read'"
}

*------------------------------------------------------------------ artefacts
use "$out/gold_composite_monthly.dta", clear
keep if defn == 1
export delimited mdate year x_dom x_re x_tot m_gen m_con gl_total gl_dom ///
    wedge re_sh trade_bn using "$out/gold_composite_monthly.csv", replace

display _n(2) "wrote gold_composite_monthly.csv and gold_composite_gl.png"
log close
