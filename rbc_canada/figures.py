"""Draw the charts: model and data moments, impulse responses, and the model run on measured technology."""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data import FIGURES, OUTPUT
from estimate import NAMES, RECESSIONS, SAMPLE, SERIES

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False})
SOURCE = ("Source: Statistics Canada tables 36-10-0104 (GDP by expenditure), 36-10-0103 (GDP by income), 14-10-0289 and "
          "14-10-0287 (Labour Force Survey) and 36-10-0580 (national balance sheets).")


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 140)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def moments():
    m = pd.read_csv(OUTPUT / "moments.csv")
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.6))
    fig.subplots_adjust(left=0.13, right=0.98, top=0.78, bottom=0.2, wspace=0.55)
    panels = [("sd", "Standard deviation, %"), ("corr_output", "Correlation with output"),
              ("autocorr", "Correlation with previous quarter")]
    for ax, (stat, label) in zip(axes, panels):
        s = m[m.statistic == stat].set_index("variable").loc[SERIES]
        names = [NAMES[v] for v in SERIES]
        if stat == "corr_output":
            s = pd.concat([s.drop("y"), m[m.statistic == "corr_hours_productivity"]])
            names = names[1:] + ["Hours with\noutput per hour"]
        rows = np.arange(len(s))[::-1]
        ax.hlines(rows, s.model_p05, s.model_p95, color=BLUE, lw=3, alpha=0.35)
        ax.plot(s.model, rows, "o", color=BLUE, ms=7, label="Model (90% of samples)")
        ax.plot(s.data, rows, "D", color=ORANGE, ms=7, label=f"Canada, {SAMPLE[0]}-{SAMPLE[1]}")
        ax.set_yticks(rows, names)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="y", visible=False)
        ax.set_title(label, fontsize=11, color=MUTED, loc="left")
        ax.axvline(0, color=MUTED, lw=0.8)
        ax.set_xlim(*((0, 1.1 * s[["data", "model_p95"]].max().max()) if stat == "sd" else (-0.5, 1.05)))
    axes[0].legend(loc="upper left", bbox_to_anchor=(-0.3, 1.22), ncol=2, fontsize=10)
    save(fig, "moments.png", "The model's cycles are smaller than Canada's, and hours miss most",
         "Hodrick-Prescott cycles (lambda 1600) in Canadian data and in 1,000 model samples of the same length",
         "Model samples are simulated from the calibrated model and filtered the same way as the data; bars span the "
         "5th to 95th percentiles across samples. Output per hour is output divided by total actual hours worked. "
         + SOURCE)


def impulse_responses():
    r = pd.read_csv(OUTPUT / "impulse_responses.csv")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.975, top=0.84, bottom=0.2)
    lines = [("i", ORANGE, "-", "Investment"), ("y", INK, "-", "Output"), ("h", AQUA, "-", "Hours"),
             ("c", BLUE, "-", "Consumption"), ("k", MUTED, "--", "Capital"), ("z", MUTED, ":", "Technology")]
    for v, colour, ls, label in lines:
        ax.plot(r.quarter, r[v], color=colour, ls=ls, lw=2, label=label)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlim(0, r.quarter.max())
    ax.set_xlabel("Quarters after the shock")
    ax.set_ylabel("Per cent from steady state")
    ax.legend(ncol=3, fontsize=9, loc="upper right")
    save(fig, "impulse_responses.png", "After a technology shock, investment jumps and consumption rises slowly",
         "Responses to a one-standard-deviation rise in technology in the calibrated model",
         "Log-linear solution. Technology persistence and shock size are estimated from Canada's Solow residual, "
         f"{SAMPLE[0]}-{SAMPLE[1]}. " + SOURCE)


def history():
    h = pd.read_csv(OUTPUT / "history.csv")
    t = pd.PeriodIndex(h.quarter, freq="Q").to_timestamp()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.85, bottom=0.14, hspace=0.25)
    for ax, v in zip(axes, ("y", "h")):
        for start, end in RECESSIONS.values():
            ax.axvspan(pd.Period(start).start_time, pd.Period(end).end_time, color=GRID, lw=0)
        ax.plot(t, h[f"data_{v}"], color=ORANGE, lw=1.8, label="Canada")
        ax.plot(t, h[f"model_{v}"], color=BLUE, lw=1.8, label="Model, given measured technology")
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(NAMES[v], fontsize=11, color=MUTED, loc="left")
        ax.set_ylabel("Per cent from trend")
    axes[0].legend(ncol=2, fontsize=9, loc="lower left")
    save(fig, "history.png", "Measured technology tracks output's cycle better than hours'",
         "Hodrick-Prescott cycles in the data and in the model fed Canada's detrended Solow residual, quarter by quarter",
         "The model starts at steady-state capital in 1976Q1 and is filtered the same way as the data. Shaded: "
         "recessions dated by the C.D. Howe Institute Business Cycle Council. " + SOURCE)


def main():
    FIGURES.mkdir(exist_ok=True)
    moments()
    impulse_responses()
    history()


if __name__ == "__main__":
    main()
