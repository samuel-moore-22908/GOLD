"""
Prove the environment works, end to end, in one command.

Every check here is something that was actually observed to fail during setup,
not a hypothetical. Run it after any Stata upgrade.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
PY = REPO / ".venv/Scripts/python.exe"
OUT = ROOT / "output"

sys.path.insert(0, str(HERE))
import stata_env  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("{} {}{}".format("PASS" if ok else "FAIL", name,
                           "  -- " + detail if detail else ""))


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    exe, edition, install = stata_env.find_stata()
    check("locate Stata", exe.exists(), "{} ({})".format(exe.name, install.name))

    stata = stata_env.init(splash=False)
    stata.run("display 2+2", quietly=True)
    check("start Stata in-process", True, "edition " + edition.upper())

    # An error must raise, and must NOT kill the session.
    raised = False
    try:
        stata.run("regress price nonexistent_var")
    except SystemError:
        raised = True
    stata.run("display 1+1", quietly=True)
    check("error raises and session survives", raised)

    # The dtype trap: object-dtype floats out of pyarrow arithmetic.
    import pandas as pd
    df = pd.DataFrame({"a": pd.array([1, 2, 3], dtype="int64[pyarrow]"),
                       "b": pd.array(["x", "y", None], dtype="string"),
                       "d": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])})
    df["ratio"] = df["a"] / pd.array([2, 0, 4], dtype="int64[pyarrow]").to_numpy()
    stata.pdataframe_to_data(stata_env.coerce_for_stata(df), force=True)
    stata.run("count", quietly=True)
    check("pandas -> Stata with mixed dtypes", int(stata.get_return()["r(N)"]) == 3)

    # Round trip back out.
    back = stata.pdataframe_from_data()
    check("Stata -> pandas", list(back.columns) == ["a", "b", "d", "ratio"],
          "{} obs".format(len(back)))

    # Batch mode: exit code must be honest.
    import run_do
    good = OUT / "_smoke_ok.do"
    good.write_text('sysuse auto, clear\nsummarize price\n', encoding="utf-8", newline="\n")
    rc_ok, _ = run_do.run(good, log_path=OUT / "_smoke_ok.log", echo=False)
    check("batch: clean do-file returns 0", rc_ok == 0)

    bad = OUT / "_smoke_bad.do"
    bad.write_text('sysuse auto, clear\nregress price nonexistent_var\n',
                   encoding="utf-8", newline="\n")
    rc_bad, text = run_do.run(bad, log_path=OUT / "_smoke_bad.log", echo=False)
    check("batch: failing do-file returns nonzero", rc_bad != 0,
          "Stata itself exits 0 here; the log said r(111)")

    # The BOM trap.
    bom = OUT / "_smoke_bom.do"
    bom.write_bytes(b"\xef\xbb\xbfdisplay \"bom test\"\n")
    rc_bom, _ = run_do.run(bom, log_path=OUT / "_smoke_bom.log", echo=False)
    check("batch: BOM is stripped, not fatal", rc_bom == 0)

    # Parquet, if this repo has any on disk.
    pq = sorted((REPO / "transfer/raw").glob("*.parquet"))
    if pq:
        rows, cols = stata_env.load_parquet(stata, pq[0])
        stata.run("count", quietly=True)
        check("parquet -> Stata", int(stata.get_return()["r(N)"]) == rows,
              "{:,} obs x {} vars from {}".format(rows, cols, pq[0].name))
    else:
        check("parquet -> Stata", True, "skipped, no parquet on disk")

    for f in OUT.glob("_smoke_*"):
        f.unlink()

    failed = [n for n, ok, _ in results if not ok]
    print("\n{}/{} passed".format(len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
