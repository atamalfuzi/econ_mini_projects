"""Draw the charts: the historical premium, the Mehra-Prescott economy, the Hansen-Jagannathan bound and disasters."""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, MultipleLocator, PercentFormatter

from data import FIGURES, OUTPUT
from estimate import BARRO, FIXED_BETA

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False})
SOURCE = ("Source: Robert Shiller, annual data for Chapter 26 of Market Volatility, updated (chapt26.xlsx). Real returns "
          "run January to January; the short rate is prime commercial paper.")
PCT = PercentFormatter(1.0, decimals=0)


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 140)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def panel_title(ax, text):
    ax.set_title(text, fontsize=11, color=MUTED, loc="left")


def history():
    a = pd.read_csv(OUTPUT / "annual.csv")
    m = pd.read_csv(OUTPUT / "moments.csv").set_index("sample").loc["1871-2011"]
    fig, (l, r) = plt.subplots(1, 2, figsize=(11, 5.4))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    years = np.r_[a.year.iloc[0], a.year + 1]
    l.plot(years, np.r_[1, a.stock_wealth], color=BLUE, lw=2, label="Stocks (S&P Composite)")
    l.plot(years, np.r_[1, a.bill_wealth], color=ORANGE, lw=2, label="Short-term commercial paper")
    l.set_yscale("log")
    l.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}" if v >= 1 else f"${v:.1f}"))
    l.set_ylabel("Real value of $1 invested in January 1871")
    l.legend(loc="upper left")
    panel_title(l, "Real wealth, log scale")
    r.plot(a.year, a.premium_30y, color=BLUE, lw=2, label="Average over the previous 30 years")
    r.axhline(m.premium, color=MUTED, lw=1, ls="--", label=f"1871-2011 average: {m.premium:.1%}")
    r.axhline(0, color=MUTED, lw=0.8)
    r.yaxis.set_major_formatter(PCT)
    r.set_ylabel("Stock return minus short rate")
    r.set_ylim(top=0.165)
    r.legend(loc="upper left")
    panel_title(r, "Equity premium, 30-year averages")
    save(fig, "history.png", f"Stocks have beaten short-term paper by {100 * m.premium:.1f} points a year since 1871",
         f"Real returns {a.year.min()}-{a.year.max()}: stocks {m.stock_mean:.1%} a year, commercial paper "
         f"{m.bill_mean:.1%} (arithmetic means)", SOURCE)


def mehra_prescott():
    g = pd.read_csv(OUTPUT / "mp_grid.csv")
    s = pd.read_csv(OUTPUT / "mp_summary.csv").set_index("calibration").loc["1889-2007"]
    g = g[(g.calibration == "1889-2007") & (g.gamma <= 40)]
    fig, (l, r) = plt.subplots(1, 2, figsize=(11, 5.4))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    for ax in (l, r):
        ax.axvspan(0, 10, color=GRID, alpha=0.6, lw=0)
        ax.text(0.5, 0.97, "risk aversion up to 10", transform=ax.get_xaxis_transform(), color=MUTED, fontsize=9, va="top")
        ax.axvline(s.gamma_needed_beta099, color=MUTED, lw=1, ls=":")
        ax.yaxis.set_major_formatter(PCT)
        ax.set_xlabel("Relative risk aversion, γ")
        ax.set_xlim(0, 40)
    for beta, colour, ls in (("0.99", BLUE, "-"), ("0.96", ORANGE, "--")):
        b = g[g.beta_rule == beta]
        l.plot(b.gamma, b.premium, color=colour, lw=2, ls=ls, label=f"Model, β = {beta}")
        r.plot(b.gamma, b.riskfree, color=colour, lw=2, ls=ls, label=f"Model, β = {beta}")
    l.axhline(s.target_premium, color=INK, lw=1.2, label=f"Data: {s.target_premium:.1%}")
    r.axhline(s.target_riskfree, color=INK, lw=1.2, label=f"Data: {s.target_riskfree:.1%}")
    l.annotate(f"γ = {s.gamma_needed_beta099:.0f}", (s.gamma_needed_beta099, s.target_premium), xytext=(8, -18),
               textcoords="offset points", color=INK, fontsize=10)
    r.annotate(f"{s.riskfree_at_gamma_needed:.0%} at γ = {s.gamma_needed_beta099:.0f}",
               (s.gamma_needed_beta099, s.riskfree_at_gamma_needed), xytext=(-8, -50), textcoords="offset points",
               ha="right", color=INK, fontsize=10, arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    r.set_ylim(0, 0.33)
    l.legend(loc="upper left", bbox_to_anchor=(0, 0.9))
    r.legend(loc="upper right")
    panel_title(l, "Equity premium")
    panel_title(r, "Risk-free rate")
    save(fig, "mehra_prescott.png", f"Matching the premium takes risk aversion of about {s.gamma_needed_beta099:.0f}",
         "Two-state Mehra-Prescott economy calibrated to 1889-2007 consumption growth, against 1889-2007 averages",
         f"Consumption growth: mean {s.growth_mean:.2%}, s.d. {s.growth_sd:.2%}, autocorrelation {s.growth_autocorr:.2f}. "
         "Equity is a claim to consumption; utility is power utility. Returns are means over the chain's stationary "
         "distribution. " + SOURCE)


def hj_bound():
    c = pd.read_csv(OUTPUT / "hj_curve.csv")
    h = pd.read_csv(OUTPUT / "hansen_jagannathan.csv").set_index("sample")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.975, top=0.8, bottom=0.2)
    for sample, colour in (("1889-2007", BLUE), ("1889-1949", ORANGE), ("1950-2007", AQUA)):
        k, s = c[c["sample"] == sample], h.loc[sample]
        ax.plot(k.gamma, k.ratio, color=colour, lw=2, label=f"{sample}: σ(m)/E(m)")
        ax.axhline(s.sharpe, color=colour, lw=1, ls="--")
        ax.plot(s.gamma_bound, s.sharpe, "o", color=colour, ms=6)
        # 1950-2007's own curve runs just above its dashed line on the right, so its label sits left of the crossing
        x = s.gamma_bound - 0.5 if sample == "1950-2007" else 30
        ax.annotate(f"{sample} Sharpe ratio {s.sharpe:.2f}: γ = {s.gamma_bound:.0f}", (x, s.sharpe),
                    xytext=(-2, 4), textcoords="offset points", ha="right", color=colour, fontsize=9)
    ax.set_xlabel("Relative risk aversion, γ")
    ax.set_ylabel("Volatility of the discount factor, σ(m)/E(m)")
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 0.8)
    ax.legend(loc="upper left")
    full = h.loc["1889-2007"]
    save(fig, "hj_bound.png", f"The Sharpe ratio alone needs risk aversion of about {full.gamma_bound:.0f}",
         r"Hansen-Jagannathan bound: $m = \beta\,(C_{t+1}/C_t)^{-\gamma}$ must be at least as volatile as the "
         "Sharpe ratio of stocks",
         "Each line uses the sample's own consumption growth; dashed lines are the same years' Sharpe ratio of stock "
         "returns over the short rate. Consumption is real per capita spending; growth is next year over this year. "
         + SOURCE)


def disasters():
    g = pd.read_csv(OUTPUT / "disaster_grid.csv")
    m = pd.read_csv(OUTPUT / "disaster_match.csv")
    s = pd.read_csv(OUTPUT / "disaster_summary.csv").set_index("gamma")
    target, rf = s.target_premium.iloc[0], s.target_riskfree.iloc[0]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13, 5.6))
    fig.subplots_adjust(left=0.06, right=0.985, top=0.8, bottom=0.22, wspace=0.3)
    colours = {3: ORANGE, 4: BLUE, 5: AQUA}
    for gamma, colour in colours.items():
        k = g[(g.gamma == gamma) & np.isclose(g.prob, BARRO[0])]
        a.plot(k["size"], k.premium, color=colour, lw=2, label=f"γ = {gamma}")
        b.plot(k["size"], k.riskfree_fixed_beta, color=colour, lw=2, label=f"γ = {gamma}")
        j = m[m.gamma == gamma]
        c.plot(j.prob, j.size_needed, color=colour, lw=2, label=f"γ = {gamma}")
    a.axhline(target, color=INK, lw=1.2, label=f"Data: {target:.1%}")
    b.axhline(rf, color=INK, lw=1.2, label=f"Data: {rf:.1%}")
    c.plot(*BARRO, "s", color=INK, ms=6)
    c.annotate("Barro (2006):\n1.7% a year,\naverage size 29%", BARRO, xytext=(8, -36), textcoords="offset points",
               color=INK, fontsize=9)
    a.set_ylim(0, 0.12)
    b.set_ylim(-0.08, 0.14)
    b.yaxis.set_major_locator(MultipleLocator(0.04))
    for ax in (a, b):
        ax.set_xlabel("Fall in consumption in a disaster")
        ax.xaxis.set_major_formatter(PCT)
        ax.yaxis.set_major_formatter(PCT)
        ax.set_xlim(0, 0.6)
    a.legend(loc="upper left", fontsize=9)
    b.legend(loc="lower left", fontsize=9)
    c.set_xlabel("Probability of a disaster each year")
    c.set_ylabel("Fall in consumption needed")
    c.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    c.yaxis.set_major_formatter(PCT)
    c.set_xlim(0, 0.05)
    c.set_ylim(0, 0.8)
    c.legend(loc="upper right", fontsize=9)
    panel_title(a, f"Premium, disaster probability {BARRO[0]:.1%}")
    panel_title(b, f"Risk-free rate, β = {FIXED_BETA}")
    panel_title(c, "Combinations that match the premium")
    save(fig, "disasters.png", "Rare, large disasters deliver the premium at moderate risk aversion",
         "Mehra-Prescott economy (1889-2007 calibration) plus a disaster state that can arrive in any year",
         f"Left and right panels set β so the mean risk-free rate is {rf:.1%}; along every matching combination that β "
         f"is between {m.beta.min():.2f} and {m.beta.max():.2f}. The middle panel fixes β at {FIXED_BETA} instead. "
         "Barro's disasters are falls in GDP per person, which vary in size. " + SOURCE)


def main():
    FIGURES.mkdir(exist_ok=True)
    history()
    mehra_prescott()
    hj_bound()
    disasters()


if __name__ == "__main__":
    main()
