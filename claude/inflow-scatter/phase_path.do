*! Three-phase path on the trade-balance plane, built in Stata.
*!
*! Stata counterpart of make_phase_path_figure.py, rebuilt from the raw Census
*! pull rather than from the Python intermediate, so the two are independent
*! implementations of the same figure and disagreeing is informative.
*!
*! Reads   data/processed/us_hs4_universe_monthly.csv
*! Writes  claude/inflow-scatter/figures/phase_path_stata.pdf
*!         claude/inflow-scatter/figures/phase_path_stata.png
*!
*! Run:  "C:\Program Files\Stata18\StataMP-64.exe" /e do claude/inflow-scatter/phase_path.do

version 18
clear all
set more off

* Launched from a shell, Stata does not inherit the caller's working directory,
* so anchor it explicitly rather than relying on relative paths.
cd "C:/Users/smoor/GitHub/GOLD"

local OUT "claude/inflow-scatter/figures"
cap mkdir "`OUT'"

* Palette lifted from src/make_paper_figures.py so the Stata and matplotlib
* versions are the same figure rather than two different-looking ones.
local ACCENT "181 72 42"      // #b5482a
local MUTED  "122 139 153"    // #7a8b99
local INK    "26 26 26"       // #1a1a1a

*------------------------------------------------------------------ load
import delimited using "data/processed/us_hs4_universe_monthly.csv", ///
    varnames(1) stringcols(3) clear
destring value_usd, replace force

gen str7 ym = substr(date, 1, 7)

* Phases split where the series turns. Lengths differ (12/5/8 months), so
* everything below is a monthly-average rate, never a cumulative total.
gen str8 phase = ""
replace phase = "baseline" if ym >= "2023-11" & ym <= "2024-10"
replace phase = "surge"    if ym >= "2024-11" & ym <= "2025-03"
replace phase = "reversal" if ym >= "2025-04" & ym <= "2025-11"
drop if phase == ""

* Gold is one heading: Switzerland reports the bullion as 7108, US Census books
* the same shipments as 7115. The split is bookkeeping, not economics.
replace hs4 = "7108+7115" if inlist(hs4, "7108", "7115")

collapse (sum) value_usd, by(hs4 phase flow)

gen byte months = cond(phase == "baseline", 12, cond(phase == "surge", 5, 8))
gen double rate = value_usd / months / 1e9        // $bn per month
drop value_usd months

*--------------------------------------------------------------- reshape
* m = imports, x = exports; b/s/r = baseline/surge/reversal.
gen str1 f = cond(flow == "imports", "m", "x")
gen str1 p = cond(phase == "baseline", "b", cond(phase == "surge", "s", "r"))
gen str2 key = f + p
drop flow phase f p
reshape wide rate, i(hs4) j(key) string
rename (ratemb ratems ratemr ratexb ratexs ratexr) (mb ms mr xb xs xr)

* A heading needs positive trade on both sides in all three phases, since both
* axes are logged.
foreach v in mb ms mr xb xs xr {
    drop if missing(`v') | `v' <= 0
}

*------------------------------------------------- top 100 + round-trip stats
gen double trade = mb + xb + ms + xs + mr + xr
gsort -trade
gen long tradernk = _n
keep if tradernk <= 100 | hs4 == "7108+7115"

* Both legs in log space. Amplitude is the shorter leg: a heading only scores
* by travelling far out AND far back, which the scale-free path/net ratio does
* not require - that ratio rewards a wobble whose net displacement is near zero.
gen double outleg  = sqrt((log10(ms/mb))^2 + (log10(xs/xb))^2)
gen double backleg = sqrt((log10(mr/ms))^2 + (log10(xr/xs))^2)
gen double net     = sqrt((log10(mr/mb))^2 + (log10(xr/xb))^2)
gen double amp     = min(outleg, backleg)
gen double retrace = (outleg + backleg) / net

gsort -amp
gen long amprnk = _n

gen byte gold = hs4 == "7108+7115"

* list has no format() option; the display format belongs on the variables.
format amp retrace mb ms mr %6.2f
list amprnk hs4 amp retrace mb ms mr if amprnk <= 5, noobs abbrev(10) sep(0)
sum amp if gold, meanonly
di as txt "gold amplitude = " as res %5.2f r(mean)
count
local n = r(N)

*------------------------------------------------------------------- graph
* Stata draws in the order given, so the faint headings go down first and the
* gold path sits on top of them.
twoway ///
  (function y = x, range(0.012 40) lcolor("`INK'%45") lpattern(dash) ///
      lwidth(thin)) ///
  (pcspike mb xb ms xs if !gold, lcolor("`MUTED'%35") lwidth(vthin)) ///
  (pcspike ms xs mr xr if !gold, lcolor("`MUTED'%35") lwidth(vthin)) ///
  (scatter mb xb if !gold, msymbol(Oh) msize(tiny)  mcolor("`MUTED'%50")) ///
  (scatter mr xr if !gold, msymbol(O)  msize(tiny)  mcolor("`MUTED'%50")) ///
  (pcarrow mb xb ms xs if gold, lcolor("`ACCENT'") lwidth(medthick) ///
      mcolor("`ACCENT'") msize(medlarge)) ///
  (pcarrow ms xs mr xr if gold, lcolor("`ACCENT'") lwidth(medthick) ///
      mcolor("`ACCENT'") msize(medlarge)) ///
  (scatter mb xb if gold, msymbol(Oh) msize(medium) mcolor("`ACCENT'") ///
      mlwidth(medthick)) ///
  (scatter ms xs if gold, msymbol(O) msize(medium) mcolor("`ACCENT'%65")) ///
  (scatter mr xr if gold, msymbol(O) msize(medlarge) mcolor("`ACCENT'")) ///
  , ///
  xscale(log range(0.012 40)) yscale(log range(0.012 40)) ///
  xlabel(0.1 "0.1" 1 "1" 10 "10", labsize(small) tlcolor("`INK'%40") ///
      grid glcolor("`INK'%10") glwidth(vthin)) ///
  ylabel(0.1 "0.1" 1 "1" 10 "10", labsize(small) angle(0) ///
      tlcolor("`INK'%40") grid glcolor("`INK'%10") glwidth(vthin)) ///
  xtitle("US exports, {c $|}bn per month", size(small) margin(t=3)) ///
  ytitle("US imports, {c $|}bn per month", size(small) margin(r=3)) ///
  title("Gold went in, then came back out", size(medium) color("`INK'") ///
      position(11) justification(left) margin(b=1)) ///
  subtitle("`n' most-traded HS4 headings, three phases each." ///
      " Above the diagonal a heading is import-dominated.", ///
      size(vsmall) color(gs7) position(11) justification(left) margin(b=3)) ///
  text(19 0.045 "GOLD" "HS 7108 + 7115", place(e) size(small) ///
      color("`ACCENT'") justification(left)) ///
  text(19.4 3.40 "surge" "Nov 24-Mar 25", place(ne) size(vsmall) ///
      color("`ACCENT'") justification(left)) ///
  text(1.95 2.46 "baseline" "Nov 23-Oct 24", place(se) size(vsmall) ///
      color("`ACCENT'") justification(left)) ///
  text(3.10 10.87 "reversal" "Apr-Nov 25", place(e) size(vsmall) ///
      color("`ACCENT'") justification(left)) ///
  text(28 0.016 "import-dominated", place(e) size(vsmall) color("`INK'%55")) ///
  text(0.016 30 "export-dominated", place(w) size(vsmall) color("`INK'%55")) ///
  legend(order(4 "other headings" 8 "baseline" 9 "surge" 10 "reversal") ///
      cols(4) size(vsmall) region(lcolor(none)) position(6) ring(1) ///
      symxsize(4) rowgap(0.5)) ///
  graphregion(color(white) margin(medium)) plotregion(color(white) ///
      lcolor("`INK'%35") lwidth(thin)) ///
  scheme(s1mono) ysize(6.4) xsize(7.2)

graph export "`OUT'/phase_path_stata.pdf", replace
graph export "`OUT'/phase_path_stata.png", replace width(1600)

di as txt "wrote `OUT'/phase_path_stata.pdf and .png"
