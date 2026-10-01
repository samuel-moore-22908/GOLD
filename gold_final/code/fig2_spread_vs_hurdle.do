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
*!      kappa is the one-off cost of flying and recasting an ounce: $0.75,
*!      the same in both directions, built from published and reported rates
*!      rather than estimated from the flows. The build is in the spec block
*!      below. The band drawn in panel A is exactly that figure made visible.
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

* KAPPA: the one-off cost of physically relocating an ounce, in dollars. ONE
* number, applied symmetrically, built from published and reported rates rather
* than estimated from the flows.
*
*   air freight, secure carrier, London <-> New York      0.20
*   recasting 400 oz Good Delivery <-> kilobar / 100 oz   0.20
*   COMEX depository delivery out, $35.00 per 100 oz      0.35
*                                                        -----
*                                                         0.75
*
* Only the third line is a published tariff: CME's approved-depository fee
* schedule sets a maximum of $35.00 per contract for delivery out and $0.00 for
* delivery in, and a gold contract is 100 troy ounces. The first two are the
* figures the trade press reported for institutional London-New York movement
* during the 2025 episode. They are not quotes we obtained, and a single real
* quote from a secure carrier would still be the cheapest improvement available
* to this project.
*
* NOT INCLUDED, deliberately: the ~$0.10 an ounce of transit financing those
* same reports cite. Financing is already in the carry term the hurdle is built
* on, and adding it here would count it twice.
*
* NOT USED: retail parcel rates of $300-500 a kilogram, which circulate widely
* and work out at $9-16 an ounce. They price a one-kilo consignment to a private
* buyer, not a tonne moving between bullion banks on a scheduled commercial
* flight, and are two orders of magnitude from the right answer.
*
* SYMMETRIC, where the previous version used +0.78 westward and -0.95 eastward.
* The physical operation is the same in both directions - fly it, recast it, book
* it in or out - and the asymmetry came from a flow-based estimate whose 90%
* intervals, [-0.46, +2.43] and [-1.78, +0.80], both contained zero and whose
* point estimate changed sign across specifications. A symmetric constant from
* published rates claims less and is easier to check.
local KAPPA = 0.75
local OZ_PER_TONNE = 32150.7

tempfile px eps monthly flows daily

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
gen double hurdle_w = carry90 + `KAPPA'
gen double hurdle_e = carry90 - `KAPPA'
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

* The daily series is kept as well as the monthly means. Panel A draws it
* faintly behind them: the monthly line is what the eye should follow, but a
* reader is entitled to see how much is being averaged away, and in this series
* that is a great deal - single days reach several times the monthly mean.
preserve
    keep d spread90
    rename spread90 sp_d
    save `daily'
restore

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
* ONE AXIS, IN DAYS. The daily series and the monthly means have to share an x
* variable, and they cannot share a %tm one: a Stata monthly date is months
* since 1960 and a daily date is days since 1960, so plotting both against
* whichever variable happened to be in memory would crush eleven years of daily
* data into the first fortnight of 1960. So everything moves onto %td, and each
* monthly observation is placed at the MIDDLE of its month rather than the 1st,
* which centres the monthly line over the daily cloud it summarises instead of
* hanging it off the left edge of each month.
gen double t = dofm(m) + 14
format t %td
rename (spread90 carry90 hurdle_w hurdle_e) (sp_m carry_m hw_m he_m)
keep t sp_m carry_m hw_m he_m net_to_us

append using `daily'
replace t = d if missing(t)
format t %td
drop d
sort t

* Monthly variables are missing on the ~2,860 daily rows and the daily variable
* is missing on the 139 monthly ones. That is exactly what is wanted here, and
* it is the one place in this project where twoway's default cmissing(y) - join
* straight across missing values - is the behaviour to keep rather than to
* override: it is what connects each monthly point to the next across the daily
* rows sitting between them.

* Shaded excursions above the westward hurdle and below the eastward one.
* Blanked rather than restricted with `if', and cmissing(n), so the areas break
* where the condition fails instead of being drawn straight across it.
gen double up_hi = sp_m if sp_m > hw_m
gen double up_lo = hw_m if sp_m > hw_m
gen double dn_hi = he_m if sp_m < he_m
gen double dn_lo = sp_m if sp_m < he_m

* X LABELS, AND WHY THEY ARE BUILT WITH A LOOP.
* On a monthly axis a year is exactly 12 units, so xlabel(a(12)b) is a clean
* arithmetic sequence. On a DAILY axis a year is 365 units or 366, so no fixed
* step lands on 1 January twice running - a step of 365 drifts a day earlier
* every leap year and is four days out by the end of this sample. The year
* starts therefore have to be enumerated rather than stepped.
qui summarize t, meanonly
local Y0 = year(dofd(r(min)))
local Y1 = year(dofd(r(max)))
local XLAB ""
forvalues yr = `Y0'/`Y1' {
    local XLAB `XLAB' `=mdy(1, 1, `yr')'
}
di as txt "x-axis: %td, year starts " `Y0' " to " `Y1'
di as txt "xlabel(`XLAB')"


* The frame is set from the MONTHLY series, not the daily one. The daily series
* has a fat tail - its 99th percentile is around $77 and its minimum is -$219,
* against a monthly series that never exceeds about $52 - so letting it set the
* scale would squash eleven years of monthly means into the middle fifth of the
* panel.
qui summarize sp_m
local LIM   = ceil(max(abs(r(max)), abs(r(min))) / 10) * 10 + 10
local LIMLO = min(-10, r(min) - 8)
qui summarize carry_m
local LIM = max(`LIM', ceil(r(max) / 10) * 10 + 10)

* yscale(range()) only ever WIDENS an axis in Stata; it cannot truncate one. So
* the daily series has to be blanked outside the frame rather than merely
* bounded, and drawn with cmissing(n) so the line BREAKS at each excursion
* instead of being joined straight across it - a chord over a spike would draw
* a line through prices that never happened. The count is reported in the
* corner so the clipping is declared rather than hidden.
gen double sp_d_in = sp_d if inrange(sp_d, `LIMLO', `LIM')
qui count if !missing(sp_d) & !inrange(sp_d, `LIMLO', `LIM')
local N_OUT = r(N)
qui count if !missing(sp_d)
local N_DAILY = r(N)
di as txt "daily prints drawn   : " `N_DAILY' - `N_OUT' " of " `N_DAILY' ///
    "  (" `N_OUT' " outside the frame)"
di as txt "frame                : " %5.0f `LIMLO' " to " %5.0f `LIM'

* Both panels get the SAME x range explicitly. Left to themselves the two plot
* regions end up different widths - the y labels differ in length - and the
* years stop lining up between the panels, which is the one thing a stacked
* pair has to get right.
* NOEXTEND is the operative word here. range() sets a MINIMUM extent and Stata
* then adds its own padding on top, so without noextend the drawn axis is wider
* than the range asked for - and anything positioned at XMAX, such as the
* outlier note below, floats short of the right edge instead of sitting on it.
* With noextend the axis is exactly XMIN to XMAX and the anchor means what it
* says.
*
* The pad is a fraction of the span rather than a fixed number of days, so it
* stays proportionate if the sample is ever extended or shortened. A fixed 20
* days is right for eleven years and wrong for one.
qui summarize t, meanonly
local SPAN = r(max) - r(min)
local XMIN = r(min) - round(`SPAN' * 0.01)
local XMAX = r(max) + round(`SPAN' * 0.01)
di as txt "x range              : " %tdCCYY-NN-DD `XMIN' " to " ///
    %tdCCYY-NN-DD `XMAX' "  (span " `SPAN' " days, pad " ///
    round(`SPAN' * 0.01) " either side)"

twoway                                                                      ///
    (line sp_d_in t, lcolor("`GREY'%45") lwidth(0.09) cmissing(n))          ///
    (rarea he_m hw_m t, color("`GREY'%35") lwidth(none))                    ///
    (rarea up_hi up_lo t, color("`RED'%22") lwidth(none) cmissing(n))       ///
    (rarea dn_hi dn_lo t, color("`GREY'%45") lwidth(none) cmissing(n))      ///
    (line carry_m t, lcolor("`GREY'") lwidth(0.40))                         ///
    (line sp_m t, lcolor("`RED'") lwidth(0.60))                             ///
    ,                                                                       ///
    title("The spread, and what it has to clear", size(medsmall)            ///
          color("`INK'") position(11) justification(left))                  ///
    subtitle("Dollars an ounce at a fixed ninety-day horizon; daily in the background, monthly means drawn", ///
             size(vsmall) color("`SOFT'") position(11) justification(left)) ///
    ytitle("Dollars per ounce", size(vsmall) color("`SOFT'"))               ///
    ylabel(, angle(0) labsize(vsmall) tlcolor(none) labcolor("`SOFT'")      ///
           grid glcolor("`RULE'") glwidth(0.28))                            ///
    xtitle("")                                                              ///
    xlabel(`XLAB', format(%tdCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor("`RULE'") glwidth(0.28))         ///
    xscale(range(`XMIN' `XMAX') noextend)                                            ///
    text(`LIMLO' `XMAX' "`N_OUT' of `N_DAILY' daily prints fall outside the frame", ///
         size(vsmall) color("`SOFT'") placement(nw) justification(right))   ///
    legend(order(2 "No-trade band: carry + shipping, both ways"             ///
                 5 "Composite carry to delivery"                            ///
                 6 "Estimated spread at 90 days"                            ///
                 1 "Daily")                                                 ///
           position(11) ring(0) cols(1) region(lstyle(none) color(none))    ///
           size(vsmall) symxsize(7) color("`SOFT'"))                        ///
    graphregion(color(white) lcolor(white)) plotregion(lstyle(none))        ///
    name(gTop, replace) nodraw

gen double pos = net_to_us if net_to_us >= 0
gen double neg = net_to_us if net_to_us <  0

* barwidth is in axis units, and the axis is now DAYS rather than months, so a
* month-wide bar is about 26 rather than 0.85.
twoway                                                                      ///
    (bar pos t, barwidth(26) color("`RED'") lwidth(none))                   ///
    (bar neg t, barwidth(26) color("`GREY'") lwidth(none))                  ///
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
    xlabel(`XLAB', format(%tdCCYY) labsize(vsmall) tlcolor(none)            ///
           labcolor("`SOFT'") grid glcolor(none))                           ///
    xscale(range(`XMIN' `XMAX') noextend)                                            ///
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
         "to the London auction so the three-and-a-half-hour gap between the two fixings is removed from the intercept. The shipping term in" ///
         "the hurdle is {c $|}0.75 an ounce in both directions: {c $|}0.35 of COMEX depository delivery-out charge, which is a published tariff, plus" ///
         "{c $|}0.20 of air freight and {c $|}0.20 of recasting, which are reported institutional rates rather than quotes we obtained. Panel B is US" ///
         "customs, both headings, with tonnage derived from customs value" ///
         " "                                                                ///
         "Source: Databento GLBX.MDP3 re-timed to the LBMA auction; LBMA; US Census Bureau", ///
         size(tiny) color("`SOFT'") position(7) justification(left))        ///
    name(gPanel, replace) xsize(11) ysize(8.2)

cap mkdir "$FIG"
graph export "$FIG/spread_vs_hurdle.pdf", replace name(gPanel)
di as txt "wrote $FIG/spread_vs_hurdle.pdf"

if "$RESTORE_FONT" != "" graph set window fontface "$RESTORE_FONT"
graph drop _all
