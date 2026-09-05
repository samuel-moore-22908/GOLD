"""
Write the three mechanism figures' inputs in a form Stata can plot directly.

The series themselves are built by validate_mechanism.py and imported from it,
so there is one implementation of the constant-maturity spread and not two. What
this adds is only what a plotting program needs and an analysis file should not
carry:

  * GAP MARKERS. CLAUDE.md requires data gaps to be drawn as gaps, and Stata's
    -line- happily draws straight through a missing fortnight. Inserting an
    all-missing row inside every gap longer than a week forces the break. The
    threshold has to sit above a long weekend or the line shatters at every
    public holiday, and below a fortnight or real holes survive.
  * EPISODE TAGS. Which of the three location shocks a month belongs to, so the
    scatter can colour them without hard-coding date ranges in the do-file.
  * BUCKET MEDIANS. The hinge drawn on Figure 3 is the bucket medians, not a
    fit. Computing them here keeps that visible rather than buried in a graph
    command.

Reads   whatever validate_mechanism.py reads
Writes  claude/mechanism-figures/fig2_dislocation.csv
        claude/mechanism-figures/fig3_monthly.csv
        claude/mechanism-figures/fig3_hinge.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_mechanism import CALM, constant_maturity, swiss_tonnes  # noqa: E402

OUT = Path("claude/mechanism-figures")

# Figure 2's window. Starts far enough before the election to show what the
# quantity looks like when nothing is wrong, ends after the reversal has run.
FIG2 = ("2024-06-01", "2025-12-31")
# Longer than a holiday weekend, shorter than a real hole.
GAP_DAYS = 7

# The three location shocks. Only the first is the paper's subject; the other
# two are what stop the hinge being a story about tariffs.
EPISODES = {
    1: ("2024-11-01", "2025-11-01", "tariff scare"),
    2: ("2020-03-01", "2020-10-01", "covid"),
    3: ("2022-03-01", "2022-03-01", "sanctions"),
}

# Months worth naming on the scatter. Anything else would be clutter.
CALLOUTS = {
    "2025-01": "Jan 2025", "2025-02": "Feb 2025", "2020-04": "Apr 2020",
    "2020-05": "May 2020", "2022-03": "Mar 2022", "2025-07": "Jul 2025",
    "2025-10": "Oct 2025", "2025-04": "Apr 2025",
}

BUCKETS = [-99, -0.5, 0, 0.5, 1.0, 1.5, 99]


def with_gaps(df, threshold=GAP_DAYS):
    """Insert an all-missing row inside every gap longer than `threshold` days."""
    gaps = df.index.to_series().diff().dt.days
    breaks = [d - pd.Timedelta(days=1) for d in df.index[gaps > threshold]]
    if not breaks:
        return df
    pad = pd.DataFrame(index=pd.DatetimeIndex(breaks), columns=df.columns, dtype=float)
    return pd.concat([df, pad]).sort_index()


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- figure 2
    daily = constant_maturity()
    calm = daily.loc[CALM[0]:CALM[1], "disloc_pp_10d"]
    lo, hi = calm.mean() - calm.std(), calm.mean() + calm.std()

    f2 = daily.loc[FIG2[0]:FIG2[1], ["disloc_pp", "disloc_pp_10d"]].copy()
    f2 = with_gaps(f2)
    # Band edges ride along as columns so -rarea- has something to span. They are
    # constants; carrying them as data is cheaper than reconstructing the calm
    # window inside the do-file.
    f2["band_lo"], f2["band_hi"] = lo, hi
    f2.index.name = "date"
    f2.to_csv(OUT / "fig2_dislocation.csv", date_format="%Y-%m-%d")
    print(f"fig2_dislocation.csv  {len(f2)} rows "
          f"({int(f2.disloc_pp.isna().sum())} gap markers), "
          f"band {lo:+.2f} to {hi:+.2f} pp")

    # ------------------------------------------------------------ figures 3, 4
    mon = daily[["disloc_pp", "excess_usd"]].groupby(
        daily.index.to_period("M")).mean()
    mon.index = mon.index.to_timestamp()
    m = pd.concat([mon, swiss_tonnes()], axis=1, sort=True)
    m = m.loc["2015-01-01":]

    m["episode"] = 0
    for code, (lo_d, hi_d, _) in EPISODES.items():
        m.loc[m.index.to_series().between(lo_d, hi_d), "episode"] = code

    m["ym"] = m.index.strftime("%Y-%m")
    m["callout"] = m.ym.map(CALLOUTS).fillna("")
    # A month needs both a spread and a tonnage to be a dot; the time-series
    # panel keeps the rest, so the two are flagged rather than filtered.
    m["on_scatter"] = (m.disloc_pp.notna() & m.che_to_us_t.notna()).astype(int)
    m.to_csv(OUT / "fig3_monthly.csv", index=False,
             columns=["ym", "disloc_pp", "excess_usd", "che_to_us_t",
                      "us_to_che_t", "episode", "callout", "on_scatter"])
    print(f"fig3_monthly.csv      {len(m)} months, "
          f"{int(m.on_scatter.sum())} on the scatter, "
          f"{int((m.episode > 0).sum())} tagged to an episode")

    # ------------------------------------------------------- the drawn hinge
    s = m[m.on_scatter == 1].copy()
    s["bucket"] = pd.cut(s.disloc_pp, BUCKETS)  # still in rate space: the
    # bucket table is a summary of the raw relationship, not the fitted model
    h = s.groupby("bucket", observed=True).agg(
        n=("che_to_us_t", "size"),
        med_west=("che_to_us_t", "median"),
        med_east=("us_to_che_t", "median"),
        x=("disloc_pp", "median"))
    # Plot the medians at the median x of each bucket, not the bucket midpoint:
    # the open-ended end buckets have no midpoint, and the interior ones are not
    # evenly populated.
    h = h.reset_index(drop=True)
    h.to_csv(OUT / "fig3_hinge.csv", index=False)
    print(f"fig3_hinge.csv        {len(h)} buckets")
    print(h.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
