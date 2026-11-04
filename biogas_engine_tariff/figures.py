"""Draw the charts: the cycle optimum, break-even tariffs, the tornado and the upgrading-cost threshold."""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

import parameters as p

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
COLOUR = {"gas": BLUE, "biogas": ORANGE}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "legend.frameon": False})
SOURCE = ("Source: an unpublished 2018 feasibility study for a site in Tabriz, Iran, and its two business-plan "
          "workbooks; 2018 rials.")
COMMA = FuncFormatter(lambda x, _: f"{x:,.0f}")


def save(fig, name, title, subtitle, caption):
    fig.text(0.015, 0.985, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.925, subtitle, color=MUTED, va="top")
    fig.text(0.015, 0.012, "\n".join(textwrap.wrap(caption, 140)), color=MUTED, fontsize=9, va="bottom")
    fig.savefig(p.FIGURES / name, dpi=200, facecolor="white")
    plt.close(fig)


def cycle():
    c = pd.read_csv(p.OUTPUT / "cycle.csv")
    o = pd.read_csv(p.OUTPUT / "cycle_optimum.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.4), gridspec_kw={"width_ratios": [1.4, 1]})
    fig.subplots_adjust(left=0.07, right=0.98, top=0.8, bottom=0.2, wspace=0.25)
    for (cp, colour, label) in ((p.CP_CODE, BLUE, "c_p = 1.04 (equation listing)"),
                                (p.CP_TEXT, ORANGE, "c_p = 1.004 (text)")):
        s, r = c[c.cp == cp], o[o.cp == cp].iloc[0]
        a.plot(s.cr, s.w_net, color=colour, lw=2, label=label)
        a.plot(r.cr_opt, r.w_net_max, "o", color=colour, ms=7)
        a.annotate(f"CR {r.cr_opt:.2f}", (r.cr_opt, r.w_net_max), xytext=(0, 8), textcoords="offset points",
                   ha="center", color=colour, fontsize=10)
        b.plot(s.cr, 100 * s.eta, color=colour, lw=2)
        b.plot(r.cr_opt, 100 * r.eta, "o", color=colour, ms=7)
    a.axhline(p.REPORTED_WNET, color=MUTED, lw=0.8, ls=":")
    a.set_ylim(480, 550)
    a.set_xlabel("Compression ratio")
    a.set_ylabel("Net work, kJ per kg of air")
    a.legend(loc="lower center")
    b.set_xlabel("Compression ratio")
    b.set_ylabel("Thermal efficiency, %")
    b.set_title("Efficiency keeps rising; dots mark the work optimum", fontsize=10, color=MUTED, loc="left")
    save(fig, "cycle.png", "Net work peaks at 538.3 kJ/kg; c_p moves where, not how high",
         "Air-standard Otto cycle with peak temperature fixed at 2000 K, T1 = 300 K, c_v = 0.717 kJ/(kg K)",
         "With T3 fixed, a higher compression ratio raises efficiency but leaves less room to add heat, so net work "
         "per kg of air has a maximum, c_v (sqrt(T3) - sqrt(T1))^2. The report prints c_p = 1.004 in its text and "
         "1.04 in its equation listing; only 1.04 puts the maximum at its CR = 8.211. " + SOURCE)


def breakeven():
    e = pd.read_csv(p.OUTPUT / "economics.csv")
    e = e[e.tariff == e.fuel.map(p.TARIFF)]
    cases = ["workbook as printed", "fuel annualised", "fuel annualised, EPA engine efficiency"]
    labels = ["workbook as printed", "full year of fuel", "full year, 38% engine"]
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(left=0.25, right=0.95, top=0.8, bottom=0.2)
    y, ticks = 0, []
    for fuel in ("biogas", "gas"):
        for case, label in zip(cases, labels):
            r = e[(e.fuel == fuel) & (e.case == case)].iloc[0]
            ax.plot(r.breakeven, y, "o", color=COLOUR[fuel], ms=8)
            ax.annotate(f"{r.breakeven:,.0f} ({r.breakeven_us_cents:.1f} US cents)", (r.breakeven, y),
                        xytext=(9, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
            ticks.append((y, f"{fuel.capitalize()}: {label}"))
            y -= 1
        ax.vlines(p.TARIFF[fuel], y + 0.6, y + 3.4, color=COLOUR[fuel], lw=1.5, ls="--")
        ax.text(p.TARIFF[fuel], y + 3.5, f"{fuel} tariff {p.TARIFF[fuel]:,.0f}", color=COLOUR[fuel], fontsize=9,
                ha="center", va="bottom")
        y -= 0.6
    ax.set_yticks([t for t, _ in ticks], [l for _, l in ticks])
    ax.set_ylim(y + 0.3, 0.9)
    ax.set_xscale("log")
    ax.set_xlim(600, 400_000)
    ax.xaxis.set_major_formatter(COMMA)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Break-even tariff, rials per kWh (log scale)")
    save(fig, "breakeven.png", "Counting a full year of fuel puts biogas far above its tariff",
         f"Guaranteed price at which the plant's net present value is zero, {p.RATE:.0%} discount rate, {p.LIFE}-year life",
         "The workbooks enter one hour of fuel cost as the year's cost. For gas this hardly matters; for biogas the "
         "hourly upgrading cost is large. The 38% efficient engine is the US EPA's 633 kW gas engine on an LHV basis. "
         f"US cents at {p.RIALS_PER_USD:,} rials per dollar, the official rate from April 2018. " + SOURCE)


NAMES = {"price_gas": "Gas price, rials/m3", "price_biogas": "Biogas upgrading cost, rials/m3",
         "tariff_gas": "Gas tariff, rials/kWh", "tariff_biogas": "Biogas tariff, rials/kWh",
         "eta": "Engine efficiency", "capex": "Capital cost (x workbook)", "rate": "Discount rate", "life": "Life, years"}


def fmt(name, v):
    if name in ("eta", "rate"):
        return f"{v:.0%}" if name == "rate" else f"{v:.1%}"
    return f"{v:g}" if name in ("capex", "life") else f"{v:,.0f}"


def tornado():
    t = pd.read_csv(p.OUTPUT / "tornado.csv")
    t["swing"] = (t.margin_high - t.margin_low).abs()
    t = t.sort_values("swing")
    base = t.base.iloc[0]
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.subplots_adjust(left=0.3, right=0.97, top=0.8, bottom=0.22)
    for i, r in enumerate(t.itertuples()):
        ax.barh(i, r.margin_low - base, left=base, color=AQUA, height=0.6)
        ax.barh(i, r.margin_high - base, left=base, color=ORANGE, height=0.6)
    ax.set_yticks(range(len(t)), [f"{NAMES[r.input]}\n{fmt(r.input, r.low)} to {fmt(r.input, r.high)}"
                                  for r in t.itertuples()], fontsize=9)
    ax.set_ylim(-0.6, len(t) + 0.3)
    ax.axvline(base, color=INK, lw=1)
    ax.axvline(0, color=MUTED, lw=1, ls="--")
    ax.text(-500, len(t) + 0.1, "biogas ranks first\nto the right of 0", color=MUTED, fontsize=9, ha="right", va="top")
    ax.text(base, len(t) + 0.1, f" workbook values: {base:,.0f}", color=INK, fontsize=9, va="top")
    ax.legend(handles=[Patch(color=AQUA, label="Input at the low end"), Patch(color=ORANGE, label="Input at the high end")],
              loc="lower left", fontsize=9)
    ax.set_xlim(-85_000, 5_000)
    ax.xaxis.set_major_formatter(COMMA)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Biogas's tariff headroom minus gas's, rials per kWh")
    save(fig, "tornado.png", "Only the biogas fuel bill moves the ranking, and not far enough",
         "Each input moved alone over its range, the others at the workbook values with a full year of fuel",
         "Headroom is the guaranteed tariff minus the break-even tariff. The plants make the same output over the same "
         "life, so a positive difference means biogas has the higher net present value. Ranges are my choice; "
         "efficiency runs from the US EPA's 633 kW gas engine (LHV) to the air-standard cycle. " + SOURCE)


def upgrading():
    u = pd.read_csv(p.OUTPUT / "upgrading_cost.csv")
    th = pd.read_csv(p.OUTPUT / "thresholds.csv").set_index("item").value
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 7.4), sharex=True, gridspec_kw={"height_ratios": [1.3, 1]})
    fig.subplots_adjust(left=0.12, right=0.97, top=0.86, bottom=0.2, hspace=0.12)
    a.plot(u.price_biogas, u.breakeven_biogas, color=ORANGE, lw=2, label="Air-standard cycle (61% efficient)")
    a.plot(u.price_biogas, u.breakeven_biogas_epa_engine, color=ORANGE, lw=1.5, ls="--",
           label="38% efficient engine")
    first = th["biogas break-even below which biogas ranks first"]
    a.axhline(p.TARIFF["biogas"], color=MUTED, lw=1)
    a.text(600, p.TARIFF["biogas"] * 0.93, f"biogas tariff {p.TARIFF['biogas']:,.0f}: breaks even below",
           color=MUTED, fontsize=9, va="top")
    a.axhline(first, color=BLUE, lw=1)
    a.text(600, first * 1.07, f"{first:,.0f}: ranks ahead of gas (gas paid {p.TARIFF['gas']:,.0f}) below",
           color=BLUE, fontsize=9, va="bottom")
    a.set_yscale("log")
    a.set_ylim(2000, 250_000)
    a.yaxis.set_major_formatter(COMMA)
    a.set_ylabel("Biogas break-even,\nrials per kWh")
    a.legend(loc="upper left", fontsize=9)
    b.plot(u.price_biogas, 100 * u.share_biogas_first, color=AQUA, lw=2)
    b.set_ylabel("Draws with biogas\nranked first, %")
    b.set_ylim(-3, 103)
    lo, hi = p.RANGES["price_biogas"]
    bench = pd.read_csv(p.OUTPUT / "benchmark.csv").set_index("case").rials_per_m3
    published = [("standard plants, low", "standard plants, high", AQUA, "published,\nlarge plants"),
                 ("plants of this size, low", "plants of this size, high", YELLOW, "published,\nthis size")]
    for ax in (a, b):
        ax.axvspan(lo, hi, color=GRID, alpha=0.7, lw=0)
        ax.axvline(p.FUEL_PRICE["biogas"], color=INK, lw=1, ls=":")
        for low, high, colour, _ in published:
            ax.axvspan(bench[low], bench[high], color=colour, alpha=0.18, lw=0)
    for low, high, colour, label in published:
        b.text((bench[low] * bench[high]) ** 0.5, 50, label, color=INK, fontsize=8, ha="center", va="center")
    b.text(p.FUEL_PRICE["biogas"], 50, "study\n200,000 ", color=INK, fontsize=9, ha="right", va="center")
    b.set_xscale("log")
    b.set_xlim(500, 400_000)
    b.xaxis.set_major_formatter(COMMA)
    b.set_xlabel("Biogas upgrading cost, rials per m3 (log scale)")
    save(fig, "upgrading_cost.png", "At published upgrading costs biogas does not break even at its tariff",
         f"Break-even tariff for biogas, and how often it ranks ahead of gas in {p.MC_DRAWS:,} random draws",
         "Draws vary the gas price, both tariffs and capital cost by +/-50% and engine efficiency between 38% and 61%, "
         f"uniformly and independently, at each upgrading cost. {p.RATE:.0%} discount rate, {p.LIFE}-year life. Grey: "
         "+/-50% around the study's upgrading cost. Coloured: published upgrading costs for large plants (1-2 euro cents "
         "per kWh) and for plants near this size (2.3-4.6), from DBFZ via IEA Bioenergy, at 2018 exchange rates. " + SOURCE)


def main():
    p.FIGURES.mkdir(exist_ok=True)
    cycle()
    breakeven()
    tornado()
    upgrading()


if __name__ == "__main__":
    main()
