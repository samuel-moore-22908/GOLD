*! fig3_counterfactual.do
*!
*! How much gold crossed into the United States that otherwise would not have.
*!
*! Back of the envelope, deliberately. Fit a straight line to US gold imports
*! over every month before the tariff episode, carry it forward unchanged, and
*! measure the area between the actual series and that line.
*!
*! FITTED TO THE WHOLE PRE-PERIOD, January 2015 to October 2024, not to a recent
*! slice. A short window is open to the charge that it was chosen to flatter the
*! result; the long one is not, and the line is drawn across the whole chart so
*! the fit can be judged against the data that produced it.
*!
*! MEASURED ON THE US SIDE. Census reports value, not mass, for these headings,
*! so tonnage here is DERIVED: the month's customs value divided by the LBMA PM
*! benchmark. That is a different measurement of the same flow from the Swiss
*! and UK export figures used earlier in this project, which carry mass
*! directly, and the two will not agree to the tonne.
*!
*! Reads   gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/lbma_pm.csv
*! Writes  gold_final/figures/counterfactual.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig3_counterfactual.do

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

global RESTORE_FONT "`c(graphfontface)'"
graph set window fontface "Arial Narrow"

local RED  "227 18 11"
local INK  "18 18 18"
local GREY "117 141 153"
local RULE "224 228 231"
local SOFT "112 112 112"

* The break is the US election, when tariff risk became priceable. The episode
* ends the month before the April 2025 exemption removed it again.
local BREAK   = tm(2024m11)
local EPI_END = tm(2025m3)
local OZ_PER_TONNE = 32150.7

tempfile px

*================================================================== 1. the price
import delimited using "$RAW/lbma_pm.csv", varnames(1) clear
destring lbma_pm_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (mean) price = lbma_pm_usd, by(m)
format m %tm
save `px'

*================================================================== 2. the metal
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
keep if flow == "imports"
gen double m = mofd(date(date, "YMD"))
format m %tm
collapse (sum) value_usd, by(m)
merge 1:1 m using `px', keep(match) nogen
sort m

* Derived mass, tagged as such everywhere it appears. Customs value for bullion
* is its market value, so the month's benchmark recovers the quantity.
gen double tonnes = value_usd / price / `OZ_PER_TONNE'

*=========================================================== 3. the baseline
* A time index rather than the Stata month number, so the intercept is the
* fitted level at the start of the sample and reads as a tonnage.
qui summarize m, meanonly
local MLO = r(min)
local MHI = r(max)
gen double t = m - `MLO'

qui regress tonnes t if m < `BREAK'
local SLOPE = _b[t]
local NPRE  = e(N)
predict double baseline, xb

* NOT clipped at zero. A clip would put a kink in what is meant to be a
* straight line, and the whole claim of the figure is that the baseline is one
* straight extrapolation and nothing else. Warn instead if it ever goes
* negative over the plotted window.
qui count if baseline < 0
if r(N) > 0 {
    di as err "WARNING: the fitted line goes negative in " r(N) " month(s)."
    di as err "         It is drawn as fitted; do not clip it silently."
}

gen double excess = tonnes - baseline if m >= `BREAK'

*=========================================================== 4. what it says
qui summarize excess if m >= `BREAK'
local EX_ALL = r(sum)
local N_POST = r(N)
qui summarize excess if m >= `BREAK' & m <= `EPI_END'
local EX_EPI = r(sum)
qui count if m >= `BREAK' & excess < 0
local N_BELOW = r(N)
qui summarize excess if m >= `BREAK' & excess > 0
local EX_POS = r(sum)
qui summarize baseline if m == tm(2025m1), meanonly
local BASE_JAN = r(mean)
qui summarize tonnes if m < `BREAK', meanonly
local PRE_MEAN = r(mean)

di as txt "pre-period months : " `NPRE' "   mean " %5.1f `PRE_MEAN' " t"
di as txt "fitted slope      : " %6.3f `SLOPE' " t a month, reaching " %5.1f `BASE_JAN' " t by 2025m1"
di as txt "excess, episode   : " %6.0f `EX_EPI' " t"
di as txt "excess, all `N_POST' mo: " %6.0f `EX_ALL' " t  (positive-only " %6.0f `EX_POS' ", " `N_BELOW' " months below)"

*=========================================================== 5. the figure
* Shade only the months after the break, and only where the actual series is
* above the line. cmissing(n) so the area breaks at the months that fall below
* it instead of being drawn straight across them.
gen double hi = tonnes   if m >= `BREAK' & tonnes > baseline
gen double lo = baseline if m >= `BREAK' & tonnes > baseline
gen double pre_t  = tonnes if m <  `BREAK'
gen double post_t = tonnes if m >= `BREAK' - 1     // overlap one month so the
                                                   // grey and red lines join

local Y0 = year(dofm(`MLO'))
local Y1 = year(dofm(`MHI'))
local XLAB `=tm(`Y0'm1)'(12)`=tm(`Y1'm1)'
* Top of the y axis from the data, rounded up to a round number, so the peak
* never sits above the last gridline the way a hard-coded ceiling lets it.
qui summarize tonnes, meanonly
local YMAX = ceil(r(max) / 50) * 50
local PRE_LO : display %tmMonth_CCYY `MLO'
local PRE_HI : display %tmMonth_CCYY `=`BREAK'-1'
local PRE_LO = trim("`PRE_LO'")
local PRE_HI = trim("`PRE_HI'")

twoway                                                                      ///
    (rarea hi lo m, color("`RED'%22") lwidth(none) cmissing(n))             ///
    (line baseline m, lcolor("`INK'") lwidth(0.30) lpattern(shortdash))     ///
    (line pre_t m, lcolor("`GREY'") lwidth(0.45) cmissing(n))               ///
    (line post_t m, lcolor("`RED'") lwidth(0.70) cmissing(n))               ///
    ,                                                                       ///
    title("███", size(vsmall) color("`RED'")                                ///
          position(11) justification(left))                                 ///
    subtitle("{bf:About `=string(`EX_ALL', "%4.0f")' tonnes of gold crossed that otherwise would not have}" ///
             "Gold imported by the United States, against a line fitted by least squares to all `NPRE' months from `PRE_LO' to `PRE_HI'" ///
             "and then carried forward unchanged. The shaded area since is `=string(`EX_ALL', "%4.0f")' tonnes, after netting off the `N_BELOW' months that fall below the line;" ///
             "the five-month episode alone is `=string(`EX_EPI', "%4.0f")'", ///
             size(small) color("`INK'") position(11) justification(left))   ///
    ytitle("Tonnes a month, derived from customs value", size(vsmall)       ///
           color("`SOFT'"))                                                 ///
    ylabel(0(50)`YMAX', angle(0) labsize(vsmall) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xline(`BREAK', lcolor("`SOFT'") lwidth(0.22) lpattern(dot))             ///
    legend(off)                                                             ///
    note("Census reports value, not mass, for HS 7108 and 7115, so tonnage is DERIVED: the month's customs value divided by the LBMA PM benchmark." ///
         "Measured on the US side, so it will not agree to the tonne with the Swiss and UK export figures, which carry mass directly. The dotted" ///
         "vertical is the November 2024 election. The baseline is drawn across the whole chart, including the months it was fitted to" ///
         " "                                                                ///
         "Source: US Census Bureau; LBMA",                                  ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    graphregion(color(white) lcolor(white) margin(l=3 r=4 t=1 b=1))         ///
    plotregion(color(white) lstyle(none) margin(l=1 r=1 t=3 b=1))           ///
    xsize(11) ysize(6.4) name(gCF, replace)

cap mkdir "$FIG"
graph export "$FIG/counterfactual.pdf", replace name(gCF)
di as txt "wrote $FIG/counterfactual.pdf"

if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
