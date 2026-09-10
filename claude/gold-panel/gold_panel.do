*! 1x2 panel: the round trip by commodity (left) and by partner (right).
*!
*! Both panels are the same figure drawn over a different unit of observation,
*! so every formatting choice is defined once in a local and reused. The shared
*! legend comes from grc1leg2 (ssc install grc1leg2). It carries only the three
*! phase markers, which mean the same thing in both panels. The accent colour
*! marks a different series in each - gold on the left, CHE on the right - so it
*! is named in each panel's subtitle instead of the legend.
*!
*! Presentation follows The Economist's chart conventions as closely as Stata
*! allows: Econ Sans stood in for by Arial Narrow, the red tab above a bold
*! headline and a plain deck, no plot border, solid pale gridlines, the source
*! line bottom-left. The red tab is three literal U+2588 FULL BLOCK glyphs set
*! as the title, which is the only way to get a filled rectangle into the header
*! of a combined graph - Stata's text elements cannot leave the plot region, and
*! graph combine takes no shape options. They must be the characters themselves:
*! Stata's {c ...} escape covers the ASCII range only and prints "{c 0x2588}"
*! verbatim. So the file must stay UTF-8, and without a BOM.
*!
*! Sized at 13 x 7.4in against the old 9 x 4.2. The point is not resolution -
*! Stata text sizes are relative, so a bigger canvas alone changes nothing. It
*! is the aspect ratio and iscale(): squarer panels give the log-log cloud room
*! to spread, and iscale(*0.92) shrinks type against the plot region so the
*! partner labels stop colliding.
*!
*! Reads   data/processed/us_hs4_universe_monthly.csv
*!         claude/gold-panel/partner_monthly.csv   (see export_partner_panel.py)
*! Writes  claude/gold-panel/figures/gold_panel.pdf and .png
*!
*! THE PNG IS NOT MADE BY STATA. graph export ... .png on this figure kills
*! Stata 18/MP on Windows outright - a process death, not an error, so nothing
*! reaches the log and the session is gone. Confirmed by breadcrumb: the run dies
*! between "starting PNG export" and "PNG written", while the PDF export of the
*! same graph immediately before it succeeds every time. Ruled out first: the
*! U+2588 tab glyph (present in Arial Narrow, Arial and Times New Roman), the
*! font substitution that would imply, and grc1leg2. It is the Windows
*! rasteriser.
*!
*! So Stata writes the PDF and pdf_to_png.py renders the PNG from it with MuPDF,
*! at the same pixel dimensions. That is also the better artefact: rasterising
*! from vectors gives cleaner text and hairlines than Stata's display list at the
*! same pixel count, and the width can be changed later without re-running
*! Stata. PNG_IN_STATA 1 restores the old behaviour if you want to retest it.
*!
*! STABILITY. This was written and tested only in batch, through run_do.py,
*! which starts a fresh Stata per run and exits. Run interactively it had three
*! ways of making a GUI session unstable, all now fixed or switchable:
*!
*!   - it set the graph window font GLOBALLY and never put it back, so every
*!     graph drawn afterwards in any project inherited Arial Narrow;
*!   - it left gLeft, gRight and gPanel in memory, which accumulate across runs;
*!   - it hard-required grc1leg2, a third-party command that rebuilds .gph files
*!     and is the least predictable thing in the file.
*!
*! Three switches below let a crash be bisected without editing the body:
*! USE_GRC1LEG2 (default 0, plain graph combine instead), TAB_GLYPH (set empty
*! to drop the U+2588 block, which is the one exotic glyph being rendered) and
*! MAKE_PDF (set 0 to test PNG alone; PDF embeds the font and is a separate
*! code path). If it still crashes, run it through run_do.py, which never opens
*! a Graph window.
*!
*! Run:  .venv\Scripts\python.exe claude\stata-console\code\run_do.py ///
*!           claude\gold-panel\gold_panel.do --log claude\gold-panel\gold_panel.log

version 18
clear all
set more off

* Leftover graphs are the usual reason a GUI session degrades over repeated
* runs of the same do-file. clear all drops them, but say it explicitly so the
* intent survives anyone removing the clear.
graph drop _all

* Bisection switches - see STABILITY above.
global USE_GRC1LEG2 0        // 1 restores the centred shared legend
global TAB_GLYPH    "███"    // "" drops the red masthead tab
global MAKE_PDF     1        // 0 skips the PDF (the PNG then needs PNG_IN_STATA 1)
global PNG_WIDTH    2800     // pixel width of the PNG
global PNG_IN_STATA 0        // 1 uses Stata's own PNG export - SEE BELOW

* Stata does not inherit the caller's working directory.
cd "C:/Users/smoor/GitHub/GOLD"

* Directories in globals, never locals: a local dies with the do-file or with
* any quietly{} block it is read inside, and an empty path fails somewhere far
* from the line that caused it.
global PROJ "claude/gold-panel"
global OUT  "$PROJ/figures"
cap mkdir "$PROJ"
cap mkdir "$OUT"

* A crash in the GUI leaves nothing behind, which is why this has been hard to
* pin down. Open our own log so the next one names the last step that finished.
* text format, not SMCL, so it is readable without Stata.
cap log close _all
log using "$PROJ/gold_panel_run.log", replace text name(runlog)
* c(edition_real), not c(flavor): the latter is a legacy macro that reports "IC"
* on this machine even though the install is MP, which would send anyone reading
* a crash log after the wrong thing.
di as txt "START  " c(current_date) " " c(current_time)
di as txt "       Stata " c(stata_version) " " c(edition_real) " " c(bit) "-bit, " ///
    c(processors) " cores, memory " c(memory) ", max_memory " c(max_memory)

* grc1leg2 is optional now. It gives a single legend centred over both panels;
* without it the key sits above the left panel instead, which is where it was
* being drawn anyway, and no third-party code runs.
if $USE_GRC1LEG2 {
    cap which grc1leg2
    if _rc {
        di as err "grc1leg2 not installed:  ssc install grc1leg2"
        di as err "or set global USE_GRC1LEG2 0 to use plain graph combine"
        exit 111
    }
}

*=================================================================== presentation
* Econ Sans is proprietary. Arial Narrow is the closest face on this machine -
* humanist, condensed, same job - and the condensing is worth something on its
* own here, since it is point labels running into each other that we are trying
* to stop.
* This is a GLOBAL, PERSISTENT Stata setting, not a per-graph option - Stata
* offers no other way to choose a graph font. It is put back at the bottom of
* the file. Stata exposes no c() macro holding the current value, so the restore
* target is the documented factory default rather than whatever was there
* before; if you have deliberately set your own, change RESTORE_FONT.
* If the do-file dies before the end, put it back by hand with:
*     graph set window fontface "Times New Roman"
global RESTORE_FONT "Times New Roman"
graph set window fontface "Arial Narrow"

* The Economist's published palette, not an approximation of it.
local RED   "227 18 11"       // #E3120B  the masthead red, used for the tab
local INK   "18 18 18"        // near-black for type
local GREY  "117 141 153"     // #758D99  the neutral series colour
local RULE  "224 228 231"     // gridlines
local SOFT  "112 112 112"     // deck and source type

* Phases. Lengths differ (12/5/8 months), so every position below is a
* monthly-average RATE. Cumulating instead would make the long phases look
* large purely for being long.
local P1LO "2023-11"
local P1HI "2024-10"
local P2LO "2024-11"
local P2HI "2025-03"
local P3LO "2025-04"
local P3HI "2025-11"

* A series needs at least this much trade in BOTH directions in EVERY phase to
* have a position on a log-log plane. Matching the Python figures, which use
* the same floor: without it ZAF enters the right panel on an export leg of a
* few hundred thousand dollars, displaces SGP from the top five, and drags the
* axis floor down two decades so that most of both panels is empty.
local FLOOR = 0.001

tempfile comm part

*============================================================ left: commodities
import delimited using "data/processed/us_hs4_universe_monthly.csv", ///
    varnames(1) stringcols(3) clear
destring value_usd, replace force
gen str7 ym = substr(date, 1, 7)

gen str8 phase = ""
replace phase = "baseline" if ym >= "`P1LO'" & ym <= "`P1HI'"
replace phase = "surge"    if ym >= "`P2LO'" & ym <= "`P2HI'"
replace phase = "reversal" if ym >= "`P3LO'" & ym <= "`P3HI'"
drop if phase == ""

* Switzerland reports the bullion as 7108; US Census books the same shipments
* as 7115. The split is bookkeeping, so gold is one heading.
drop unit          // the pull's quantity-unit column; frees the name
gen str12 series = hs4
replace series = "GOLD" if inlist(hs4, "7108", "7115")

* Phase length is COUNTED FROM THE DATA, never restated as a literal. The
* window macros above are the only place a phase length is declared. A hard
* 12/5/8 here is a second, silent declaration of the same fact: move a window -
* which is exactly what happens when this is pointed at a longer pull - and
* every series in that phase is divided by the wrong number. Because the same
* wrong number hits imports and exports alike, every point in the phase is
* multiplied by one constant, so on a log-log plane the whole cloud TRANSLATES
* diagonally and reads as growth in every commodity at once. Running the
* reversal to 2026-06 while this said 8 shifted all 100 headings by exactly
* 15/8 = 1.875x and put 95% of them up and to the right.
tempfile pmonths
preserve
    keep phase ym
    duplicates drop
    gen byte one = 1
    collapse (sum) nmonths = one, by(phase)
    save `pmonths'
restore
collapse (sum) value_usd, by(series phase flow)
merge m:1 phase using `pmonths', nogen
gen double rate = value_usd / nmonths / 1e9
drop value_usd nmonths

gen str1 f = cond(flow == "imports", "m", "x")
gen str1 p = cond(phase == "baseline", "b", cond(phase == "surge", "s", "r"))
gen str2 key = f + p
drop flow phase f p
reshape wide rate, i(series) j(key) string
rename (ratemb ratems ratemr ratexb ratexs ratexr) (mb ms mr xb xs xr)

* Both axes are logged, so a series needs positive trade both ways in all
* three phases.
foreach v in mb ms mr xb xs xr {
    drop if missing(`v') | `v' < `FLOOR'
}

gen double trade = mb + xb + ms + xs + mr + xr
gsort -trade
gen long rk = _n
keep if rk <= 100 | series == "GOLD"
gen byte hl = series == "GOLD"
gen str8 lbl = cond(hl, "GOLD", "")
gen byte mlpos = 3
keep series hl lbl mlpos mb ms mr xb xs xr
save `comm', replace
di as txt "commodities: " as res _N as txt " series"

*=============================================================== right: partners
import delimited using "$PROJ/partner_monthly.csv", varnames(1) clear
destring value_usd, replace force

gen str8 phase = ""
replace phase = "baseline" if ym >= "`P1LO'" & ym <= "`P1HI'"
replace phase = "surge"    if ym >= "`P2LO'" & ym <= "`P2HI'"
replace phase = "reversal" if ym >= "`P3LO'" & ym <= "`P3HI'"
drop if phase == ""

* Phase length is COUNTED FROM THE DATA, never restated as a literal. The
* window macros above are the only place a phase length is declared. A hard
* 12/5/8 here is a second, silent declaration of the same fact: move a window -
* which is exactly what happens when this is pointed at a longer pull - and
* every series in that phase is divided by the wrong number. Because the same
* wrong number hits imports and exports alike, every point in the phase is
* multiplied by one constant, so on a log-log plane the whole cloud TRANSLATES
* diagonally and reads as growth in every commodity at once. Running the
* reversal to 2026-06 while this said 8 shifted all 100 headings by exactly
* 15/8 = 1.875x and put 95% of them up and to the right.
tempfile pmonths
preserve
    keep phase ym
    duplicates drop
    gen byte one = 1
    collapse (sum) nmonths = one, by(phase)
    save `pmonths'
restore
collapse (sum) value_usd, by(iso3 phase flow)
merge m:1 phase using `pmonths', nogen
gen double rate = value_usd / nmonths / 1e9
drop value_usd nmonths

gen str1 f = cond(flow == "imports", "m", "x")
gen str1 p = cond(phase == "baseline", "b", cond(phase == "surge", "s", "r"))
gen str2 key = f + p
drop flow phase f p
reshape wide rate, i(iso3) j(key) string
rename (ratemb ratems ratemr ratexb ratexs ratexr) (mb ms mr xb xs xr)

* Same requirement, and here it is substantive: a partner that sells gold to
* the US and buys none back has no export coordinate at all. ZAF and HKG are
* both large enough to belong in this top five and are excluded by it.
foreach v in mb ms mr xb xs xr {
    drop if missing(`v') | `v' < `FLOOR'
}

gen double trade = mb + xb + ms + xs + mr + xr
gsort -trade
gen long rk = _n
keep if rk <= 5
gen byte hl = iso3 == "CHE"
gen str8 lbl = iso3
* AUS and CAN end up adjacent, and CAN's default label lands on top of the
* Swiss baseline marker, so both are moved off the 3 o'clock default.
gen byte mlpos = 3
replace mlpos = 9  if iso3 == "AUS"
replace mlpos = 12 if iso3 == "CAN"
keep iso3 hl lbl mlpos mb ms mr xb xs xr
save `part', replace
di as txt "partners: " as res _N as txt " series"

*========================================================= axis range per panel
* Each panel gets its own range. A single shared range was tried and rejected:
* the two panels count different things - a commodity's trade with the whole
* world against one partner's gold trade - so a common absolute scale invites
* a comparison that is not well defined, and it costs roughly half the
* plotting area to emptiness. Formatting is identical; only the limits differ.
local i = 0
foreach f in `comm' `part' {
    local ++i
    use "`f'", clear
    local lo = .
    local hi = .
    foreach v in mb ms mr xb xs xr {
        qui su `v'
        local lo = min(`lo', r(min))
        local hi = max(`hi', r(max))
    }
    local LO`i' = `lo' * 0.40
    local HI`i' = `hi' * 3.2

    * Decade ticks built from the range rather than hardcoded. A fixed list
    * leaves an orphan label floating outside the plot whenever a value falls
    * below the panel's floor.
    local TK`i' ""
    forvalues e = -4/2 {
        local v = 10^(`e')
        if `e' == -4 local lb "0.0001"
        if `e' == -3 local lb "0.001"
        if `e' == -2 local lb "0.01"
        if `e' == -1 local lb "0.1"
        if `e' ==  0 local lb "1"
        if `e' ==  1 local lb "10"
        if `e' ==  2 local lb "100"
        if (`v' >= `LO`i'') & (`v' <= `HI`i'') {
            * Compound double quotes on both sides. The accumulator already
            * holds quoted labels, so a plain "`TK`i''" on the right-hand side
            * closes on the first one it meets and the rest becomes syntax.
            local TK`i' `"`TK`i'' `v' "`lb'""'
        }
    }
    di as txt "panel `i' range: " as res %8.4f `LO`i'' as txt " .. " ///
        as res %8.2f `HI`i''
    * Same reason, again: echoing the tick list needs compound quotes or the
    * display command itself dies on r(198) after the figure is already built.
    di as txt `"  ticks: `TK`i''"'
}

*================================================= formatting, defined ONCE
* Everything below is shared verbatim by both panels.
local DIAG  lcolor("`INK'%40") lpattern(dash) lwidth(thin)
local OARROW lwidth(vthin) msize(vtiny) lcolor("`GREY'%55") ///
             mcolor("`GREY'%55")
local HARROW lwidth(medthick) msize(medsmall) lcolor("`RED'") ///
             mcolor("`RED'")
local MB    msymbol(Oh) msize(small)     mlwidth(medium)
local MS    msymbol(O)  msize(vsmall)
local MR    msymbol(O)  msize(medsmall)
local MLAB  mlabsize(vsmall) mlabcolor("`INK'") mlabgap(1.8)

* No box, no ticks, pale solid rules. Dashes read as data on a chart whose
* one dashed line is the 45-degree reference.
local GRID  grid glcolor("`RULE'") glwidth(vthin) glpattern(solid) notick
local SCL   lcolor(none)
local AXES1 xscale(log range(`LO1' `HI1') `SCL')                              ///
            yscale(log range(`LO1' `HI1') `SCL')                              ///
            xlabel(`TK1', labsize(vsmall) labcolor("`SOFT'") `GRID')          ///
            ylabel(`TK1', labsize(vsmall) labcolor("`SOFT'") angle(0) `GRID')
local AXES2 xscale(log range(`LO2' `HI2') `SCL')                              ///
            yscale(log range(`LO2' `HI2') `SCL')                              ///
            xlabel(`TK2', labsize(vsmall) labcolor("`SOFT'") `GRID')          ///
            ylabel(`TK2', labsize(vsmall) labcolor("`SOFT'") angle(0) `GRID')
local TITLES xtitle("US exports, {c $|}bn per month", size(vsmall)            ///
                color("`SOFT'") margin(t=2))                                  ///
            ytitle("US imports, {c $|}bn per month", size(vsmall)             ///
                color("`SOFT'") margin(r=2))
local REGION graphregion(color(white) lcolor(white))                          ///
            plotregion(color(white) lstyle(none) margin(medium))
* With grc1leg2 the legend is stripped from both panels and redrawn centred,
* so both carry it. Without it, only the left panel does and the right is told
* to draw none - two legends side by side would be the same key printed twice.
* The legend CONTENTS are defined once; where it is placed differs by route, so
* the wrapper legend(...) is built twice rather than appended to. position() is
* a legend suboption - bolting it on after the closing paren makes it a twoway
* option, which does not exist, and Stata answers "option position() not
* allowed".
local LEGBODY order(6 "baseline  Nov 23-Oct 24"                               ///
                    7 "surge  Nov 24-Mar 25"                                  ///
                    8 "reversal  Apr-Nov 25")                                 ///
            cols(3) size(vsmall) region(lcolor(none) color(white))            ///
            symxsize(4) bmargin(zero)
if $USE_GRC1LEG2 {
    local LEG  legend(`LEGBODY')
    local LEGR legend(`LEGBODY')
}
else {
    local LEG  legend(`LEGBODY' position(12) ring(1))
    local LEGR legend(off)
}

*------------------------------------------------------------- left panel
use `comm', clear
twoway ///
  (function y = x, range(`LO1' `HI1') `DIAG') ///
  (pcarrow mb xb ms xs if !hl, `OARROW') ///
  (pcarrow ms xs mr xr if !hl, `OARROW') ///
  (pcarrow mb xb ms xs if hl,  `HARROW') ///
  (pcarrow ms xs mr xr if hl,  `HARROW') ///
  (scatter mb xb if !hl, `MB' mcolor("`GREY'%75")) ///
  (scatter ms xs if !hl, `MS' mcolor("`GREY'%75")) ///
  (scatter mr xr if !hl, `MR' mcolor("`GREY'%75")) ///
  (scatter mb xb if hl,  `MB' mcolor("`RED'")) ///
  (scatter ms xs if hl,  `MS' mcolor("`RED'") msize(small)) ///
  (scatter mr xr if hl,  `MR' mcolor("`RED'") msize(medium) ///
      mlabel(lbl) `MLAB' mlabcolor("`RED'") mlabvposition(mlpos)) ///
  , `AXES1' `TITLES' `REGION' `LEG' ///
  title("By commodity", size(medsmall) color("`INK'") position(11) ///
      justification(left)) ///
  subtitle("100 most-traded HS4 headings; gold in colour", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(gLeft, replace) nodraw
di as txt "STEP  left panel built"

*------------------------------------------------------------ right panel
use `part', clear
twoway ///
  (function y = x, range(`LO2' `HI2') `DIAG') ///
  (pcarrow mb xb ms xs if !hl, `OARROW') ///
  (pcarrow ms xs mr xr if !hl, `OARROW') ///
  (pcarrow mb xb ms xs if hl,  `HARROW') ///
  (pcarrow ms xs mr xr if hl,  `HARROW') ///
  (scatter mb xb if !hl, `MB' mcolor("`GREY'%75")) ///
  (scatter ms xs if !hl, `MS' mcolor("`GREY'%75")) ///
  (scatter mr xr if !hl, `MR' mcolor("`GREY'%75") ///
      mlabel(lbl) `MLAB' mlabvposition(mlpos)) ///
  (scatter mb xb if hl,  `MB' mcolor("`RED'")) ///
  (scatter ms xs if hl,  `MS' mcolor("`RED'") msize(small)) ///
  (scatter mr xr if hl,  `MR' mcolor("`RED'") msize(medium) ///
      mlabel(lbl) `MLAB' mlabcolor("`RED'") mlabvposition(mlpos)) ///
  , `AXES2' `TITLES' `REGION' `LEGR' ///
  title("By partner", size(medsmall) color("`INK'") position(11) ///
      justification(left)) ///
  subtitle("5 largest bilateral gold partners; Switzerland in colour", ///
      size(vsmall) color("`SOFT'") position(11) justification(left)) ///
  name(gRight, replace) nodraw
di as txt "STEP  right panel built"

*-------------------------------------------------------------- combine
* Header order is the masthead's: red tab, bold headline, plain deck, key,
* charts, source. title() and subtitle() are the only two header slots that
* take separate colours, which is why the tab occupies one of them outright.
local HEADER ///
    graphregion(color(white) lcolor(white)) imargin(small) iscale(*0.92) ///
    title("$TAB_GLYPH", size(vsmall) color("`RED'") ///
        position(11) justification(left)) ///
    subtitle("{bf:Gold went in, then came back out}" ///
        "US trade on the balance plane, monthly average within each phase." ///
        "Above the diagonal the United States is a net importer", ///
        size(medsmall) color("`INK'") position(11) justification(left)) ///
    note("South Africa and Hong Kong belong in the right-hand panel by size" ///
        "but trade gold with the United States in one direction only, so they" ///
        "have no position on it" ///
        " " ///
        "Source: US Census Bureau, monthly HS4 trade, November 2023-November 2025", ///
        size(tiny) color("`SOFT'") position(7) justification(left)) ///
    name(gPanel, replace) ysize(7.4) xsize(13)

if $USE_GRC1LEG2 {
    grc1leg2 gLeft gRight, cols(2) legendfrom(gLeft) position(11) ring(1) ///
        `HEADER'
}
else {
    graph combine gLeft gRight, cols(2) `HEADER'
}
di as txt "STEP  panels combined and drawn"

* A nodraw graph cannot be exported - graph export needs a current Graph
* window, and fails r(693) without one even when given name(). So the combined
* graph is drawn, and that is unavoidable rather than an oversight.
* The two exports are separated by breadcrumbs because they are different code
* paths - PDF embeds the font as vectors, PNG rasterises through the Windows
* graphics layer at PNG_WIDTH/xsize dpi - and the report is that the crash comes
* immediately after the final graph appears, which is exactly here.
if $MAKE_PDF {
    di as txt "STEP  starting PDF export"
    graph export "$OUT/gold_panel.pdf", replace
    di as txt "STEP  PDF written"
}
if $PNG_IN_STATA {
    * The crashing path, kept only so the fault can be re-tested.
    di as txt "STEP  starting PNG export IN STATA at width $PNG_WIDTH"
    graph export "$OUT/gold_panel.png", replace width($PNG_WIDTH)
    di as txt "STEP  PNG written by Stata"
}
else {
    di as txt "STEP  rasterising PDF to PNG outside Stata"
    cap confirm file ".venv/Scripts/python.exe"
    if _rc {
        di as err "  .venv not found. Make the PNG yourself with:"
        di as err "    python claude/stata-console/code/pdf_to_png.py " ///
                  "$OUT/gold_panel.pdf --width $PNG_WIDTH"
    }
    else {
        * shell, not winexec: winexec returns immediately and the confirm below
        * would race it.
        shell .venv\Scripts\python.exe claude\stata-console\code\pdf_to_png.py "$OUT/gold_panel.pdf" --width $PNG_WIDTH
        cap confirm file "$OUT/gold_panel.png"
        if _rc di as err "  PNG not produced - run pdf_to_png.py by hand"
        else di as txt "STEP  PNG written from PDF"
    }
}

*----------------------------------------------------------------- put it back
* Leave the session as it was found: no graphs in memory, factory graph font.
graph drop _all
graph set window fontface "$RESTORE_FONT"
di as txt "STEP  font restored to $RESTORE_FONT, graphs dropped"
di as txt "DONE  " c(current_date) " " c(current_time)
cap log close runlog
