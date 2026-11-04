"""Draw the charts: the raw trends, and the Arizona x year effects for each outcome."""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data import FIGURES, OUTPUT
from estimate import REF

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False})
SOURCE = ("Source: NCES Common Core of Data via the Urban Institute Education Data API; US Census Bureau intercensal "
          "county estimates. Regular traditional public schools; years are the fall of each school year.")


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 140)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def law(ax):
    ax.axvline(REF + 0.5, color=MUTED, lw=1, ls=":")
    ax.text(REF + 0.6, 1.0, "first charters open", transform=ax.get_xaxis_transform(), color=MUTED, fontsize=9, va="bottom")


def levels():
    m = pd.read_csv(OUTPUT / "means.csv")
    c = pd.read_csv(OUTPUT / "charter_share.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.4), gridspec_kw={"width_ratios": [1.6, 1]})
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    for state, colour in (("AZ", BLUE), ("NM", ORANGE)):
        s = m[m.state == state]
        a.plot(s.year, 100 * s.white_share, color=colour, lw=2, label=f"{state} schools")
        a.plot(s.year, 100 * s.youth_white_share, color=colour, lw=1.5, ls="--", label=f"{state} county children 5-19")
        k = c[(c.state == state) & (c.year >= 1999)]
        b.plot(k.year, 100 * k.charter_share, color=colour, lw=2, marker="o", ms=4, label=state)
    law(a)
    a.set_ylabel("White non-Hispanic, %")
    a.legend(ncol=2, fontsize=9, loc="lower left")
    b.set_ylabel("Share of public school students, %")
    b.set_title("In charter schools", fontsize=11, color=MUTED, loc="left")
    b.legend()
    save(fig, "levels.png", "Arizona's schools were getting less white before charters arrived",
         "Average white non-Hispanic share in traditional public schools, and among each county's children",
         SOURCE + " Charter shares start in 1999-2000, the first year Arizona's charter schools are flagged in the data.")


def effects(outcome, ylabel, scale, name, title, subtitle, caption):
    e = pd.read_csv(OUTPUT / "event_study.csv")
    s = pd.read_csv(OUTPUT / "event_study_summary.csv")
    e = e[(e.outcome == outcome) & e.balanced]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.975, top=0.8, bottom=0.2)
    specs = [(False, False, BLUE, "No controls"), (True, False, ORANGE, "County child population control")]
    for i, (control, trend, colour, label) in enumerate(specs):
        p = e[(e.control == control) & (e.trend == trend)]
        x = p.year + (i - 0.5) * 0.18
        ax.errorbar(x, scale * p.coef, yerr=scale * 1.96 * p.se, fmt="o", color=colour, ms=4, lw=1.2, capsize=0, label=label)
    slope = s[(s.outcome == outcome) & s.balanced & s.trend & ~s.control].pretrend_slope.iloc[0]
    years = np.arange(1990, 2006)
    ax.plot(years, scale * slope * (years - REF), color=BLUE, lw=1, ls="--", label="No controls: 1990-94 trend carried on")
    ax.axhline(0, color=MUTED, lw=0.8)
    law(ax)
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=9, loc="lower left" if scale * slope < 0 else "upper left")
    save(fig, name, title, subtitle, caption)


def main():
    FIGURES.mkdir(exist_ok=True)
    levels()
    effects("white_share", "Arizona minus New Mexico, percentage points", 100, "white_share_effects.png",
            "Arizona's relative decline began before charters",
            "Change in white non-Hispanic share of traditional public schools, Arizona relative to New Mexico, from 1994-95",
            "School and year fixed effects, schools present every year from 1990-91 to 2005-06. Bars are 95% intervals "
            "with standard errors clustered by district. " + SOURCE)
    effects("ptr", "Arizona minus New Mexico, pupils per teacher", 1, "ptr_effects.png",
            "Pupil-teacher ratios rose in Arizona relative to New Mexico",
            "Change in pupils per full-time teacher in traditional public schools, Arizona relative to New Mexico, from 1994-95",
            "School and year fixed effects, schools present every year from 1990-91 to 2005-06. Bars are 95% intervals "
            "with standard errors clustered by district. " + SOURCE)


if __name__ == "__main__":
    main()
