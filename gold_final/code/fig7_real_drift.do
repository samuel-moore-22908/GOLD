*! fig7_real_drift.do
*!
*! The drift this puts into real trade, on both sides of the account.
*!
*! THE POINT. The nominal distortion from gold is well known by now and a
*! reader can undo it: the gold line is published, and subtracting it is
*! arithmetic. The drift in the REAL series is neither. It is not published,
*! it cannot be recomputed from anything BLS releases, and because it
*! accumulates rather than reversing it does not wash out of a trend.
*!
*! THE ARITHMETIC. A price index applied to current trade should carry each
*! component at the share that trade actually has. The BLS index carries gold
*! at its share two years ago (see fig6_deflator_weights.do for the rule and
*! the source). The gap between what the index carries and what is being
*! deflated is a bias in measured inflation of
*!
*!     bias_t = (s_t - w_t) * (pi_gold,t - pi_nongold,t)
*!
*! with pi_nongold backed out of the published aggregate given w_t, and
*! pi_gold taken from BLS's OWN nonmonetary gold index rather than proxied by
*! the metal price. An understated deflator is an overstated volume, so the
*! cumulative sum of this term is the drift in real trade.
*!
*! WHAT IT COMES TO. Since January 2020, +1.7 index points on the import side
*! and +1.0 on the export side. Both are positive, so both real series are
*! overstated - but they arrive at completely different times, which is why
*! they do not cancel in the real balance. The import drift is a 2020 step and
*! a 2025 step. The export drift is slightly NEGATIVE all the way to 2024 and
*! then adds about 1.6 points in 2025 alone, and the export share is still
*! climbing in 2026 while the import share has gone home.
*!
*! A GAP, LEFT AS A GAP. BLS published no October 2025 value for either
*! all-commodities aggregate - the only month absent since 2015, and a
*! shutdown casualty. Both nonmonetary gold components WERE published that
*! month. Because the decomposition needs a month-on-month change in the
*! aggregate, neither October nor November 2025 is computable, and the drift
*! line breaks there rather than being drawn flat across the hole.
*!
*! This matters more than a missing month usually would, because October 2025
*! was the single largest gold export month in the sample at 9.1% of goods
*! exports. Bridging September to November - treating the two-month index
*! change as one observation - would add a further +0.91 points to the export
*! drift and -0.01 to imports, so the export figure reported here is the
*! CONSERVATIVE one. An earlier Python prototype of this calculation dropped
*! the October row and differenced November against September while weighting
*! it as a single month, which silently manufactured +0.77 points of export
*! drift. That number was wrong and is not used anywhere.
*!
*! WHAT IS NOT AFFECTED. Published GDP. BEA removes nonmonetary gold from the
*! national accounts outright, so the NIPA aggregates are not deflated through
*! these indexes. What is exposed is anything built on the trade release's own
*! real series, and nowcasts that bridge from it.
*!
*! HONEST LIMITS. The aggregate is chained monthly with a Lowe formula, so
*! relative importances drift within the year as prices move and this two-term
*! decomposition is an approximation to BLS's actual aggregation. And MXPI
*! excludes some trade that the Census totals include - military, used goods,
*! art - so gold's share of the index universe is marginally different from
*! its share of the trade totals used here.
*!
*! Reads   gold_final/data/raw/us_mxpi_monthly.csv
*!         gold_final/data/raw/us_deflator_inputs_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/real_drift.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig7_real_drift.do

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

local LAG    = 2              // BLS weight lag, in years
local BASE_M = tm(2020m1)     // the drift is cumulated from here

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
rename eiuir      p_m          // all commodities, imports
rename eiuiq      p_x          // all commodities, exports
rename eiuir14270 pg_m         // nonmonetary gold, imports
rename eiuiq12260 pg_x         // nonmonetary gold, exports
keep m p_m p_x pg_m pg_x
save `mxpi'

*======================================================== 3. totals, and merge
import delimited using "$RAW/us_deflator_inputs_monthly.csv", varnames(1) clear
destring bopgimp bopgexp, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m bopgimp bopgexp
merge 1:1 m using `gold', keep(match) nogen
merge 1:1 m using `mxpi', keep(match) nogen
sort m

gen double s_m = gold_m / (bopgimp * 1e6)
gen double s_x = gold_x / (bopgexp * 1e6)
gen int yr = year(dofm(m))

*=================================================== 4. the weight BLS carries
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

*============================================================== 5. the bias
foreach side in m x {
    gen double pi_pub_`side'  = ln(p_`side')  - ln(p_`side'[_n-1])
    gen double pi_gold_`side' = ln(pg_`side') - ln(pg_`side'[_n-1])
    * Non-gold inflation implied by the published aggregate at the weight the
    * index actually carries.
    gen double pi_ng_`side' = (pi_pub_`side' - w_`side' * pi_gold_`side') ///
                              / (1 - w_`side')
    gen double bias_`side' = (s_`side' - w_`side')                        ///
                             * (pi_gold_`side' - pi_ng_`side')
    * Cumulate from the base month. An understated deflator is an overstated
    * volume, so this cumulates straight into the real-series drift.
    gen double drift_`side' = 100 * sum(cond(m > `BASE_M', bias_`side', 0))
    replace drift_`side' = . if m < `BASE_M'
}

*============================================ 5b. the gap, named out loud
* Any month where the aggregate is missing cannot be decomposed, and neither
* can the month after it, which needs that month as its base. Report them
* rather than letting sum() quietly treat them as zero.
gen byte nogap_m = !missing(bias_m)
gen byte nogap_x = !missing(bias_x)
replace drift_m = . if m > `BASE_M' & missing(bias_m)
replace drift_x = . if m > `BASE_M' & missing(bias_x)

di as txt "{hline 70}"
di as txt "Months since 2020 that cannot be decomposed (aggregate index absent)"
levelsof m if m > `BASE_M' & missing(bias_m), local(HOLES_M)
levelsof m if m > `BASE_M' & missing(bias_x), local(HOLES_X)
foreach h of local HOLES_M {
    local lbl : display %tmMon_CCYY `h'
    di as txt "   imports  " trim("`lbl'")
}
foreach h of local HOLES_X {
    local lbl : display %tmMon_CCYY `h'
    di as txt "   exports  " trim("`lbl'")
}
di as txt "   The drift line BREAKS at these months rather than being drawn"
di as txt "   flat across them, so the totals below are conservative."

*=========================================================== 6. what it says
di as txt "{hline 70}"
di as txt "Cumulative drift in real trade since January 2020, index points"
di as txt "   year    imports    exports"
forvalues y = 2020/2026 {
    qui summarize drift_m if yr == `y', meanonly
    local DM = r(max)
    qui summarize drift_x if yr == `y', meanonly
    local DX = r(max)
    qui summarize m if yr == `y' & !missing(drift_m), meanonly
    local LM = r(max)
    qui summarize drift_m if m == `LM', meanonly
    local DM = r(mean)
    qui summarize drift_x if m == `LM', meanonly
    local DX = r(mean)
    di as txt "   `y'  " %9.2f `DM' "  " %9.2f `DX'
}
di as txt ""
di as txt "What the drift is worth in volume, at that year's nominal trade"
foreach y in 2024 2025 {
    qui summarize m if yr == `y' & !missing(drift_m), meanonly
    local LM = r(max)
    qui summarize drift_m if m == `LM', meanonly
    local DM = r(mean)
    qui summarize drift_x if m == `LM', meanonly
    local DX = r(mean)
    qui summarize bopgimp if yr == `y'
    local IM = r(sum) / 1000
    qui summarize bopgexp if yr == `y'
    local IX = r(sum) / 1000
    local VM = `IM' * `DM' / 100
    local VX = `IX' * `DX' / 100
    local VB = `VX' - `VM'
    di as txt "   `y': real imports " %6.0f `VM' "bn   real exports " ///
        %6.0f `VX' "bn   real balance " %6.0f `VB' "bn"
}
di as txt "{hline 70}"

* Endpoint labels, written into the figure rather than typed by hand.
qui summarize m if !missing(drift_m), meanonly
local MEND = r(max)
qui summarize drift_m if m == `MEND', meanonly
local END_M = r(mean)
qui summarize drift_x if m == `MEND', meanonly
local END_X = r(mean)

*=========================================================== 7. the figure
qui summarize m if !missing(drift_m), meanonly
local M0 = r(min)
local M1 = r(max)
local Y0 = year(dofm(`M0'))
local Y1 = year(dofm(`M1'))
local XMIN = `M0' - 1
local XMAX = `M1' + 13       // room for the endpoint labels

local XLAB ""
forvalues y = `Y0'/`Y1' {
    local XLAB `XLAB' `=tm(`y'm1)' "`y'"
}

gen double mplot = m + 0.5

* THE `if' MATTERS. xscale(range()) can only EXTEND an axis, never clip it,
* and the axis is sized from every observation a plot command touches - not
* from the non-missing ones. The dataset starts in 2015, so without this
* restriction the scale ran from 2015 even though both series are missing
* until 2020, and the drawn data was squeezed into the right half of an
* otherwise empty panel.
twoway                                                                      ///
    (line drift_m mplot if m >= `BASE_M', lcolor("`RED'") lwidth(0.60)      ///
        cmissing(n))                                                        ///
    (line drift_x mplot if m >= `BASE_M', lcolor("`INK'") lwidth(0.50)      ///
        lpattern(dash) cmissing(n))                                         ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.25))                                 ///
    text(`END_M' `=`MEND'+2' "Real imports", size(vsmall) color("`RED'")    ///
         placement(e) justification(left))                                  ///
    text(`END_X' `=`MEND'+2' "Real exports", size(vsmall) color("`INK'")    ///
         placement(e) justification(left))                                  ///
    title("███", size(vsmall) color("`RED'") position(11)                   ///
          justification(left))                                              ///
    subtitle("{bf:The nominal distortion reverses. The drift in real trade does not}" ///
             "Cumulative overstatement of real US goods trade from gold's weight in the deflator, index points, January 2020 = 0", ///
             size(small) color("`INK'") position(11) justification(left))   ///
    ytitle("Index points", size(vsmall) color("`SOFT'"))                    ///
    ylabel(-0.5(0.5)2, format(%3.1f) angle(0) labsize(vsmall)               ///
           tlcolor(none) labcolor("`SOFT'") grid glcolor("`RULE'")          ///
           glwidth(0.28))                                                   ///
    yscale(range(-0.7 2.1) noextend lcolor(none))                           ///
    xtitle("")                                                              ///
    xlabel(`XLAB', labsize(vsmall) tlcolor(none) labcolor("`SOFT'") nogrid) ///
    xscale(range(`XMIN' `XMAX') noextend lcolor("`RULE'"))                  ///
    legend(off)                                                             ///
    note("Bias in measured inflation is (actual share - carried weight) x (gold inflation - non-gold inflation), cumulated. Gold inflation is BLS's own nonmonetary" ///
         "gold index for each side (EIUIR14270, EIUIQ12260), not a proxy; non-gold inflation is backed out of the published aggregate at the weight the index carries." ///
         "An understated deflator is an overstated volume, so a rising line means real trade is measured too high. Both sides end up overstated, but they arrive at" ///
         "different times and so do not cancel: the import drift is a 2020 step and a 2025 step, while the export drift is slightly negative until 2024 and then adds" ///
         "1.6 points in 2025 alone. At 2025 nominal trade the two are worth about {c $|}57bn of real imports and {c $|}20bn of real exports that were never there." ///
         "The break in late 2025 is a real hole: BLS published no October 2025 value for either aggregate, the only month absent since 2015, so neither October nor" ///
         "November can be decomposed. Both gold components WERE published. Bridging September to November would add a further 0.9 points to the export drift, so the" ///
         "line as drawn understates it." ///
         "This does NOT affect published GDP - BEA removes nonmonetary gold from the national accounts - but it does affect real series built from the trade release." ///
         "Approximation: the aggregate is chained monthly with a Lowe formula, so this two-term decomposition is close to, not identical with, BLS's aggregation." ///
         "Source: Bureau of Labor Statistics; US Census Bureau; Bureau of Economic Analysis.", ///
         size(vsmall) color("`SOFT'") position(7) span)                     ///
    graphregion(color(white) margin(l=2 r=1 t=2 b=2))                       ///
    plotregion(color(white) margin(zero) lcolor(none))                      ///
    ysize(5.4) xsize(9.6)                                                   ///
    name(drift, replace)

graph export "$FIG/real_drift.pdf", replace
di as txt "wrote $FIG/real_drift.pdf"

capture graph set window fontface "$RESTORE_FONT"
