*==============================================================================
* Grubel-Lloyd on the universe-tier US HS6 panel, 2022-01 .. 2026-05
*
* GL_i = 1 - |X_i - M_i| / (X_i + M_i)
*
*   0 = pure one-way trade (a country only imports it, or only exports it)
*   1 = exports exactly balance imports in the same HS6 line
*
* Read at HS6 and monthly, a high GL means the same commodity crossed the
* border in both directions in the same month. For a consumption good that is
* product differentiation. For an undifferentiated bulk commodity -- and one
* kilo of 995 fine gold is the same as any other -- there is no differentiation
* to find, so a high GL is the signature of metal passing through rather than
* being absorbed.
*
* The DF split makes a second measure available that the literature cannot
* normally compute. Census reports domestic exports separately from re-exports,
* so GL can be built twice:
*
*   gl_total  X = domestic + re-export   the number any other dataset gives you
*   gl_dom    X = domestic only          re-exports removed
*
*   wedge     gl_total - gl_dom
*
* The wedge is SIGNED, and the sign carries the meaning. Re-exports add to X,
* so they move the trade balance in one direction only; whether that raises or
* lowers GL depends on which side of balance the commodity already sits.
*
*   X < M  ->  re-exports push X toward M   ->  wedge > 0, GL inflated
*   X > M  ->  re-exports push X past M     ->  wedge < 0, GL depressed
*
* An earlier draft of this file described the wedge as one-directional
* contamination that always inflates GL. That is wrong, and gold is the case
* that shows it: the US is a large net exporter of HS 7108 in value terms, so
* its gold wedge is negative in every year of the sample. Stripping re-exports
* raises gold's GL rather than lowering it.
*
* Either sign means the same thing about the data -- that a chunk of the
* measured two-way trade is metal passing through rather than being produced or
* absorbed -- but the direction has to be read off the balance, not assumed.
*
* Values are USD, general imports (GEN_VAL_MO) against total exports, which is
* the pairing that matches on basis. CON_VAL_MO is carried for a robustness
* check: general imports include bonded warehouses and foreign trade zones,
* consumption imports do not, and for gold that gap is the phenomenon itself.
*==============================================================================

clear all
set more off
version 18

* Directories are globals, never locals. A local dies with the do-file, the
* program, or the quietly{} block that created it, so a path held in one
* silently becomes an empty string as soon as this code is split into
* subroutines, run interactively, or called from another do-file. Locals below
* are all scalars and counters, which is what they are for.
global proj "claude/gl-universe"
global out  "$proj/output"

capture log close
log using "$out/gl_results.log", replace text

*------------------------------------------------------------------ exports
* Collapse rather than reshape: DF=1 and DF=2 arrive as separate rows, and a
* commodity-month may have either, both, or neither.
use "$out/universe_exports.dta", clear
destring DF, replace
keep if inlist(DF, 1, 2)
gen double x_dom = ALL_VAL_MO if DF == 1
gen double x_re  = ALL_VAL_MO if DF == 2
collapse (sum) x_dom x_re, by(hs6 time)
tempfile exports
save `exports'

*------------------------------------------------------------------ imports
use "$out/universe_imports.dta", clear
rename GEN_VAL_MO m_gen
rename CON_VAL_MO m_con
recast double m_gen m_con

merge 1:1 hs6 time using `exports'
* _merge==1 imported but not exported, ==2 exported but not imported. Both are
* real one-way trade, not missing data, so the absent side is a true zero.
foreach v in x_dom x_re m_gen m_con {
    replace `v' = 0 if missing(`v')
}
drop _merge

gen mdate = monthly(time, "YM")
format mdate %tm
gen year = year(dofm(mdate))
label var mdate "month"

*------------------------------------------------------------------ the index
gen double x_tot = x_dom + x_re
gen double trade = x_tot + m_gen

gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen) if (x_tot + m_gen) > 0
gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen) if (x_dom + m_gen) > 0
gen double gl_con   = 1 - abs(x_tot - m_con) / (x_tot + m_con) if (x_tot + m_con) > 0
gen double wedge    = gl_total - gl_dom

label var gl_total "GL, exports incl. re-exports"
label var gl_dom   "GL, domestic exports only"
label var wedge    "re-export contamination of GL"

gen byte is7108 = substr(hs6, 1, 4) == "7108"
gen byte ch71   = substr(hs6, 1, 2) == "71"

compress
save "$out/gl_panel.dta", replace

*==============================================================================
* A. Coverage
*==============================================================================
display _n(2) "{hline 78}"
display "A. COVERAGE"
display "{hline 78}"
quietly count
local nobs = r(N)
quietly levelsof hs6, local(codes)
local ncodes : word count `codes'
quietly summarize mdate
display "commodity-months : " %9.0fc `nobs'
display "distinct HS6     : " %9.0fc `ncodes'
display "window           : " %tm r(min) " .. " %tm r(max)
quietly summarize trade
display "total trade      : " %12.1fc `=r(sum)/1e9' " bn USD"

*==============================================================================
* B. Economy-wide GL, trade-weighted, by year
*    GL_agg = 1 - sum|X-M| / sum(X+M).  This is the standard aggregate form;
*    it is NOT the mean of the commodity-level index.
*==============================================================================
display _n(2) "{hline 78}"
display "B. ECONOMY-WIDE GL, TRADE-WEIGHTED, ALL COMMODITIES"
display "{hline 78}"
display "  year      GL_total       GL_dom        wedge    trade_bnUSD"
display "  {hline 62}"
quietly levelsof year, local(yrs)
foreach y of local yrs {
    quietly {
        summarize x_tot if year == `y', meanonly
        local X = r(sum)
        summarize x_dom if year == `y', meanonly
        local XD = r(sum)
        summarize m_gen if year == `y', meanonly
        local M = r(sum)
        generate double _gap = abs(x_tot - m_gen) if year == `y'
        summarize _gap, meanonly
        local G = r(sum)
        drop _gap
        generate double _gapd = abs(x_dom - m_gen) if year == `y'
        summarize _gapd, meanonly
        local GD = r(sum)
        drop _gapd
    }
    local glt = 1 - `G' / (`X' + `M')
    local gld = 1 - `GD' / (`XD' + `M')
    display "  `y'      " %8.4f `glt' "     " %8.4f `gld' "     " ///
            %8.4f `=`glt' - `gld'' "     " %9.1fc `=(`X' + `M')/1e9'
}

*==============================================================================
* C. Cross-section of commodity-level GL
*    Restricted to commodity-months with at least $1m of combined trade. Below
*    that the index is dominated by rounding: a $4,000 export against a $3,900
*    import scores 0.99 and means nothing.
*==============================================================================
display _n(2) "{hline 78}"
display "C. DISTRIBUTION OF COMMODITY-LEVEL GL  (commodity-months >= 1m USD)"
display "{hline 78}"
summarize gl_total if trade >= 1e6, detail
display _n "same cross-section, re-exports removed:"
summarize gl_dom if trade >= 1e6, detail

*==============================================================================
* D. Gold
*==============================================================================
display _n(2) "{hline 78}"
display "D. HS 7108 -- GOLD, UNWROUGHT / SEMI-MANUFACTURED / POWDER"
display "{hline 78}"

preserve
    keep if is7108
    collapse (sum) x_dom x_re m_gen m_con, by(hs6 year)
    gen double x_tot = x_dom + x_re
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen) if (x_tot + m_gen) > 0
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen) if (x_dom + m_gen) > 0
    gen double wedge = gl_total - gl_dom
    gen double re_sh = x_re / x_tot if x_tot > 0
    gen double x_bn = x_tot / 1e9
    gen double m_bn = m_gen / 1e9
    format x_bn m_bn %8.2f
    format gl_total gl_dom wedge re_sh %8.3f
    list hs6 year x_bn m_bn gl_total gl_dom wedge re_sh, noobs abbrev(8) ///
         sepby(hs6)
restore

display _n "HS 7108 aggregated across subheadings, by year:"
preserve
    keep if is7108
    collapse (sum) x_dom x_re m_gen, by(year)
    gen double x_tot = x_dom + x_re
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen)
    gen double wedge = gl_total - gl_dom
    gen double x_bn = x_tot / 1e9
    gen double m_bn = m_gen / 1e9
    format x_bn m_bn %9.2f
    format gl_total gl_dom wedge %8.3f
    list year x_bn m_bn gl_total gl_dom wedge, noobs abbrev(10)
restore

*==============================================================================
* E. Where gold sits in the cross-section
*    Percentile rank of HS 7108's GL among all commodity-months with comparable
*    trade volume (1m USD+), computed within year so a rising gold price does
*    not move the rank on its own.
*==============================================================================
display _n(2) "{hline 78}"
display "E. GOLD PERCENTILE RANK IN THE GL CROSS-SECTION, BY YEAR"
display "{hline 78}"
display "  year   gold GL_total   pct of commodities below   n compared"
display "  {hline 66}"
foreach y of local yrs {
    quietly {
        summarize gl_total if is7108 & year == `y' & trade >= 1e6, meanonly
        local g = r(mean)
        count if !is7108 & year == `y' & trade >= 1e6 & !missing(gl_total)
        local n = r(N)
        count if !is7108 & year == `y' & trade >= 1e6 & gl_total < `g'
        local below = r(N)
    }
    if `n' > 0 {
        display "  `y'        " %8.4f `g' "                " ///
                %6.1f `=100 * `below' / `n'' "              " %8.0fc `n'
    }
}

*==============================================================================
* F. The re-export wedge, ranked
*    Which commodities have their GL most inflated by re-exports. If the wedge
*    is a general feature of trade, gold is unremarkable. If it is concentrated,
*    the concentration is the finding.
*==============================================================================
display _n(2) "{hline 78}"
display "F. LARGEST RE-EXPORT WEDGE, ANNUAL, COMMODITIES WITH >= 1bn USD TRADE"
display "{hline 78}"
preserve
    collapse (sum) x_dom x_re m_gen, by(hs6 year)
    gen double x_tot = x_dom + x_re
    gen double trade = x_tot + m_gen
    keep if trade >= 1e9
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen)
    gen double wedge = gl_total - gl_dom
    gen double awedge = abs(wedge)
    gen double trade_bn = trade / 1e9
    format trade_bn %9.1f
    format gl_total gl_dom wedge %8.3f

    display _n "ranked on |wedge|, either sign:"
    gsort -awedge
    list hs6 year gl_total gl_dom wedge trade_bn in 1/20, noobs abbrev(9)

    * Where gold sits in that same ranking, rather than only reporting the top.
    gen long rank = _n
    quietly count
    local ntot = r(N)
    display _n "HS 7108 in the same ranking (of `ntot' commodity-years >= 1bn USD):"
    list rank hs6 year gl_total gl_dom wedge trade_bn ///
         if substr(hs6, 1, 4) == "7108", noobs abbrev(9)
restore

*==============================================================================
* G. Monthly against annual, for gold
*    CLAUDE.md asserts annual aggregation erases the phenomenon. This tests it
*    rather than repeating it: within-year offsetting months cancel, so the
*    annual index is not the average of the monthly ones.
*==============================================================================
display _n(2) "{hline 78}"
display "G. GOLD GL AT MONTHLY VS ANNUAL FREQUENCY"
display "{hline 78}"
display "  year   mean of monthly GL   GL of annual totals   difference"
display "  {hline 64}"
foreach y of local yrs {
    quietly {
        preserve
        keep if is7108 & year == `y'
        collapse (sum) x_dom x_re m_gen, by(mdate)
        gen double x_tot = x_dom + x_re
        gen double gl_m = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
        summarize gl_m, meanonly
        local mean_monthly = r(mean)
        collapse (sum) x_tot m_gen
        local gl_annual = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
        restore
    }
    display "  `y'          " %8.4f `mean_monthly' "            " ///
            %8.4f `gl_annual' "        " %8.4f `=`gl_annual' - `mean_monthly''
}

*==============================================================================
* H. General vs consumption imports, gold only
*    GEN includes bonded warehouses and foreign trade zones; CON does not.
*    Metal sitting in a bonded warehouse is the phenomenon under study, so a
*    divergence here for gold and not elsewhere is itself a result.
*==============================================================================
display _n(2) "{hline 78}"
display "H. GOLD: GENERAL VS CONSUMPTION IMPORTS"
display "{hline 78}"
preserve
    keep if is7108
    collapse (sum) m_gen m_con x_tot, by(year)
    gen double gap_bn = (m_gen - m_con) / 1e9
    gen double gen_bn = m_gen / 1e9
    gen double con_bn = m_con / 1e9
    gen double gl_gen = 1 - abs(x_tot - m_gen) / (x_tot + m_gen)
    gen double gl_con = 1 - abs(x_tot - m_con) / (x_tot + m_con)
    format gen_bn con_bn gap_bn %9.2f
    format gl_gen gl_con %8.3f
    list year gen_bn con_bn gap_bn gl_gen gl_con, noobs abbrev(10)
    quietly summarize gap_bn
    if abs(r(max)) < 0.01 & abs(r(min)) < 0.01 {
        display _n "NEGATIVE RESULT. General and consumption imports of HS 7108 are"
        display "equal to within rounding in every year. The bonded-warehouse and"
        display "foreign-trade-zone channel is NOT visible in gold import statistics,"
        display "contrary to the expectation recorded in CLAUDE.md that this gap is"
        display "potentially load-bearing for gold. It cannot be used to separate"
        display "metal in bond from metal entering the economy."
    }
restore

*------------------------------------------------------------------ artefacts
preserve
    keep if is7108
    keep hs6 mdate year x_dom x_re x_tot m_gen m_con gl_total gl_dom gl_con wedge
    order hs6 mdate year
    sort hs6 mdate
    export delimited using "$out/gl_gold_monthly.csv", replace
restore

preserve
    collapse (sum) x_dom x_re m_gen m_con, by(hs6 year)
    gen double x_tot = x_dom + x_re
    gen double gl_total = 1 - abs(x_tot - m_gen) / (x_tot + m_gen) if (x_tot + m_gen) > 0
    gen double gl_dom   = 1 - abs(x_dom - m_gen) / (x_dom + m_gen) if (x_dom + m_gen) > 0
    gen double wedge = gl_total - gl_dom
    export delimited using "$out/gl_by_commodity_year.csv", replace
restore

display _n(2) "wrote gl_panel.dta, gl_gold_monthly.csv, gl_by_commodity_year.csv"
log close
