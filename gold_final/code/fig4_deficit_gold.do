*! fig4_deficit_gold.do
*!
*! The monthly US trade deficit, as published and with nonmonetary gold taken
*! out of both sides.
*!
*! The FT-900 goods-and-services balance carries nonmonetary gold in full. BEA
*! removes gold from the NATIONAL ACCOUNTS - a bar bought as a store of value is
*! a valuable, not consumption or investment, so it is replaced there by
*! domestic production less industrial use - but nobody removes it from the
*! trade release. The same metal is therefore excluded from one official
*! statistic and headlined in another, and the trade deficit is where the
*! phantom flow actually lands.
*!
*! The adjustment is one line. The published balance is X - M; take the gold out
*! of both sides and it becomes balance + net gold imports. The published
*! balance is BEA's own and the gold is subtracted FROM it rather than a deficit
*! being rebuilt from scratch, so the two series differ by the gold and by
*! nothing else.
*!
*! Reads   gold_final/data/raw/us_trade_balance_monthly.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/deficit_gold.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig4_deficit_gold.do

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

tempfile gold

*=================================================================== 1. the gold
* Both headings. 7108 is gold unwrought; 7115 is "other articles of precious
* metal", which is where the bars went in over the winter of 2024-25. BEA
* reclassifies line 7115900530 as nonmonetary gold on a BOP basis, so the pair
* is the right match to the concept the published balance is built on. 7108
* alone misses the episode almost entirely.
import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
destring value_usd, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
collapse (sum) value_usd, by(m flow)
reshape wide value_usd, i(m) j(flow) string
rename value_usdimports gold_imports
rename value_usdexports gold_exports
gen double net_gold = (gold_imports - gold_exports) / 1e9
keep m net_gold
save `gold'

*=========================================================== 2. the FT-900 line
import delimited using "$RAW/us_trade_balance_monthly.csv", varnames(1) clear
destring balance_usdmn, replace force
gen double m = mofd(date(date, "YMD"))
format m %tm
keep m balance_usdmn
gen double reported = balance_usdmn / 1000        // $mn -> $bn, negative = deficit
drop balance_usdmn

merge 1:1 m using `gold', keep(match) nogen
sort m

* Plotted as a positive magnitude, so up is a wider deficit.
gen double deficit     = -reported
gen double deficit_adj = -(reported + net_gold)
gen double gold_share  = 100 * net_gold / deficit

*=========================================================== 3. what it says
* Everything quoted in the figure is computed here and carried in a local. A
* number typed into a title is a second, silent declaration of a fact that the
* data already states, and it goes stale the first time the pull is extended.
summarize m, meanonly
local MLO = r(min)
local MHI = r(max)
local NM  = r(N)

local JAN = tm(2025m1)
local OCT = tm(2025m10)
qui summarize deficit     if m == `JAN', meanonly
local JAN_REP = r(mean)
qui summarize deficit_adj if m == `JAN', meanonly
local JAN_ADJ = r(mean)
qui summarize gold_share  if m == `JAN', meanonly
local JAN_SH  = r(mean)
qui summarize deficit     if m == `OCT', meanonly
local OCT_REP = r(mean)
qui summarize deficit_adj if m == `OCT', meanonly
local OCT_ADJ = r(mean)
qui summarize gold_share  if m == `OCT', meanonly
local OCT_SH  = abs(r(mean))

* The rolling twelve-month overstatement, for the source note. It peaks when a
* full year of data carries the whole surge and none of the reversal.
tsset m
gen double roll12 = .
qui replace roll12 = net_gold + L1.net_gold + L2.net_gold + L3.net_gold  ///
    + L4.net_gold + L5.net_gold + L6.net_gold + L7.net_gold             ///
    + L8.net_gold + L9.net_gold + L10.net_gold + L11.net_gold
qui summarize roll12, meanonly
local ROLLMAX = r(max)
qui summarize m if abs(roll12 - `ROLLMAX') < 1e-9, meanonly
local ROLLMON = r(mean)
local ROLLTXT : display %tmMonth_CCYY `ROLLMON'

qui summarize deficit
local SD_REP = r(sd)
qui summarize deficit_adj
local SD_ADJ = r(sd)

di as txt "months            : " `NM'
di as txt "Jan-2025 reported : " %6.1f `JAN_REP' "  adjusted " %6.1f `JAN_ADJ'
di as txt "Oct-2025 reported : " %6.1f `OCT_REP' "  adjusted " %6.1f `OCT_ADJ'
di as txt "rolling 12m peak  : " %6.1f `ROLLMAX' " in `ROLLTXT'"
di as txt "sd reported/adj   : " %5.1f `SD_REP' " / " %5.1f `SD_ADJ'

*=========================================================== 4. the figure
* Two shaded regions, split on the sign of the gold term, so the eye can tell
* metal arriving from metal leaving without reading the legend.
*
* The split has to be done by BLANKING the series, not by an if-condition.
* rarea restricted with `if` still joins the observations that survive, so it
* draws a wedge straight across every stretch where the condition was false -
* which on this series produced long pale triangles spanning whole years that
* corresponded to nothing. Missing values make rarea break, which is what is
* wanted: the months where the sign flips are left unshaded rather than having
* a colour invented for them. cmissing(n) is what actually enforces it - twoway
* defaults to cmissing(y), which SKIPS missing observations and joins straight
* across them, and that drew pale wedges spanning whole years.
gen double hi_in  = deficit     if net_gold >= 0
gen double lo_in  = deficit_adj if net_gold >= 0
gen double hi_out = deficit     if net_gold <  0
gen double lo_out = deficit_adj if net_gold <  0

* Labels are computed from the span, not typed. The gold series now reaches
* back to 2015, so a hard-coded window would silently crop the figure the next
* time the pull is extended.
local Y0 = year(dofm(`MLO'))
local Y1 = year(dofm(`MHI'))
local XLAB `=tm(`Y0'm1)'(12)`=tm(`Y1'm1)'
local ROLLTXT = trim("`ROLLTXT'")

twoway                                                                      ///
    (rarea hi_in  lo_in  m, color("`RED'%22") lwidth(none) cmissing(n))     ///
    (rarea hi_out lo_out m, color("`GREY'%34") lwidth(none) cmissing(n))    ///
    (line deficit m, lcolor("`RED'") lwidth(0.65))                          ///
    (line deficit_adj m, lcolor("`INK'") lwidth(0.45) lpattern(dash))       ///
    ,                                                                       ///
    title("███", size(vsmall) color("`RED'")                                ///
          position(11) justification(left))                                 ///
    subtitle("{bf:The record deficits, and the collapse that followed, were both largely bullion}" ///
             "US goods and services deficit as published each month, and with nonmonetary gold taken out of both sides." ///
             "Gold is `=string(`JAN_SH', "%3.0f")'% of the January 2025 record and `=string(`OCT_SH', "%3.0f")'% of October 2025, the smallest deficit in six years", ///
             size(small) color("`INK'") position(11) justification(left))   ///
    ytitle("Monthly deficit, {c $|}bn", size(vsmall) color("`SOFT'"))       ///
    ylabel(0(20)140, angle(0) labsize(vsmall) tlcolor(none)                 ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    legend(order(3 "As published" 4 "With nonmonetary gold removed")        ///
           position(11) ring(0) cols(1) region(lstyle(none) color(none))    ///
           size(vsmall) symxsize(6) color("`INK'"))                         ///
    note("The published balance is BEA and Census, FT-900, goods and services, balance-of-payments basis. Gold is US imports minus exports" ///
         "of HS 7108 and 7115, all partners, subtracted from both sides of that same balance, so the two lines differ by the gold and by" ///
         "nothing else. It nets out only slowly: the rolling twelve-month deficit was overstated by {c $|}`=string(`ROLLMAX', "%3.0f")'bn at its worst in `ROLLTXT'" ///
         " "                                                                ///
         "Source: US Census Bureau; Bureau of Economic Analysis",           ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    graphregion(color(white) lcolor(white) margin(l=3 r=4 t=1 b=1))         ///
    plotregion(color(white) lstyle(none) margin(l=1 r=1 t=3 b=1))           ///
    xsize(11) ysize(6.2) name(gDef, replace)

cap mkdir "$FIG"
graph export "$FIG/deficit_gold.pdf", replace name(gDef)
di as txt "wrote $FIG/deficit_gold.pdf"

* Only restore if there was something to restore: in batch mode
* c(graphfontface) can come back empty, and an empty fontface is a syntax
* error rather than a no-op.
if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
