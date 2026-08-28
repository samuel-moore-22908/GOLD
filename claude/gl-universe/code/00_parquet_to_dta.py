"""
Convert the universe-tier parquet pulls into two .dta files.

Mechanical only -- Stata 18 cannot read parquet, and nothing analytic happens
here. Every decision that affects a number lives in 01_grubel_lloyd.do, so that
the do-file is the whole method and can be read on its own.
"""
import glob
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "stata-console/code"))
import stata_env  # noqa: E402

RAW = Path("transfer/raw")
OUT = Path("claude/gl-universe/output")

KEEP = {
    "imports": ["I_COMMODITY", "time", "GEN_VAL_MO", "CON_VAL_MO"],
    "exports": ["E_COMMODITY", "time", "DF", "ALL_VAL_MO"],
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stata = stata_env.init(splash=False)

    for flow in ("imports", "exports"):
        files = sorted(RAW.glob("universe_{}_*.parquet".format(flow)))
        if not files:
            raise SystemExit("No universe {} parquet under {}".format(flow, RAW))
        df = pd.concat([pd.read_parquet(f, columns=KEEP[flow]) for f in files],
                       ignore_index=True)
        df = df.rename(columns={"I_COMMODITY": "hs6", "E_COMMODITY": "hs6"})

        # The universe tier is CTY_CODE="-" only, so (hs6, time[, DF]) must be
        # unique. If it is not, something upstream changed and every GL below
        # would be computed on doubled values.
        key = ["hs6", "time"] + (["DF"] if flow == "exports" else [])
        dup = df.duplicated(key).sum()
        if dup:
            raise SystemExit("{:,} duplicate rows on {} in {} -- stop".format(
                dup, key, flow))

        dest = OUT / "universe_{}.dta".format(flow)
        stata.pdataframe_to_data(stata_env.coerce_for_stata(df), force=True)
        stata.run('save "{}", replace'.format(dest.as_posix()), quietly=True)
        print("{:<8} {:>9,} rows x {} vars -> {}".format(
            flow, len(df), df.shape[1], dest.name))


if __name__ == "__main__":
    main()
