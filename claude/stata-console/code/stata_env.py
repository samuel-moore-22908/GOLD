"""
Locate Stata on this machine and bring it up inside Python.

Nothing here is pinned to a version or an install path: the executable is
discovered by scanning Program Files, so a Stata 19 upgrade needs no edit. The
edition letter is read off the executable's own filename rather than assumed,
because pystata.config.init() refuses to start against the wrong one.

Shared by stata_console.py (interactive) and run_do.py (batch).
"""
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# StataMP-64.exe -> "mp". pystata wants the lowercase edition code.
EXE_RE = re.compile(r"^Stata(MP|SE|BE|IC)-64\.exe$", re.IGNORECASE)
SEARCH_ROOTS = [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)"), Path("C:/")]

# Stata stores %tc datetimes as milliseconds since this instant.
STATA_EPOCH = pd.Timestamp("1960-01-01")


def find_stata():
    """Return (exe_path, edition, install_dir) for the newest Stata installed.

    Raises rather than guessing. A wrong path here fails deep inside a C
    extension with an unhelpful message, so it is worth failing early and
    saying exactly what was searched.
    """
    override = os.environ.get("STATA_HOME")
    roots = [Path(override)] if override else []
    if not roots:
        for r in SEARCH_ROOTS:
            if r.is_dir():
                roots += sorted(r.glob("Stata*"), reverse=True)  # Stata19 before Stata18

    for d in roots:
        if not d.is_dir():
            continue
        for exe in sorted(d.iterdir()):
            m = EXE_RE.match(exe.name)
            if m:
                return exe, m.group(1).lower(), d
    raise SystemExit(
        "No Stata install found. Looked under:\n  "
        + "\n  ".join(str(r) for r in (roots or SEARCH_ROOTS))
        + "\nSet STATA_HOME to the install directory if it lives elsewhere.")


def init(splash=True):
    """Start Stata in this process and return the pystata `stata` module.

    pystata ships inside the Stata install, not on PyPI, so sys.path is pointed
    at it there. Importing pystata does not start Stata; config.init() does, and
    it can only be called once per process.
    """
    _, edition, install = find_stata()
    utils = install / "utilities"
    if str(utils) not in sys.path:
        sys.path.insert(0, str(utils))

    import pystata

    if splash:
        pystata.config.init(edition)
    else:
        # config.init() always prints the licence banner. Swallow it when the
        # caller wants clean stdout; stderr is left alone so failures show.
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            pystata.config.init(edition)

    from pystata import stata
    return stata


def coerce_for_stata(df):
    """Return a copy of `df` whose dtypes survive the handoff into Stata.

    Necessary, not defensive. pandas 3 reads parquet into pyarrow-backed dtypes,
    and arithmetic on those can land in `object` -- dividing an int64 column by
    one holding <NA> produces an object column of Python floats. pystata's
    pdataframe_to_data() then fails with "failed to store the string value in
    the current Stata dataset", which names neither the column nor the cause.

    Rules applied, in order: object columns that are numeric underneath are
    converted back to numbers; datetimes become %tc doubles; booleans and
    nullable numerics become float64 (Stata has no separate missing-integer);
    everything else becomes str, with missing as "" rather than the string
    "None" or "<NA>".
    """
    out = pd.DataFrame(index=range(len(df)))
    for c in df.columns:
        s = df[c].reset_index(drop=True)

        if s.dtype == object:
            conv = pd.to_numeric(s, errors="coerce")
            if conv.notna().sum() >= s.notna().sum():   # nothing was lost
                s = conv

        if pd.api.types.is_datetime64_any_dtype(s):
            ms = (s - STATA_EPOCH) / pd.Timedelta("1ms")
            out[c] = pd.to_numeric(ms, errors="coerce").astype("float64")
        elif pd.api.types.is_bool_dtype(s):
            out[c] = s.astype("float64")
        elif pd.api.types.is_numeric_dtype(s):
            if pd.api.types.is_integer_dtype(s) and not s.isna().any():
                out[c] = np.asarray(s, dtype="int64")
            else:
                out[c] = pd.to_numeric(s, errors="coerce").astype("float64")
        else:
            out[c] = s.astype("object").where(s.notna(), "").map(
                lambda v: v if isinstance(v, str) else "" if v is None else str(v))
    return out


def datetime_columns(df):
    """Names of the columns coerce_for_stata() turned into %tc doubles, so the
    caller can apply the format and have them print as dates, not as 2.0e+12."""
    return [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]


def load_parquet(stata, path, columns=None, query=None):
    """Read a parquet file into Stata's dataset in memory. Returns (rows, cols).

    Stata 18 cannot read parquet, and every dataset in this repo is parquet.
    That is the whole reason to drive Stata from Python here rather than from
    its own console.

    `query` is a pandas .query() string applied before the handoff. Filtering in
    pandas is far cheaper than loading sixteen million rows into Stata and then
    dropping most of them.
    """
    df = pd.read_parquet(path, columns=columns)
    if query:
        df = df.query(query)
    dates = datetime_columns(df)
    stata.pdataframe_to_data(coerce_for_stata(df), force=True)
    for c in dates:
        stata.run("format {} %tc".format(c), quietly=True)
    return df.shape
