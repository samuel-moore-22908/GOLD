*! fig2b_net_metal.do
*!
*! Net gold shipped to and from the United States, monthly. This is the lower
*! panel of fig2_spread_vs_hurdle.do rebuilt as a figure in its own right.
*!
*! IT STARTS FROM THE TRADE DATA. In fig2 this panel is a by-product: the script
*! spends two hundred lines on the futures curve, the premium and the re-timing
*! before it gets anywhere near a tonne, and the flow series is assembled at the
*! end from whatever is still in memory. Here the trade data is the baseline and
*! the only other input is the price needed to turn customs value into mass. It
*! reads two CSVs and nothing else, which means it can be checked, rerun and
*! argued with on its own.
*!
*! TONNAGE IS DERIVED. Census reports value and not mass for HS 7108 and 7115,
*! so each month's customs value is divided by that month's LBMA PM benchmark.
*! That is a different measurement of the same flow from the Swiss and UK export
*! returns, which carry mass directly, and the two will not agree to the tonne.
*!
*! Both headings, always: 7108 is gold unwrought and 7115 is where the bars were
*! booked during the 2024-25 episode. 7108 alone misses most of it.
*!
*! Reads   gold_final/data/raw/us_gold_monthly.csv
*!         gold_final/data/raw/lbma_pm.csv
*! Writes  gold_final/figures/net_metal.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig2b_net_metal.do

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
graph set window fontface "Arial Narrow"

local RED  "227 18 11"
local INK  "18 18 18"
local GREY "117 141 153"
local RULE "224 228 231"
local SOFT "112 112 112"

local OZ_PER_TONNE = 32150.7
local EP_LO = tm(2024m12)       // the episode, first full month of the surge
local EP_HI = tm(2025m3)        // the month before the April exemption
local RV_LO = tm(2025m4)
local RV_HI = tm(2025m8)

tempfile px

*================================================================== 1. the price
* Monthly mean of the London PM benchmark. Only needed to convert value to mass.
import delimited using "$RAW/lbma_pm.csv", varnames(1) clear
destring lbma_pm_usd, replace force
gen double m = mofd(date(date, "YMD"))
collapse (mean) price = lbma_pm_usd, by(m)
format m %tm
save `px'

*================================================================== 2. the trade
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
collapse (sum) value_usd, by(m flow)
reshape wide value_usd, i(m) j(flow) string
rename value_usdimports imports_usd
rename value_usdexports exports_usd

merge 1:1 m using `px', keep(match) nogen
sort m

* Positive is net INTO the United States. The sign convention matters here:
* over most of this sample it is negative, because the United States is
* normally a net exporter of gold.
gen double net_t = (imports_usd - exports_usd) / price / `OZ_PER_TONNE'
gen double imports_t = imports_usd / price / `OZ_PER_TONNE'
gen double exports_t = exports_usd / price / `OZ_PER_TONNE'

*=========================================================== 3. what it says
qui count
local NM = r(N)
qui count if net_t < 0
local N_EAST = r(N)
qui summarize net_t if m >= `EP_LO' & m <= `EP_HI'
local EP = r(sum)
local EP_N = r(N)
qui summarize net_t if m >= `RV_LO' & m <= `RV_HI'
local RV = r(sum)
local RV_N = r(N)
* The peak month is found by sorting, not by matching on the value. A local
* holds a rounded decimal representation, so net_t == `PEAK' is a
* floating-point equality that silently matches nothing and leaves the month
* blank - which is exactly what the first run of this file printed.
gsort -net_t
local PEAK = net_t[1]
local PEAK_M : display %tmMonth_CCYY m[1]
local PEAK_M = trim("`PEAK_M'")
sort m
qui summarize net_t if m < `EP_LO'
local PRE_MEAN = r(mean)
local PRE_CUM  = r(sum)
local PRE_N    = r(N)
* The 2020 dislocation, which did much the same thing for an unrelated reason
* and is the one piece of evidence here that the mechanism is not specific to
* a tariff.
qui summarize net_t if m >= tm(2020m3) & m <= tm(2020m7)
local EP20 = r(sum)
local EP20_N = r(N)
local BACK_PCT = 100 * abs(min(`RV', 0)) / `EP'

di as txt "{hline 62}"
di as txt "months                  : " `NM' "  (" `N_EAST' " net eastward, " ///
    %4.1f 100 * `N_EAST' / `NM' "%)"
di as txt "before the episode      : " %7.1f `PRE_MEAN' " t a month over " `PRE_N' " months,"
di as txt "                          cumulative " %7.0f `PRE_CUM' " t"
di as txt "2020 dislocation        : " %7.1f `EP20' " t over " `EP20_N' " months"
di as txt "episode, `EP_N' months     : " %7.1f `EP' " t net west"
di as txt "reversal, `RV_N' months    : " %7.1f `RV' " t net"
di as txt "  so " %4.0f `BACK_PCT' "% of the westward move came back within five months"
di as txt "largest month           : " %7.1f `PEAK' " t in `PEAK_M'"
di as txt "{hline 62}"

*=========================================================== 4. the figure
gen double pos = net_t if net_t >= 0
gen double neg = net_t if net_t <  0

* A MONTHLY AXIS, so the year ticks are a clean arithmetic sequence: a year is
* exactly 12 units here. That is the opposite of the combined figure, where the
* daily spread forces a %td axis on which a year is 365 units or 366 and the
* year starts have to be enumerated one by one. Worth keeping in mind before
* copying an xlabel between the two.
qui summarize m, meanonly
local Y0 = year(dofm(r(min)))
local Y1 = year(dofm(r(max)))
local XLAB `=tm(`Y0'm1)'(12)`=tm(`Y1'm1)'
local XMIN = r(min) - 2
local XMAX = r(max) + 2

qui summarize net_t
local YHI = ceil(r(max) / 100) * 100
local YLO = floor(r(min) / 100) * 100

twoway                                                                      ///
    (bar pos m, barwidth(0.85) color("`RED'") lwidth(none))                 ///
    (bar neg m, barwidth(0.85) color("`GREY'") lwidth(none))                ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.20))                                 ///
    title("███", size(vsmall) color("`RED'")                                ///
          position(11) justification(left))                                 ///
    subtitle("{bf:Four months brought in more gold than the previous decade sent out}" ///
             "Net gold shipped to the United States each month, both headings, tonnes derived from customs value. Red is net in, grey net out." ///
             "December 2024 to March 2025 ran `=string(`EP', "%4.0f")' tonnes in, against `=string(abs(`PRE_CUM'), "%4.0f")' tonnes net exported over the `PRE_N' months before it;" ///
             "`N_EAST' of the `NM' months in the sample are net out. The 2020 dislocation did much the same thing, `=string(`EP20', "%4.0f")' tonnes over `EP20_N' months", ///
             size(small) color("`INK'") position(11) justification(left))   ///
    ytitle("Tonnes a month, net", size(vsmall) color("`SOFT'"))             ///
    ylabel(`YLO'(100)`YHI', angle(0) labsize(vsmall) tlcolor(none)          ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xscale(range(`XMIN' `XMAX') noextend)                                   ///
    legend(off)                                                             ///
    note("Gold is US imports minus exports of HS 7108 and 7115, all partners. Census reports value and not mass for these headings," ///
         "so tonnage is DERIVED: the month's customs value divided by that month's LBMA PM benchmark. Measured on the US side, it will" ///
         "not agree to the tonne with the Swiss and UK export returns, which carry mass directly" ///
         " "                                                                ///
         "Source: US Census Bureau; LBMA",                                  ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    graphregion(color(white) lcolor(white) margin(l=3 r=4 t=1 b=1))         ///
    plotregion(color(white) lstyle(none) margin(l=1 r=1 t=3 b=1))           ///
    xsize(11) ysize(5.0) name(gNet, replace)

cap mkdir "$FIG"
graph export "$FIG/net_metal.pdf", replace name(gNet)
di as txt "wrote $FIG/net_metal.pdf"

if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
