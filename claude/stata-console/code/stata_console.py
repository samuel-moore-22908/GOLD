"""
An interactive Stata prompt in the terminal.

Stata for Windows ships no console binary -- StataMP-64.exe is a GUI
application, and its only headless mode is a one-shot batch run. This gets a
real REPL by starting Stata inside Python through pystata, which is the
supported embedding interface and is already in the install.

What that buys beyond a plain Stata window:

  * parquet, which Stata 18 cannot read at all, and which is the format every
    dataset in this repo is stored in
  * the same terminal as everything else -- pipeable, scriptable, no window
  * a live pandas session next to the Stata one, so a frame can be pushed in,
    modelled, and pulled back without touching disk

Usage:
    python claude/stata-console/code/stata_console.py
    python claude/stata-console/code/stata_console.py --quiet
    echo "sysuse auto, clear" | python claude/stata-console/code/stata_console.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stata_env  # noqa: E402

BANNER = """
Stata {edition} {version} -- interactive, in the terminal.

  <command>              run it in Stata
  %parquet PATH [QUERY]  load a parquet file into Stata (QUERY is pandas .query)
  %use PATH              load a .dta
  %save PATH             save the dataset to .dta
  %df NAME               copy Stata's dataset into a pandas frame named NAME
  %py EXPR               evaluate Python; the frames live in the same session
  %help                  this list
  exit / quit / Ctrl-D   leave (does not end Stata's own session cleanly, just
                         drops the process, which is fine -- nothing is cached)

Multi-line blocks work: a line ending in an open brace keeps reading until the
braces balance, so foreach / forvalues / program blocks paste in whole.
"""


class Console:
    def __init__(self, splash=True):
        self.stata = stata_env.init(splash=splash)
        self.ns = {"stata": self.stata, "env": stata_env}
        import pandas as pd
        self.ns["pd"] = pd

    # ---------------------------------------------------------------- meta
    def meta(self, line):
        """Handle a %command. Returns True if the line was consumed."""
        if not line.startswith("%"):
            return False
        parts = line[1:].split(None, 1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "help":
            print(BANNER.format(edition="", version=""))
        elif cmd == "parquet":
            # "%parquet path.parquet DF == '2'" -- the query is optional and
            # everything after the first whitespace-free path is passed to it.
            bits = arg.split(None, 1)
            path = bits[0].strip('"')
            query = bits[1] if len(bits) > 1 else None
            rows, cols = stata_env.load_parquet(self.stata, path, query=query)
            print("loaded {:,} obs, {} vars from {}".format(rows, cols, Path(path).name))
        elif cmd == "use":
            self.stata.run('use "{}", clear'.format(arg.strip('"')))
        elif cmd == "save":
            self.stata.run('save "{}", replace'.format(arg.strip('"')))
        elif cmd == "df":
            name = arg or "df"
            self.ns[name] = self.stata.pdataframe_from_data()
            print("{} = {} obs x {} vars".format(name, *self.ns[name].shape))
        elif cmd == "py":
            try:
                value = eval(arg, self.ns)          # noqa: S307 -- an interactive prompt
                if value is not None:
                    print(value)
            except SyntaxError:
                exec(arg, self.ns)                  # noqa: S102 -- statements too
        else:
            print("unknown meta-command %{}. %help lists them.".format(cmd))
        return True

    # ---------------------------------------------------------------- loop
    def run_line(self, line):
        try:
            self.stata.run(line)
        except SystemError as exc:
            # pystata raises SystemError carrying Stata's own r(nnn) message.
            # Print it and keep the session -- an interactive typo should not
            # end the process the way it would end a batch run.
            print(str(exc).rstrip(), file=sys.stderr)

    def loop(self, stream, interactive):
        buf = []
        depth = 0
        while True:
            if interactive:
                sys.stdout.write("... " if buf else ". ")
                sys.stdout.flush()
            line = stream.readline()
            if not line:
                break
            line = line.rstrip("\n")
            stripped = line.strip()

            if not buf:
                if stripped in ("exit", "quit", "exit, clear"):
                    break
                if not stripped:
                    continue
                if self.meta(stripped):
                    continue

            buf.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                self.run_line("\n".join(buf))
                buf, depth = [], 0


def main():
    ap = argparse.ArgumentParser(description="Interactive Stata in the terminal.")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress Stata's licence banner and the usage header")
    a = ap.parse_args()

    interactive = sys.stdin.isatty()
    try:                                    # optional: arrow-key history
        import readline  # noqa: F401
    except ImportError:
        pass

    console = Console(splash=not a.quiet)
    if interactive and not a.quiet:
        _, edition, install = stata_env.find_stata()
        print(BANNER.format(edition=edition.upper(), version=install.name.replace("Stata", "")))

    console.loop(sys.stdin, interactive)
    if interactive:
        print()


if __name__ == "__main__":
    main()
