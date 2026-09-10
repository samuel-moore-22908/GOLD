*! Find out what this machine's Stata can actually export, and what it cannot.
*!
*! Both graph export .pdf and .png kill Stata 18/MP in the GUI on the figure-1
*! panel - the PDF prints "cannot publish pdf" first, the PNG dies silently.
*! The same exports succeed every time in batch through run_do.py on the same
*! machine and the same install, so this is specific to an interactive session
*! and cannot be reproduced from here.
*!
*! This separates the three candidate causes by brute force. It draws a
*! deliberately trivial graph - ten points, no arrows, no labels, no exotic
*! glyphs - and exports it in five formats under three fonts. A trivial graph
*! removes complexity from the question, so:
*!
*!   everything passes      -> the fault is the FIGURE (size or complexity),
*!                             not the format or the font. Go to STAGE 2.
*!   one font fails         -> the fault is that FONT. Arial Narrow is the
*!                             suspect; it is a separate family on Windows and
*!                             is awkward to embed.
*!   one format fails       -> use another format. SVG and EPS are different
*!                             writers from PDF and PNG and are tried first.
*!
*! CRASHES, not errors, are what we are hunting: capture cannot catch a process
*! death, so read the log rather than the return codes. Whatever TRY line is
*! LAST in the log is the combination that killed Stata. Formats are ordered
*! least-suspect first so that as much is learned as possible before it dies.
*!
*! Run it from the GUI, the way the real do-file is run when it crashes. Then
*! send me claude/gold-panel/probe/export_probe.log - if Stata dies the log is
*! still on disk, which is the entire point.
*!
*! STAGE 2 (set the global below) repeats the exercise on the real figure, to
*! separate size from complexity. Only worth running if stage 1 is all-clear.

version 18
clear all
set more off
* Not hardcoded to one machine: try the author's path, otherwise assume the
* session is already in the repo, and fail loudly rather than running against
* whatever directory happens to be current.
cap cd "C:/Users/smoor/GitHub/GOLD"
cap confirm file "claude/gold-panel/gold_panel.do"
if _rc {
    di as err "Not in the GOLD repo. cd there first, then run this again."
    di as err "  current directory: `c(pwd)'"
    exit 170
}

global STAGE 1        // 1 = trivial graph, 2 = the real 13x7.4in panel

global PROBE "claude/gold-panel/probe"
cap mkdir "$PROBE"

cap log close _all
log using "$PROBE/export_probe.log", replace text name(probe)

di as txt "START  " c(current_date) " " c(current_time)
di as txt "       Stata " c(stata_version) " " c(edition_real) " " c(bit) "-bit, " ///
    c(processors) " cores, memory " c(memory) ", max_memory " c(max_memory)
di as txt "       os " c(os) " " c(osdtl) ", machine " c(machine_type)
di as txt "       STAGE $STAGE"

* Whatever the window font is right now, before anything touches it. Stata
* offers no c() macro for this, so it is only recorded by eye from the table.
di as txt _n "{hline 60}" _n "graph window fonts as found:" _n "{hline 60}"
graph set window

* Least suspect first. SVG and EPS are different writers from the two that are
* known to die, so if either survives there is a way out even if the others
* never work.
local FORMATS svg eps tif png pdf

if $STAGE == 1 {
    sysuse auto, clear
    keep in 1/10
}
else {
    * The real thing, rebuilt by the figure do-file. Run gold_panel.do first
    * with MAKE_PDF 0 and PNG_IN_STATA 0 so it builds without exporting, then
    * this reuses the graph it left in memory.
    cap graph describe gPanel
    if _rc {
        di as err "STAGE 2 needs gPanel in memory. Run gold_panel.do first with"
        di as err "  global MAKE_PDF 0"
        di as err "  global PNG_IN_STATA 0"
        cap log close probe
        exit 198
    }
}

foreach face in "AS FOUND" "Arial Narrow" "Arial" {

    if "`face'" != "AS FOUND" {
        graph set window fontface "`face'"
    }
    di as txt _n "{hline 60}"
    di as txt "FONT  `face'"
    di as txt "{hline 60}"

    if $STAGE == 1 {
        * Rebuilt under each font, since the font is baked in at draw time.
        twoway (scatter mpg weight), name(probeg, replace) ///
            title("probe") subtitle("ten points, nothing exotic")
    }
    else {
        graph display gPanel
    }
    di as txt "  drew the graph"

    foreach fmt of local FORMATS {
        * The line is written BEFORE the attempt, so a process death leaves it
        * as the last thing in the log. That is the whole diagnostic.
        di as txt "TRY   font=`face'  format=`fmt'"
        cap graph export "$PROBE/probe_`fmt'.`fmt'", replace
        if _rc  di as err  "  FAILED rc=" _rc
        else    di as txt  "  ok"
    }
}

*------------------------------------------------------------------- tidy up
graph drop _all
graph set window fontface "Times New Roman"
di as txt _n "DONE   " c(current_date) " " c(current_time)
di as txt "Window font left at Times New Roman (Stata's default)."
di as txt "Send claude/gold-panel/probe/export_probe.log"
cap log close probe
