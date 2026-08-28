"""
Run a .do file from the terminal and get a truthful exit code.

The trap this exists for:

    StataMP-64.exe /e do broken.do   ->   exit code 0

Stata's Windows batch mode returns 0 whether the do-file succeeded or died on
r(111). Nothing in the shell, and nothing in a Makefile or CI step, can tell the
difference without reading the log. This runner reads the log, finds the r(nnn)
that Stata wrote there, echoes it, and exits with 1. That is the entire point.

Second trap, also silent: a .do file saved with a UTF-8 byte-order mark makes
Stata reject its own first line --

    'display is not a valid command name
    r(199);

Windows PowerShell's `Set-Content -Encoding utf8` and `>` both write a BOM by
default, so this is easy to hit and baffling to diagnose. The runner detects the
BOM, says so loudly, and runs a stripped copy rather than failing on it.

Usage:
    python claude/stata-console/code/run_do.py analysis.do
    python claude/stata-console/code/run_do.py analysis.do --args 2024 CHE
    python claude/stata-console/code/run_do.py analysis.do --log out/run.log
    python claude/stata-console/code/run_do.py analysis.do --cwd some/other/dir
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stata_env  # noqa: E402

# Stata writes its return code to the log as "r(111);" on a line of its own.
RC_RE = re.compile(r"^r\((\d+)\);\s*$", re.MULTILINE)
BOM = b"\xef\xbb\xbf"


def strip_bom(path):
    """Return a path Stata can read. Copies to a temp file if a BOM is present."""
    raw = path.read_bytes()
    if not raw.startswith(BOM):
        return path, False
    tmp = Path(tempfile.mkdtemp(prefix="stata_nobom_")) / path.name
    tmp.write_bytes(raw[len(BOM):])
    return tmp, True


def run(do_path, do_args=(), log_path=None, echo=True, cwd=None):
    """Execute a do-file. Returns (returncode, log_text).

    returncode is 0 only if Stata logged no error.

    `cwd` defaults to the caller's working directory, NOT the do-file's own
    directory. Relative paths inside a do-file therefore mean the same thing
    they mean on the command line, which is what anyone running
    `run_do.py claude/thing/code/x.do` from the repo root expects.
    """
    do_path = Path(do_path).resolve()
    if not do_path.exists():
        raise SystemExit("No such do-file: {}".format(do_path))

    exe, _, _ = stata_env.find_stata()
    target, had_bom = strip_bom(do_path)
    if had_bom:
        print("WARNING: {} starts with a UTF-8 BOM, which Stata treats as part of\n"
              "         the first command. Running a stripped copy. Re-save the file\n"
              "         as UTF-8 without BOM to fix it permanently."
              .format(do_path.name), file=sys.stderr)

    # Stata writes <stem>.log into the working directory. Clear it first, so a
    # stale log from an earlier run can never be mistaken for this one's.
    workdir = Path(cwd).resolve() if cwd else Path.cwd()
    produced = workdir / (target.stem + ".log")
    if produced.exists():
        produced.unlink()

    cmd = [str(exe), "/e", "do", str(target), *[str(a) for a in do_args]]
    subprocess.run(cmd, cwd=str(workdir), check=False)

    if not produced.exists():
        print("Stata produced no log at {}. It may not have started."
              .format(produced), file=sys.stderr)
        return 1, ""

    text = produced.read_text(encoding="utf-8", errors="replace")
    if echo:
        sys.stdout.write(text)

    dest = Path(log_path) if log_path else do_path.with_suffix(".log")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if produced.resolve() != dest.resolve():
        shutil.copyfile(produced, dest)
        # Stata writes its log into the working directory, which since the cwd
        # change is usually the repo root. Move it rather than copy, so a run
        # does not litter the root with one .log per do-file.
        produced.unlink()

    codes = [int(m) for m in RC_RE.findall(text)]
    if codes:
        print("\nSTATA ERROR r({}) -- see {}".format(codes[0], dest), file=sys.stderr)
        return 1, text
    return 0, text


def main():
    ap = argparse.ArgumentParser(
        description="Run a Stata do-file in batch and exit nonzero if it failed.")
    ap.add_argument("do_file")
    ap.add_argument("--args", nargs="*", default=[],
                    help="arguments passed through to the do-file as `1, `2, ...")
    ap.add_argument("--log", help="where to keep the log (default: beside the do-file)")
    ap.add_argument("--cwd", help="working directory for the run (default: here)")
    ap.add_argument("--quiet", action="store_true", help="do not echo the log to stdout")
    a = ap.parse_args()

    rc, _ = run(a.do_file, a.args, a.log, echo=not a.quiet, cwd=a.cwd)
    sys.exit(rc)


if __name__ == "__main__":
    main()
