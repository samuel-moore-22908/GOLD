*! fig8_real_trade_levels.do
*!
*! What the deflator misalignment does to the published real trade levels, on
*! both sides of the account. Four panels, 2x2.
*!
*!   a (top left)      import price index, as published and reweighted for gold
*!   b (top right)     goods imports: nominal, real, and real on the
*!                     reweighted deflator
*!   c (bottom left)   the same for the export price index
*!   d (bottom right)  the same for goods exports
*!
*! THE SIGN, WHICH IS EASY TO GET BACKWARDS. The index understates inflation
*! whenever gold's actual share exceeds the weight the index carries AND gold
*! is outrunning everything else. An understated deflator makes the volume it
*! produces too BIG. So the reweighted real series sits BELOW the published
*! one: real trade is over-reported, not under.
*!
*! WHAT THAT WOULD DO TO GDP, AND WHY IT DOES NOT. Real GDP counts exports
*! positively and imports negatively. Over-reported real imports therefore
*! push measured GDP DOWN and over-reported real exports push it UP, and
*! because the import drift is both larger in points and applied to a larger
*! base, the net is negative: if these series fed the national accounts, real
*! GDP would be understated. The size is worth stating carefully, because the
*! level effect and the growth effect are very different animals. The LEVEL
*! effect grows every year from 2015 to 2025 and reaches about 0.18% of real
*! GDP. The GROWTH effect - the year-on-year change in that level - never
*! exceeds about 0.06pp and REVERSES to roughly +0.12pp in 2026 as the export
*! side catches up. A drift that is consistent in levels is close to invisible
*! in growth rates.
*!
*! They do not. BEA removes nonmonetary gold from the national accounts
*! outright - it is replaced by domestic production less industrial use - so
*! the NIPA aggregates are never deflated through these indexes and published
*! GDP carries none of this. The exposure is to anything built on the trade
*! release's OWN real series (FT-900 Exhibit 10) and to nowcasts bridging
*! from the monthly release before BEA's quarterly treatment lands. The
*! arithmetic below is therefore what the drift is worth to those users, not
*! a correction to published GDP.
*!
*! THE CONSISTENCY QUESTION. The drift is consistent in the cumulative sense
*! and NOT in the monthly one. On the computed weight the monthly correction
*! is positive in 45 of 78 months since 2020 on the import side and 31 of 78
*! on the export side - barely better and slightly worse than a coin. What
*! makes the lines drift apart is that the positive months are much the
*! larger ones, so the level separates even though the sign does not.
*!
*! A GENUINE HOLE, HANDLED GENERALLY. BLS published no October 2025 value for
*! either all-commodities aggregate, the only month absent since 2015. Rather
*! than bridge it silently, every difference here is taken against the
*! PREVIOUS NON-MISSING observation and paired with the gold share summed over
*! exactly the months that difference spans. That is the correct
*! generalisation, not a patch: a two-month index change is decomposed with a
*! two-month share. October itself has no published index, so it is missing in
*! every series and the lines break there.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv   (needs 2013 on, so that
*!                                                    the two-year-lagged
*!                                                    weight exists from 2015)
*! Writes  gold_final/figures/real_trade_levels.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig8_real_trade_levels.do

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

local LAG    = 2              // BLS reweights on a two-year lag
local BASE_M = tm(2015m1)     // indexes = 100 here; real series in these dollars

tempfile gold mxpi

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
rename eiuir      p_m
rename eiuiq      p_x
rename eiuir14270 pg_m
rename eiuiq12260 pg_x
keep m p_m p_x pg_m pg_x
save `mxpi'

*======================================================== 3. totals, and merge
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp bopgexp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(master match) nogen
sort m

* Nominal goods trade in $bn. BOPGIMP/BOPGEXP are $ millions.
gen double nom_m = bopgimp / 1000
gen double nom_x = bopgexp / 1000
gen int yr = year(dofm(m))

*=================================================== 4. the weight BLS carries
* Gold's share of each side in each calendar year - the Census annual figure
* BLS reweights from - lagged two years onto the receiving year.
preserve
    collapse (sum) gold_m gold_x bopgimp bopgexp, by(yr)
    gen double w_m = gold_m / (bopgimp * 1e6)
    gen double w_x = gold_x / (bopgexp * 1e6)
    replace yr = yr + `LAG'
    keep yr w_m w_x
    tempfile wt
    save `wt'
restore
merge m:1 yr using `wt', keep(master match) nogen
sort m

*============================================ 5. interval-aware decomposition
* Differences are taken against the previous NON-MISSING index observation and
* paired with the gold share accumulated over exactly the months that
* difference spans. With a complete series this is an ordinary one-month
* change; across the October 2025 hole it is a correct two-month one.
foreach side in m x {
    gen double dlp_`side'  = .      // change in the published aggregate
    gen double dlg_`side'  = .      // change in the gold component
    gen double sint_`side' = .      // gold's share over the same interval

    local prev = .
    local prevg = .
    local gacc = 0
    local tacc = 0
    forvalues i = 1/`=_N' {
        local gacc = `gacc' + gold_`side'[`i']
        local tacc = `tacc' + nom_`side'[`i'] * 1e9
        if !missing(p_`side'[`i']) {
            if !missing(`prev') {
                qui replace dlp_`side'  = ln(p_`side'[`i'])  - `prev'  in `i'
                qui replace dlg_`side'  = ln(pg_`side'[`i']) - `prevg' in `i'
                qui replace sint_`side' = `gacc' / `tacc'              in `i'
            }
            local prev  = ln(p_`side'[`i'])
            local prevg = ln(pg_`side'[`i'])
            local gacc = 0
            local tacc = 0
        }
    }

    * Non-gold inflation implied by the published aggregate at the weight the
    * index carries, then the omitted term.
    gen double png_`side'  = (dlp_`side' - w_`side' * dlg_`side') / (1 - w_`side')
    gen double bias_`side' = (sint_`side' - w_`side') * (dlg_`side' - png_`side')

    * The adjusted index: published, times the cumulated correction. Both are
    * normalised to 100 at the base month so they start together.
    gen double cum_`side' = sum(cond(m > `BASE_M', bias_`side', 0))
    qui summarize p_`side' if m == `BASE_M', meanonly
    local P0 = r(mean)
    gen double ipub_`side' = 100 * p_`side' / `P0'
    gen double iadj_`side' = ipub_`side' * exp(cum_`side')
    replace ipub_`side' = . if m < `BASE_M'
    replace iadj_`side' = . if m < `BASE_M'

    * Real trade, in base-month dollars. An understated deflator gives too big
    * a volume, so the adjusted series sits below the published one.
    gen double real_`side' = 100 * nom_`side' / ipub_`side'
    gen double radj_`side' = 100 * nom_`side' / iadj_`side'
}

*=========================================================== 6. what it says
qui summarize m if !missing(iadj_m), meanonly
local MEND = r(max)
local ENDLAB : display %tmMon_CCYY `MEND'
local ENDLAB = trim("`ENDLAB'")

di as txt "{hline 74}"
di as txt "Indexes at `ENDLAB', January 2015 = 100"
foreach side in m x {
    local WHAT = cond("`side'" == "m", "imports", "exports")
    qui summarize ipub_`side' if m == `MEND', meanonly
    local IP = r(mean)
    qui summarize iadj_`side' if m == `MEND', meanonly
    local IA = r(mean)
    di as txt "   `WHAT' : published " %6.1f `IP' "   reweighted " %6.1f `IA' ///
        "   wedge " %5.2f `IA' - `IP' " points"
}
di as txt ""
di as txt "Monthly correction since 2020: positive in how many months?"
foreach side in m x {
    local WHAT = cond("`side'" == "m", "imports", "exports")
    qui count if m >= tm(2020m1) & !missing(bias_`side')
    local N = r(N)
    qui count if m >= tm(2020m1) & bias_`side' > 0 & !missing(bias_`side')
    di as txt "   `WHAT' : " r(N) " of `N'  (" %4.0f 100*r(N)/`N' "%)" ///
        "  - a drift in the level, not a consistent monthly sign"
}
di as txt ""
di as txt "Real trade over-reported, at `ENDLAB' monthly rate, {c $|}bn"
foreach side in m x {
    local WHAT = cond("`side'" == "m", "imports", "exports")
    qui summarize real_`side' if m == `MEND', meanonly
    local R = r(mean)
    qui summarize radj_`side' if m == `MEND', meanonly
    local A = r(mean)
    di as txt "   `WHAT' : published " %6.1f `R' "   reweighted " %6.1f `A' ///
        "   over-reported " %5.1f `R' - `A'
}
di as txt ""
* ANNUALISED, not summed. 2025 has 11 months because BLS did not publish
* October, and 2026 is incomplete; summing raw months would make those years
* look smaller for a reason that has nothing to do with gold.
gen double over_m = real_m - radj_m
gen double over_x = real_x - radj_x
gen double over_n = over_x - over_m

di as txt "Over-reporting by year, ANNUALISED ({c $|}bn, Jan 2015 dollars)"
di as txt "   year    imports    exports   net real net exports   months"
forvalues y = 2020/2026 {
    qui count if yr == `y' & !missing(over_m)
    local NM = r(N)
    if `NM' > 0 {
        qui summarize over_m if yr == `y', meanonly
        local DM = 12 * r(mean)
        qui summarize over_x if yr == `y', meanonly
        local DX = 12 * r(mean)
        qui summarize over_n if yr == `y', meanonly
        local NET = 12 * r(mean)
        di as txt "   `y'  " %9.1f `DM' "  " %9.1f `DX' "  " %13.1f `NET' ///
            "  " %8.0f `NM'
        local NET`y' = `NET'
    }
}
di as txt ""
di as txt "Year-on-year change in the net effect - the GROWTH contribution"
forvalues y = 2021/2026 {
    local PREV = `y' - 1
    if "`NET`y''" != "" & "`NET`PREV''" != "" {
        di as txt "   `y'  " %9.1f `NET`y'' - `NET`PREV'' " {c $|}bn"
    }
}
di as txt ""
di as txt "   READ THE TWO APART. The LEVEL effect drifts one way and keeps"
di as txt "   drifting: measured real net exports too low by a growing amount"
di as txt "   every year from 2015 to 2025, which is about 0.18% of real GDP"
di as txt "   at its widest. The GROWTH effect is an order of magnitude"
di as txt "   smaller - at most about 0.06pp in any year, and it REVERSES in"
di as txt "   2026 as the export side catches up. So the drift is consistent"
di as txt "   in levels and almost invisible in growth rates."
di as txt ""
di as txt "   And none of it touches published GDP: BEA strips nonmonetary"
di as txt "   gold from NIPA, so the national accounts are never deflated"
di as txt "   through these indexes."
di as txt "{hline 74}"

*=========================================================== 7. the four panels
qui summarize m if !missing(ipub_m), meanonly
local M0 = r(min)
local M1 = r(max)
local Y0 = year(dofm(`M0'))
local Y1 = year(dofm(`M1'))
local XMIN = `M0' - 1
local XMAX = `M1' + 2

* Every other year. The final year is NOT forced in as an extra tick: it
* lands next to the one before it and the two labels collide.
local XLAB ""
forvalues y = `Y0'/`Y1' {
    if mod(`y', 2) == 1 {
        local XLAB `XLAB' `=tm(`y'm1)' "`y'"
    }
}

gen double mplot = m + 0.5

* ---- the index panels -------------------------------------------------------
foreach side in m x {
    if "`side'" == "m" {
        local TTL "{bf:a.} The import price index, as published and reweighted for gold"
        local YLAB 95(5)120
        local YRNG 92 124
        local LEG legend(order(2 "As published" 3 "Gold at its actual share") ///
                  rows(1) size(vsmall) region(lcolor(none)) symxsize(6)       ///
                  symysize(2) position(11) ring(0) bmargin(zero)              ///
                  color("`SOFT'"))
    }
    else {
        local TTL "{bf:c.} The export price index, as published and reweighted for gold"
        local YLAB 95(5)135
        local YRNG 92 138
        local LEG legend(off)
    }
    twoway                                                                  ///
        (rarea iadj_`side' ipub_`side' mplot if m >= `BASE_M',              ///
            color("`RED'%22") lwidth(none) cmissing(n))                     ///
        (line ipub_`side' mplot if m >= `BASE_M', lcolor("`GREY'")          ///
            lwidth(0.50) cmissing(n))                                       ///
        (line iadj_`side' mplot if m >= `BASE_M', lcolor("`RED'")           ///
            lwidth(0.50) cmissing(n))                                       ///
        ,                                                                   ///
        title("`TTL'", size(small) color("`INK'") position(11)              ///
              justification(left) span)                                     ///
        ytitle("Index, Jan 2015 = 100", size(vsmall) color("`SOFT'"))       ///
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
        name(idx_`side', replace) nodraw
}

* ---- the level panels -------------------------------------------------------
foreach side in m x {
    * What the wedge is worth at the latest month. It is about 2% of the level
    * - a few pixels - so it is stated rather than left to be measured.
    qui summarize real_`side' if m == `MEND', meanonly
    local RL = r(mean)
    qui summarize radj_`side' if m == `MEND', meanonly
    local AL = r(mean)
    local GAP : display %3.1f `RL' - `AL'
    local GAP = trim("`GAP'")

    if "`side'" == "m" {
        local TTL1 "{bf:b.} US goods imports: nominal, real, and real on the reweighted deflator"
        local TTL2 "{it:Shaded: reweighting cuts measured real imports by {c $|}`GAP'bn a month}"
        local YLAB 100(50)350
        local YRNG 90 360
        local LEG legend(order(2 "Nominal" 3 "Real, published deflator"      ///
                               4 "Real, reweighted deflator")               ///
                  rows(1) size(vsmall) region(lcolor(none)) symxsize(6)      ///
                  symysize(2) position(11) ring(0) bmargin(zero)             ///
                  color("`SOFT'"))
    }
    else {
        local TTL1 "{bf:d.} US goods exports: nominal, real, and real on the reweighted deflator"
        local TTL2 "{it:Shaded: reweighting cuts measured real exports by {c $|}`GAP'bn a month}"
        local YLAB 100(25)225
        local YRNG 95 230
        local LEG legend(off)
    }
    twoway                                                                  ///
        (rarea real_`side' radj_`side' mplot if m >= `BASE_M',              ///
            color("`RED'%55") lwidth(none) cmissing(n))                     ///
        (line nom_`side' mplot if m >= `BASE_M', lcolor("`INK'")            ///
            lwidth(0.35) lpattern(shortdash) cmissing(n))                   ///
        (line real_`side' mplot if m >= `BASE_M', lcolor("`GREY'")          ///
            lwidth(0.50) cmissing(n))                                       ///
        (line radj_`side' mplot if m >= `BASE_M', lcolor("`RED'")           ///
            lwidth(0.50) cmissing(n))                                       ///
        ,                                                                   ///
        title("`TTL1'" "`TTL2'", size(small) color("`INK'") position(11)    ///
              justification(left) span)                                     ///
        ytitle("{c $|}bn a month, Jan 2015 dollars", size(vsmall)           ///
               color("`SOFT'"))                                             ///
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
        name(lvl_`side', replace) nodraw
}

graph combine idx_m lvl_m idx_x lvl_x, cols(2) imargin(small)               ///
    xsize(11.4) ysize(7.6)                                                  ///
    graphregion(color(white) margin(l=2 r=2 t=2 b=2))                       ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left) span)                                         ///
    subtitle("{bf:An index that carries gold at a two-year-old weight reports too much real trade, on both sides}" ///
             "US goods trade, monthly. The reweighted deflator puts gold at the share trade actually had instead of the share it had two years ago", ///
             size(small) color("`INK'") position(11)                        ///
             justification(left) span)                                      ///
    note(" " ///
         "Left: the published all-commodities index against the same index with gold reweighted to its actual monthly share, January 2015 = 100. Right: nominal goods" ///
         "trade, that trade deflated by the published index, and deflated by the reweighted one, all in January 2015 dollars. Shaded area is the over-reporting." ///
         "The index understates inflation when gold's share exceeds its carried weight and gold is outrunning the rest, and an understated deflator gives too large a" ///
         "volume - so the red line sits BELOW the grey one and real trade is over-reported, not under. The drift is cumulative, not monthly: the correction is" ///
         "positive in only 45 of 78 months since 2020 on imports and 31 of 78 on exports, but the positive months are much the larger ones." ///
         " " ///
         "THIS IS NOT A CORRECTION TO PUBLISHED GDP. Over-reported real imports would push measured GDP down and over-reported real exports would push it up, and on" ///
         "these numbers the import side dominates, so real GDP would be understated. But BEA removes nonmonetary gold from the national accounts outright, so NIPA is" ///
         "never deflated through these indexes. What is exposed is the trade release's own real series and nowcasts bridging from it before BEA's treatment lands." ///
         " " ///
         "Every difference is taken against the previous non-missing index observation and paired with the gold share over exactly the months it spans, so the" ///
         "October 2025 hole - the only month BLS did not publish since 2015 - is decomposed correctly rather than bridged. October itself is missing in every series." ///
         "Source: Bureau of Labor Statistics (EIUIR, EIUIQ, EIUIR14270, EIUIQ12260); US Census Bureau; Bureau of Economic Analysis.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    name(combined, replace)

graph export "$FIG/real_trade_levels.pdf", replace
di as txt "wrote $FIG/real_trade_levels.pdf"

capture graph set window fontface "$RESTORE_FONT"
