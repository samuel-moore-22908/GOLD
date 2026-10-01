"""
Figure 1 of spread_system.tex: the monthly location premium against the carry
wedge, 2019-2026.

Reads the daily curve fits through spread_model_checks.fit_daily(), so the
figure and every number in the paper come from one implementation.

Run from the repo root:
    .venv/Scripts/python.exe claude/spread-explainer/make_paper_figure.py

Writes claude/spread-explainer/spread_system_fig1.pdf
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spread_model_checks import fit_daily  # noqa: E402

OUT = Path(__file__).with_name("spread_system_fig1.pdf")

# Dated policy events, from data/processed/federal_register_events.csv and
# cbp_gold_bar_rulings.csv, which is where the paper's episode windows come from.
EVENTS = (("2024-11-05", "US election"),
          ("2025-04-07", "EO 14257"),
          ("2025-07-31", "CBP N351466"))


def main():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9,
        "axes.linewidth": 0.6,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "pdf.fonttype": 42,
    })

    f = fit_daily()
    m = (f.resample("ME")
          .agg(level=("level_pct", "mean"), omega=("omega_pp", "mean"), n=("level_pct", "size"))
          .loc["2019":])
    # Reindex to a complete monthly grid and blank thin months, so that a gap in
    # the underlying data is drawn as a gap rather than interpolated across.
    m = m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="ME"))
    m.loc[m.n.fillna(0) < 6, ["level", "omega"]] = float("nan")

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.axhline(0, color="black", lw=0.5)
    ax.plot(m.index, m.omega, color="0.55", lw=1.1, ls="--",
            label=r"carry wedge $\hat{\omega}_t$, pp a year")
    ax.plot(m.index, m.level, color="black", lw=1.3,
            label=r"location premium $\hat{p}_t$, per cent of spot")

    top = ax.get_ylim()[1]
    for date, lab in EVENTS:
        ax.axvline(pd.Timestamp(date), color="0.72", lw=0.6, ls=":")
        ax.annotate(lab, xy=(pd.Timestamp(date), top), xytext=(2.5, -3),
                    textcoords="offset points", fontsize=6.5, color="0.3",
                    rotation=90, va="top", ha="left")

    ax.set_ylabel("per cent")
    ax.legend(frameon=False, loc="upper left", fontsize=7.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
