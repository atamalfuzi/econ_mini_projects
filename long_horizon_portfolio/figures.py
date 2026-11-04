"""Draw the charts: the dividend yield and returns, the optimal shares by horizon, the share against the
dividend yield under each slope, and the out-of-sample record."""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import data
from data import FIGURES, OUTPUT
from estimate import sample

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False})
SOURCE = ("Source: Robert Shiller, annual US stock market data (chapt26.xlsx): S&P Composite price in January, "
          "dividends over the year, one-year interest rate.")
SCENARIOS = {"ols": (BLUE, "Full-sample slope"), "bias_corrected": (ORANGE, "Bias-corrected slope"),
             "half_slope": (AQUA, "Half the full-sample slope"), "no_predictability": (MUTED, "No predictability")}


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 140)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def predictability():
    d = data.load()
    s = sample(d)
    f = pd.read_csv(OUTPUT / "predictive.csv").iloc[0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.4), gridspec_kw={"width_ratios": [1.6, 1]})
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    y = d.dropna(subset=["dividend_yield"])
    a.plot(y.year, 100 * y.dividend_yield, color=BLUE, lw=1.6)
    a.axhline(100 * np.exp(f.mean_log_dp), color=MUTED, lw=1, ls="--")
    a.text(y.year.iloc[-1], 100 * np.exp(f.mean_log_dp) + 0.15, "average", color=MUTED, fontsize=9, ha="right",
           va="bottom")
    a.plot(y.year.iloc[-1], 100 * y.dividend_yield.iloc[-1], "o", color=ORANGE, ms=5)
    a.text(y.year.iloc[-1], 100 * y.dividend_yield.iloc[-1] - 0.35, f"{int(y.year.iloc[-1])}", color=ORANGE,
           fontsize=9, ha="center", va="top")
    a.set_ylabel("Dividend yield, %")
    b.scatter(s.log_dp, 100 * s.log_excess, s=10, color=BLUE, alpha=0.5, lw=0)
    z = np.linspace(s.log_dp.min(), s.log_dp.max(), 2)
    mean_r = 100 * f.mean_excess
    for beta, colour, label in ((f.beta, BLUE, "full-sample slope"), (f.beta_corrected, ORANGE, "bias-corrected")):
        b.plot(z, mean_r + 100 * beta * (z - f.mean_log_dp), color=colour, lw=2, label=label)
    ticks = [0.01, 0.02, 0.04, 0.08]
    b.set_xticks(np.log(ticks), [f"{100 * t:.0f}%" for t in ticks])
    b.set_xlabel("Starting dividend yield (log scale)")
    b.set_ylabel("Log excess return over the year, %")
    b.legend(fontsize=9, loc="upper left")
    save(fig, "predictability.png", "A high dividend yield has been followed by slightly higher returns",
         f"Dividend yield, {int(y.year.iloc[0])}-{int(y.year.iloc[-1])}, and the next year's stock return over "
         f"the one-year rate, {int(f.first_year)}-{int(f.last_year)}",
         SOURCE + " The dividend yield is the previous year's dividends over the January price.")


def allocation():
    a = pd.read_csv(OUTPUT / "allocation.csv")
    a = a[a.scenario == "ols"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 5.4))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.78, bottom=0.22, wspace=0.28)
    for ax, g in zip(axes, sorted(a.gamma.unique())):
        for point, colour in (("average", BLUE), ("current", ORANGE)):
            p = a[(a.gamma == g) & (a.point == point)]
            label = "average yield" if point == "average" else f"{int(p.year.iloc[0])} yield"
            ax.fill_between(p.horizon, 100 * p.myopic, 100 * p.total, color=colour, alpha=0.15, lw=0)
            ax.plot(p.horizon, 100 * p.total, color=colour, lw=2, label=f"Total, {label}")
            ax.plot(p.horizon, 100 * p.myopic, color=colour, lw=1.2, ls="--", label=f"Myopic part, {label}")
        ax.set_ylim(0, None)
        ax.set_xlim(0, 30)
        ax.set_title(f"Risk aversion {g}", fontsize=11, color=MUTED, loc="left")
        ax.set_xlabel("Years to the horizon")
    axes[0].set_ylabel("Share of wealth in stocks, %")
    axes[0].legend(fontsize=8.5, loc="lower left")
    save(fig, "allocation.png", "Hedging demand adds to the stock share at long horizons",
         "Optimal share of wealth in stocks (Kim and Omberg 1996), full-sample estimates; shading is the hedging part",
         "CRRA utility over wealth at the horizon, constant short rate, risk premium following an "
         "Ornstein-Uhlenbeck process calibrated to the annual regression of excess returns on the log dividend "
         "yield, 1872-2011. " + SOURCE)


def sensitivity():
    s = pd.read_csv(OUTPUT / "share_by_yield.csv")
    alloc = pd.read_csv(OUTPUT / "allocation.csv")
    g, h = int(s.gamma.iloc[0]), int(s.horizon.iloc[0])
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.4))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    for name, (colour, label) in SCENARIOS.items():
        p = s[s.scenario == name]
        a.plot(100 * p.dividend_yield, 100 * p.total, color=colour, lw=2, label=label)
        b.plot(100 * p.dividend_yield, 100 * p.hedging, color=colour, lw=2, label=label)
    for ax in (a, b):
        for point in ("average", "current"):
            dy = alloc[alloc.point == point].dividend_yield.iloc[0]
            ax.axvline(100 * dy, color=MUTED, lw=1, ls=":")
            ax.text(100 * dy, 1.0, " average" if point == "average" else f" {int(alloc[alloc.point == point].year.iloc[0])}",
                    transform=ax.get_xaxis_transform(), color=MUTED, fontsize=9, va="bottom")
        ax.set_xlabel("Dividend yield, %")
    a.set_ylabel("Share of wealth in stocks, %")
    b.set_ylabel("Hedging part, percentage points")
    a.legend(fontsize=9, loc="lower right")
    save(fig, "slope_sensitivity.png", "A weaker slope flattens the rule and shrinks the hedging part",
         f"Optimal share in stocks against the dividend yield, risk aversion {g}, {h} years to the horizon",
         "The bias-corrected slope applies Stambaugh's (1999) correction to the slope and Kendall's to the "
         "persistence of the dividend yield. The long-run premium is the same in every case. " + SOURCE)


def out_of_sample():
    o = pd.read_csv(OUTPUT / "oos_path.csv")
    f = pd.read_csv(OUTPUT / "predictive.csv").iloc[0]
    r2 = pd.read_csv(OUTPUT / "oos.csv").iloc[0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.4))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    a.plot(o.year, o.cum_sse_difference, color=BLUE, lw=2)
    a.axhline(0, color=MUTED, lw=0.8)
    a.set_ylabel("Cumulative difference in squared errors")
    a.set_title("Above zero: the dividend yield has forecast better", fontsize=10, color=MUTED, loc="left")
    b.plot(o.year, o.slope, color=BLUE, lw=2, label="Expanding window")
    b.axhline(f.beta, color=BLUE, lw=1, ls="--", label="Full sample")
    b.axhline(f.beta_corrected, color=ORANGE, lw=1, ls="--", label="Full sample, bias-corrected")
    b.axhline(0, color=MUTED, lw=0.8)
    b.set_ylabel("Slope on the log dividend yield")
    b.set_title("Slope estimated with data up to each year", fontsize=10, color=MUTED, loc="left")
    b.legend(fontsize=9, loc="lower right")
    save(fig, "out_of_sample.png", "Out of sample, the dividend yield has not beaten the historical mean",
         f"Expanding-window forecasts of the next year's excess return, {int(r2.first_forecast)}-{int(r2.last_forecast)}",
         f"Each year's forecast uses only earlier years, with at least 20 years of data, as in Goyal and Welch (2008). "
         f"Out-of-sample R² over {int(r2.first_forecast)}-{int(r2.last_forecast)}: {100 * r2.r2_oos:.1f}%. " + SOURCE)


def main():
    FIGURES.mkdir(exist_ok=True)
    predictability()
    allocation()
    sensitivity()
    out_of_sample()


if __name__ == "__main__":
    main()
