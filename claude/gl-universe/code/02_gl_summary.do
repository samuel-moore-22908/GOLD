*==============================================================================
* Grubel-Lloyd: summary statistics and the tails, by year
*
* Runs on gl_panel.dta, which 01_grubel_lloyd.do builds. Two units of analysis,
* deliberately kept apart because they answer different questions:
*
*   commodity-MONTH   the distribution the index actually lives at
*   commodity-YEAR    GL of annual totals, which is what a ranking should use
*
* Size floors are not cosmetic. GL is a ratio, so a $4,000 export against a
* $3,900 import scores 0.987 and carries no information. Rankings use a $1bn
* annual floor; distributions use a $1m monthly floor. Both are stated in every
* table header rather than buried here.
*
* The bottom tail is degenerate: thousands of commodities are purely one-way and
* score exactly 0, so "bottom 10" is a tie among hundreds. Ties are broken on
* trade value descending, which turns a meaningless list into a useful one --
* the LARGEST commodities that move in only one direction.
*
* AND THE BOTTOM TAIL IS NOT COMMODITIES. Running it the first time returned
* 880000, 980100, 988000 and 999995 -- Schedule B and HTSUS special provisions,
* not HS headings. Chapter 98 is US goods returned and articles admitted under
* special provisions; 999995 is literally "estimated imports of low valued
* transactions"; codes ending 0000 are chapter-level catch-alls. They are
* one-way BY CONSTRUCTION, score exactly 0 every year, and carry 5.1% to 6.8%
* of all recorded US trade. They belong in no GL computation.
*
* Flagged as `special' below and reported both ways rather than dropped
* silently, because they are present in the 01_grubel_lloyd.do results too and
* that needs to be visible rather than quietly fixed.
*
* One caveat on the labels: descr is the FIRST 10-digit line under each HS6 in
* the Census concordance, not an official 6-digit heading. It is a readable
* handle, not authority. 980100 prints as "U.S. MEAT & POULTRY" when the
* provision is US goods returned generally.
*==============================================================================

clear all
set more off
version 18
set linesize 110

* Directories are globals, never locals.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/gl_summary.log", replace text

*------------------------------------------------------------------ build
use "$out/gl_panel.dta", clear

* Annual aggregate: sum the flows first, then form the index. GL of summed
* totals is not the mean of monthly GL, and the annual figure is the right one
* for a commodity ranking.
preserve
    collapse (sum) x_dom x_re m_gen, by(hs6 year)
    gen double x_tot = x_dom + x_re
    gen double trade = x_tot + m_gen
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen) if trade > 0
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen) ///
                          if (x_dom + m_gen) > 0
    gen double wedge = gl_total - gl_dom
    gen double trade_bn = trade / 1e9
    gen double re_sh = x_re / x_tot if x_tot > 0

    merge m:1 hs6 using "$out/hs6_labels.dta", keep(master match) nogenerate
    replace descr = "(no description)" if missing(descr)

    * Special provisions and catch-all aggregates, not commodities.
    gen byte special = inlist(substr(hs6, 1, 2), "98", "99") | ///
                       substr(hs6, 3, 4) == "0000"
    label var special "Schedule B / HTSUS special provision, not an HS heading"

    tempfile annual
    save `annual'
restore

*==============================================================================
* 1. GL distribution by year, commodity-MONTH level
*==============================================================================
display _n(2) "{hline 79}"
display "1. GL BY YEAR, COMMODITY-MONTH LEVEL (>= 1m USD combined trade)"
display "{hline 79}"
display "        n        mean      sd     p10     p25     p50     p75     p90"
display "  {hline 75}"
quietly levelsof year, local(yrs)
foreach y of local yrs {
    quietly summarize gl_total if year == `y' & trade >= 1e6, detail
    display "  `y' " %8.0fc r(N) "   " %6.3f r(mean) "  " %6.3f r(sd) "  " ///
            %6.3f r(p10) "  " %6.3f r(p25) "  " %6.3f r(p50) "  " ///
            %6.3f r(p75) "  " %6.3f r(p90)
}

display _n "  shape of the distribution -- what share sits at each end:"
display "        share GL = 0   share GL < .05   share GL > .90   share GL > .99"
display "  {hline 75}"
foreach y of local yrs {
    quietly {
        count if year == `y' & trade >= 1e6 & !missing(gl_total)
        local n = r(N)
        count if year == `y' & trade >= 1e6 & gl_total == 0
        local z = r(N)
        count if year == `y' & trade >= 1e6 & gl_total < .05
        local lo = r(N)
        count if year == `y' & trade >= 1e6 & gl_total > .90 & !missing(gl_total)
        local hi = r(N)
        count if year == `y' & trade >= 1e6 & gl_total > .99 & !missing(gl_total)
        local vhi = r(N)
    }
    display "  `y'      " %8.1f `=100*`z'/`n'' "%       " %8.1f `=100*`lo'/`n'' ///
            "%        " %8.1f `=100*`hi'/`n'' "%       " %8.1f `=100*`vhi'/`n'' "%"
}

*==============================================================================
* 2. Same, on domestic exports only
*==============================================================================
display _n(2) "{hline 79}"
display "2. THE SAME, RE-EXPORTS REMOVED (gl_dom)"
display "{hline 79}"
display "        n        mean      sd     p10     p25     p50     p75     p90"
display "  {hline 75}"
foreach y of local yrs {
    quietly summarize gl_dom if year == `y' & trade >= 1e6, detail
    display "  `y' " %8.0fc r(N) "   " %6.3f r(mean) "  " %6.3f r(sd) "  " ///
            %6.3f r(p10) "  " %6.3f r(p25) "  " %6.3f r(p50) "  " ///
            %6.3f r(p75) "  " %6.3f r(p90)
}

*==============================================================================
* 3. Commodity-YEAR distribution, the unit the rankings below use
*==============================================================================
display _n(2) "{hline 79}"
display "3. GL BY YEAR, COMMODITY-YEAR LEVEL (>= 1bn USD annual trade)"
display "{hline 79}"
use `annual', clear
display "        n        mean      sd     p10     p25     p50     p75     p90"
display "  {hline 75}"
foreach y of local yrs {
    quietly summarize gl_total if year == `y' & trade >= 1e9, detail
    display "  `y' " %8.0fc r(N) "   " %6.3f r(mean) "  " %6.3f r(sd) "  " ///
            %6.3f r(p10) "  " %6.3f r(p25) "  " %6.3f r(p50) "  " ///
            %6.3f r(p75) "  " %6.3f r(p90)
}

*==============================================================================
* 3b. What the special provisions do to the aggregate
*==============================================================================
display _n(2) "{hline 79}"
display "3b. SPECIAL PROVISIONS: SHARE OF TRADE, AND EFFECT ON MEAN GL"
display "{hline 79}"
display "        trade_bn   of which special   share   mean GL all   mean GL real"
display "  {hline 75}"
foreach y of local yrs {
    quietly {
        summarize trade if year == `y', meanonly
        local T = r(sum)
        summarize trade if year == `y' & special, meanonly
        local S = r(sum)
        summarize gl_total if year == `y' & trade >= 1e9
        local ma = r(mean)
        summarize gl_total if year == `y' & trade >= 1e9 & !special
        local mr = r(mean)
    }
    display "  `y'  " %9.0fc `=`T'/1e9' "        " %9.0fc `=`S'/1e9' "     " ///
            %5.1f `=100*`S'/`T'' "%       " %6.3f `ma' "        " %6.3f `mr'
}

*==============================================================================
* 4. TOP 10 BY YEAR -- most balanced two-way trade
*==============================================================================
display _n(2) "{hline 79}"
display "4. TOP 10 BY GL EACH YEAR   (annual totals, >= 1bn USD, special excl.)"
display "{hline 79}"
foreach y of local yrs {
    display _n "  --- `y' " "{hline 62}"
    preserve
        keep if year == `y' & trade >= 1e9 & !special
        gsort -gl_total -trade
        format gl_total gl_dom wedge %6.3f
        format trade_bn %7.1f
        list hs6 descr gl_total gl_dom trade_bn in 1/10, ///
             noobs abbrev(9) string(38) separator(0)
    restore
}

*==============================================================================
* 5. BOTTOM 10 BY YEAR -- most one-way trade
*    Hundreds of commodities tie at exactly 0, so the tie is broken on trade
*    value descending. The list is therefore "the biggest one-way commodities",
*    which is the informative version of the question.
*==============================================================================
display _n(2) "{hline 79}"
display "5. BOTTOM 10 BY GL EACH YEAR   (annual totals, >= 1bn USD trade)"
display "   Special provisions EXCLUDED -- see 3b. Ties at the floor broken on"
display "   trade value, so these are the LARGEST real commodities that move in"
display "   essentially one direction only."
display "{hline 79}"
foreach y of local yrs {
    display _n "  --- `y' " "{hline 62}"
    preserve
        keep if year == `y' & trade >= 1e9 & !special
        gen byte netexp = x_tot > m_gen
        label define dir 0 "net import" 1 "net export"
        label values netexp dir
        gsort gl_total -trade
        format gl_total %6.3f
        format trade_bn %7.1f
        list hs6 descr gl_total trade_bn netexp in 1/10, ///
             noobs abbrev(9) string(38) separator(0)
    restore
}

*------------------------------------------------------------------ artefacts
export delimited hs6 descr special year x_dom x_re x_tot m_gen trade ///
    gl_total gl_dom wedge re_sh using "$out/gl_annual_ranked.csv", replace

display _n(2) "wrote gl_annual_ranked.csv"
log close
