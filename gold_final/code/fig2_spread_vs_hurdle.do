*! fig2_spread_vs_hurdle.do
*!
*! The COMEX-London spread against everything it has to clear, and the metal
*! that then moves. Built from the raw Databento curve, not from an intermediate
*! series: the daily fit, the premium, the carry, the re-timing and the hurdle
*! are all done here.
*!
*! THE MODEL, in one line per step.
*!
*!   1. Each day, project the whole futures curve onto a line in log price
*!      against days to first notice, weighted by open interest:
*!
*!          ln F_i(tau_i) = a + b * tau_i + u_i,   weights OI_i^WPOW
*!
*!      b is the carry, in log points a day. a is the fitted log price at zero
*!      maturity - what the curve says New York gold is worth for immediate
*!      delivery.
*!
*!   2. The premium is that intercept over London spot:  p = a - ln(S).
*!      This is a REDUCED FORM. p is defined by the projection, not by a
*!      structural decomposition of what sits inside it, and no attempt is made
*!      here to split it into location, form and trust.
*!
*!   3. RE-TIMING. The COMEX settlement is struck at 13:30 New York, the London
*!      benchmark at 15:00 London - three and a half hours apart, two and a half
*!      for the three weeks a year when only one country has changed its clocks.
*!      Gold moves in that gap, and the move is a pure measurement error in p.
*!      It is common to every contract on the day, so it lands entirely on the
*!      intercept and not at all on the slope:
*!
*!          eps = ln F(settle instant) - ln F(auction instant)
*!          p   = a - ln(S) - eps
*!
*!   4. At a fixed ninety-day horizon, in dollars:
*!
*!          spread = S * (exp(p + 90b) - 1)
*!          hurdle = S * (exp(90b) - 1) + kappa
*!
*!      kappa is the one-off cost of flying and recasting an ounce, estimated
*!      from the kink in the premium-tonnage relationship in earlier work at
*!      $0.78 westward and -$0.95 eastward. Its interval contains zero; it is an
*!      assumption with a range, not a measurement, and the band drawn in panel
*!      A is exactly that assumption made visible.
*!
*! PANEL B IS US CUSTOMS, NOT SWISS. Census reports value and not mass for these
*! headings, so the tonnage is DERIVED - the month's customs value over the LBMA
*! benchmark. Both directions come from the one reporter, so the net series is a
*! real net rather than one country's exports minus nothing.
*!
*! Reads   gold_final/data/raw/comex_contract_daily.csv
*!         gold_final/data/raw/gc_minute_windows.csv
*!         gold_final/data/raw/lbma_pm.csv
*!         gold_final/data/raw/us_gold_monthly.csv
*! Writes  gold_final/figures/spread_vs_hurdle.pdf
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           gold_final\code\fig2_spread_vs_hurdle.do

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

*=================================================================== the spec
* Contracts entering the daily fit. Inside 15 days a contract is in its delivery
* window and stops behaving like a forward; past 400 days open interest is a
* rounding error; the 1,000-lot floor drops deferred contracts whose settlement
* is marked rather than traded. Two points fit a line exactly and leave no
* residual, so three is the minimum that says anything.
local MIN_TAU  = 15
local MAX_TAU  = 400
local MIN_OI   = 1000
local MIN_N    = 3

* The exponent on open interest in the WLS objective: the fit minimises
* sum_i OI_i^WPOW * u_i^2. 0.5 is the sqrt(OI) weighting this project specifies
* throughout. Note that np.polyfit(..., w=sqrt(OI)) implements 1.0, not 0.5,
* because polyfit squares the weights it is handed - a discrepancy documented
* rather than quietly reconciled.
local WPOW = 0.5

local HORIZON = 90
local KAPPA_W =  0.78
local KAPPA_E = -0.95
local OZ_PER_TONNE = 32150.7

tempfile px eps monthly flows

*================================================================= 1. the spot
import delimited using "$RAW/lbma_pm.csv", varnames(1) clear
destring lbma_pm_usd, replace force
gen long d = date(date, "YMD")
format d %td
keep d lbma_pm_usd
rename lbma_pm_usd spot
duplicates drop d, force
save `px'

*========================================================= 2. the re-timing term
* One bar per instant per day: the print closest to the instant itself. The
* windows were bought a few minutes wide so that a minute with no trade is not
* a missing day.
import delimited using "$RAW/gc_minute_windows.csv", varnames(1) clear
destring close minutes_from, replace force
gen long d = date(substr(date, 1, 10), "YMD")
format d %td
gen double adist = abs(minutes_from)
bysort d instant (adist): keep if _n == 1
keep d instant close
reshape wide close, i(d) j(instant) string
rename closesettle f_settle
rename closeauction f_auction
gen double eps = ln(f_settle) - ln(f_auction)
keep d eps
save `eps'

*=========================================================== 3. the daily curve
import delimited using "$RAW/comex_contract_daily.csv", varnames(1) clear
destring settle open_interest days_to_first_notice, replace force
gen long d = date(date, "YMD")
format d %td

keep if days_to_first_notice >= `MIN_TAU' & days_to_first_notice <= `MAX_TAU'
keep if open_interest >= `MIN_OI'
keep if settle > 0 & !missing(settle)

gen double y = ln(settle)
gen double x = days_to_first_notice
gen double w = open_interest^`WPOW'

* Weighted least squares in closed form, by day. A loop of 2,900 `regress'
* calls would give the same numbers far more slowly, and the closed form makes
* the estimator legible: these are the five weighted sums a simple linear WLS
* needs, and nothing else enters it.
bysort d: egen double Sw  = total(w)
bysort d: egen double Sx  = total(w * x)
bysort d: egen double Sy  = total(w * y)
bysort d: egen double Sxx = total(w * x * x)
bysort d: egen double Sxy = total(w * x * y)
bysort d: egen long   nk  = count(y)

gen double D = Sw * Sxx - Sx * Sx
gen double b = (Sw * Sxy - Sx * Sy) / D
gen double a = (Sy - b * Sx) / Sw

* Residual scale, for the record. Not drawn, but a fit whose residuals blow up
* is a fit that should not be trusted, and this is where you would see it.
gen double resid = y - a - b * x
bysort d: egen double Sr2 = total(w * resid * resid)
gen double s2 = Sr2 / (Sw * (nk - 2) / nk)

bysort d: keep if _n == 1
keep d a b nk s2
keep if nk >= `MIN_N'

merge 1:1 d using `px', keep(match) nogen
merge 1:1 d using `eps', keep(master match) nogen
sort d

*========================================================== 4. premium and carry
gen double premium_raw = a - ln(spot)

* Days with no minute data keep the raw premium and are flagged, rather than
* being dropped or silently carrying a zero correction.
gen byte retimed = !missing(eps)
gen double premium = premium_raw - cond(retimed, eps, 0)

gen double spread_pct = 100 * premium
gen double carry_pct  = 100 * 365 * b

* At a fixed ninety-day horizon, in dollars an ounce. The horizon is fixed
* because the raw dollar spread carries a sawtooth driven purely by the
* delivery calendar: time to delivery cycles from about two months to zero and
* back, and carry scales with it. Regressing on the raw spread would be
* regressing on the calendar.
gen double p = spread_pct / 100
gen double bd = carry_pct / 100 / 365
gen double spread90 = spot * (exp(p + bd * `HORIZON') - 1)
gen double carry90  = spot * (exp(bd * `HORIZON') - 1)
gen double hurdle_w = carry90 + `KAPPA_W'
gen double hurdle_e = carry90 + `KAPPA_E'
gen byte clears_w = spread90 > hurdle_w
gen byte clears_e = spread90 < hurdle_e

qui count
local NDAYS = r(N)
qui count if retimed
local NRETIMED = r(N)
qui summarize clears_w, meanonly
local PCT_W = 100 * r(mean)
local N_W = r(sum)
qui summarize clears_e, meanonly
local PCT_E = 100 * r(mean)
local N_E = r(sum)
qui summarize spread_pct
local SD_RAW = r(sd)
qui summarize premium_raw if retimed
local SD_PRE = 100 * r(sd)

di as txt "days in the fit      : " `NDAYS' "  (" `NRETIMED' " re-timed)"
di as txt "clearing westward    : " `N_W' " (" %4.1f `PCT_W' "%)"
di as txt "clearing eastward    : " `N_E' " (" %4.1f `PCT_E' "%)"
di as txt "premium sd, raw      : " %5.3f `SD_PRE' "%"
di as txt "premium sd, re-timed : " %5.3f `SD_RAW' "%"

preserve
    gen double m = mofd(d)
    format m %tm
    collapse (mean) spread90 carry90 hurdle_w hurdle_e ///
             (sum) days_west = clears_w days_east = clears_e ///
             (count) n_days = spread90, by(m)
    save `monthly'
restore

*=========================================================== 5. the metal
* US customs, both directions, both headings. Tonnage is DERIVED: Census
* reports value and not mass for 7108 and 7115, so the month's customs value is
* divided by the LBMA benchmark. Positive is net into the United States.
preserve
    use `px', clear
    gen double m = mofd(d)
    collapse (mean) price = spot, by(m)
    format m %tm
    tempfile pxm
    save `pxm'

    import delimited using "$RAW/us_gold_monthly.csv", varnames(1) clear
    destring value_usd, replace force
    gen double m = mofd(date(date, "YMD"))
    format m %tm
    collapse (sum) value_usd, by(m flow)
    reshape wide value_usd, i(m) j(flow) string
    merge 1:1 m using `pxm', keep(match) nogen
    gen double net_to_us = (value_usdimports - value_usdexports) / price / `OZ_PER_TONNE'
    keep m net_to_us
    save `flows'
restore

use `monthly', clear
merge 1:1 m using `flows', keep(master match) nogen
sort m

qui count if !missing(net_to_us)
local NM = r(N)
qui count if net_to_us < 0 & !missing(net_to_us)
local N_EAST = r(N)
qui summarize net_to_us if m >= tm(2024m12) & m <= tm(2025m3)
local EP_WEST = r(sum)
qui summarize net_to_us if m >= tm(2025m4) & m <= tm(2025m8)
local EP_BACK = r(sum)

di as txt "months with flow     : " `NM' "  (" `N_EAST' " net eastward)"
di as txt "episode Dec24-Mar25  : " %7.1f `EP_WEST' " t net west"
di as txt "after   Apr25-Aug25  : " %7.1f `EP_BACK' " t net"

*=========================================================== 6. the figure
* Shaded excursions above the westward hurdle and below the eastward one.
* Blanked rather than restricted with `if', and cmissing(n), so the areas break
* where the condition fails instead of being drawn straight across it.
gen double up_hi = spread90 if spread90 > hurdle_w
gen double up_lo = hurdle_w if spread90 > hurdle_w
gen double dn_hi = hurdle_e if spread90 < hurdle_e
gen double dn_lo = spread90 if spread90 < hurdle_e

qui summarize m, meanonly
local Y0 = year(dofm(r(min)))
local Y1 = year(dofm(r(max)))
local XLAB `=tm(`Y0'm1)'(24)`=tm(`Y1'm1)'

qui summarize spread90
local LIM = ceil(max(abs(r(max)), abs(r(min))) / 10) * 10 + 10

* Both panels get the SAME x range explicitly. Left to themselves the two plot
* regions end up different widths - the y labels differ in length - and the
* years stop lining up between the panels, which is the one thing a stacked
* pair has to get right.
qui summarize m, meanonly
local XMIN = r(min) - 2
local XMAX = r(max) + 2

twoway                                                                      ///
    (rarea hurdle_e hurdle_w m, color("`GREY'%35") lwidth(none))            ///
    (rarea up_hi up_lo m, color("`RED'%22") lwidth(none) cmissing(n))       ///
    (rarea dn_hi dn_lo m, color("`GREY'%45") lwidth(none) cmissing(n))      ///
    (line carry90 m, lcolor("`GREY'") lwidth(0.40))                         ///
    (line spread90 m, lcolor("`RED'") lwidth(0.60))                         ///
    ,                                                                       ///
    title("The spread, and what it has to clear", size(medsmall)            ///
          color("`INK'") position(11) justification(left))                  ///
    subtitle("Dollars an ounce at a fixed ninety-day horizon, monthly means", ///
             size(vsmall) color("`SOFT'") position(11) justification(left)) ///
    ytitle("Dollars per ounce", size(vsmall) color("`SOFT'"))               ///
    ylabel(, angle(0) labsize(vsmall) tlcolor(none) labcolor("`SOFT'")      ///
           grid glcolor("`RULE'") glwidth(0.28))                            ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xscale(range(`XMIN' `XMAX'))                                            ///
    legend(order(1 "No-trade band: carry + shipping, both ways"             ///
                 4 "Composite carry to delivery"                            ///
                 5 "Estimated spread at 90 days")                           ///
           position(11) ring(0) cols(1) region(lstyle(none) color(none))    ///
           size(vsmall) symxsize(7) color("`SOFT'"))                        ///
    graphregion(color(white) lcolor(white)) plotregion(lstyle(none))        ///
    name(gTop, replace) nodraw

gen double pos = net_to_us if net_to_us >= 0
gen double neg = net_to_us if net_to_us <  0

twoway                                                                      ///
    (bar pos m, barwidth(0.85) color("`RED'") lwidth(none))                 ///
    (bar neg m, barwidth(0.85) color("`GREY'") lwidth(none))                ///
    ,                                                                       ///
    yline(0, lcolor("`SOFT'") lwidth(0.20))                                 ///
    title("Net metal shipped", size(medsmall) color("`INK'")                ///
          position(11) justification(left))                                 ///
    subtitle("United States, both directions netted, tonnes derived from customs value." ///
             "Red is net west, grey net east; `N_EAST' of `NM' months are net east", ///
             size(vsmall) color("`SOFT'") position(11) justification(left)) ///
    ytitle("Tonnes a month", size(vsmall) color("`SOFT'"))                  ///
    ylabel(, angle(0) labsize(vsmall) tlcolor(none) labcolor("`SOFT'")      ///
           grid glcolor("`RULE'") glwidth(0.28))                            ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tmCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xscale(range(`XMIN' `XMAX'))                                            ///
    legend(off)                                                             ///
    graphregion(color(white) lcolor(white)) plotregion(lstyle(none))        ///
    name(gBot, replace) nodraw

graph combine gTop gBot, cols(1) imargin(small) iscale(*0.95)               ///
    graphregion(color(white) lcolor(white))                                 ///
    title("███", size(vsmall) color("`RED'")                                ///
          position(11) justification(left))                                 ///
    subtitle("{bf:Gold moves only when the spread clears the cost}"         ///
             "The estimated COMEX-London spread against carry plus shipping, and the net metal that crossed." ///
             "Above the band the westward trade pays; below it the eastward one does", ///
             size(medsmall) color("`INK'") position(11) justification(left)) ///
    note("The spread is a daily open-interest-weighted projection of the COMEX curve onto log price against days to first notice, re-timed" ///
         "to the London auction so the three-and-a-half-hour gap between the two fixings is removed from the intercept. kappa, the shipping" ///
         "term in the hurdle, is an assumption with an interval containing zero, not a measurement. Panel B is US customs, both headings," ///
         "with tonnage derived from customs value" ///
         " "                                                                ///
         "Source: Databento GLBX.MDP3 re-timed to the LBMA auction; LBMA; US Census Bureau", ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    name(gPanel, replace) xsize(11) ysize(8.2)

cap mkdir "$FIG"
graph export "$FIG/spread_vs_hurdle.pdf", replace name(gPanel)
di as txt "wrote $FIG/spread_vs_hurdle.pdf"

if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
