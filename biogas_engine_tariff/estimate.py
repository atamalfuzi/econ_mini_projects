"""Cycle optimum, fuel use, break-even tariffs, sensitivity and Monte Carlo. Writes output/*.csv."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq, minimize_scalar

import parameters as p
from model import ETA_CYCLE, cycle, fuel_use, irr, margin, optimum_cr, plant

ETA_EPA = p.RANGES["eta"][0]   # the EPA engine's efficiency on an LHV basis
SHARED = ("eta", "capex", "rate", "life")


def usd(rials, rate=p.RIALS_PER_USD):
    return rials / rate


def cycle_tables():
    cr = np.round(np.arange(4, 14.001, 0.05), 2)
    sweep, best = [], []
    for cp, source in ((p.CP_CODE, "equation listing, p. 41"), (p.CP_TEXT, "text, p. 39")):
        c = cycle(cr, cp)
        sweep.append(pd.DataFrame({"cp": cp, "cr": cr, "w_net": c["w_net"], "eta": c["eta"], "q_in": c["q_in"],
                                   "eta_closed_form": 1 - cr ** (1 - c["k"])}))
        r = optimum_cr(cp)
        numeric = minimize_scalar(lambda x: -cycle(x, cp)["w_net"], bounds=(2, 30), method="bounded",
                                  options={"xatol": 1e-9}).x
        o = cycle(r, cp)
        best.append({"cp": cp, "source": source, "k": o["k"], "cr_opt": r, "cr_opt_numeric": numeric,
                     "w_net_max": o["w_net"], "w_net_at_reported_cr": cycle(p.REPORTED_CR, cp)["w_net"],
                     "eta": o["eta"], "q_in": o["q_in"], "q_out": o["q_out"], "t2": o["t2"], "t4": o["t4"],
                     "gas_kg_per_kg_air": o["q_in"] / p.LHV["gas"], "biogas_kg_per_kg_air": o["q_in"] / p.LHV["biogas"]})
    return pd.concat(sweep), pd.DataFrame(best)


def fuel_table():
    rows = []
    for fuel in p.FUELS:
        for case, eta in (("air-standard cycle", ETA_CYCLE), ("EPA engine", ETA_EPA)):
            f = fuel_use(fuel, eta)
            cost = f["m3_per_kwh"] * p.FUEL_PRICE[fuel]
            rows.append({"fuel": fuel, "efficiency_case": case, "eta": eta, **f, "price_rials_per_m3": p.FUEL_PRICE[fuel],
                         "price_usd_per_m3": usd(p.FUEL_PRICE[fuel]),
                         "fuel_cost_rials_per_kwh": cost, "fuel_cost_us_cents_per_kwh": 100 * usd(cost),
                         "workbook_m3_per_h": p.WORKBOOK_FUEL_M3_H[fuel], "report_kg_per_s": p.REPORTED_FUEL_KG_S[fuel]})
    return pd.DataFrame(rows)


def workbook_check():
    rows = []
    for fuel in p.FUELS:
        tariff = p.TARIFF_GAS_WORKBOOK if fuel == "gas" else p.TARIFF["biogas"]
        printed, fixed = plant(fuel, tariff, annual_fuel=False), plant(fuel, tariff)
        for item, value in p.WORKBOOK[fuel].items():
            rows.append({"fuel": fuel, "tariff": tariff, "item": item, "workbook": value,
                         "model_as_printed": float(printed[item]), "model_fuel_annualised": float(fixed[item])})
    return pd.DataFrame(rows)


def economics():
    rows = []
    cases = [("workbook as printed", dict(annual_fuel=False)), ("fuel annualised", {}),
             ("fuel annualised, EPA engine efficiency", dict(eta=ETA_EPA))]
    for fuel in p.FUELS:
        tariffs = [p.TARIFF[fuel]] + ([p.TARIFF_GAS_WORKBOOK] if fuel == "gas" else [])
        for case, kw in cases:
            for tariff in tariffs:
                r = plant(fuel, tariff, **kw)
                rows.append({"fuel": fuel, "case": case, "tariff": tariff, "revenue": tariff * float(r["kwh"]),
                             "unit_cost": float(r["unit_cost"]),
                             "breakeven": float(r["breakeven"]), "npv": float(r["npv"]), "irr": irr(fuel, tariff=tariff, **kw),
                             "fixed": float(r["fixed"]), "fixed_usd": usd(float(r["fixed"])),
                             "fixed_usd_market": usd(float(r["fixed"]), p.RIALS_PER_USD_MARKET),
                             "investment": float(r["investment"]), "machinery": float(r["machinery"]),
                             "fuel_cost": float(r["fuel_cost"]), "cash_cost": float(r["cash_cost"]),
                             "breakeven_us_cents": 100 * usd(float(r["breakeven"])),
                             "breakeven_us_cents_market": 100 * usd(float(r["breakeven"]), p.RIALS_PER_USD_MARKET),
                             "tariff_us_cents": 100 * usd(tariff), "npv_usd": usd(float(r["npv"])),
                             "investment_usd": usd(float(r["investment"])),
                             "investment_usd_market": usd(float(r["investment"]), p.RIALS_PER_USD_MARKET),
                             "fuel_cost_usd": usd(float(r["fuel_cost"]))})
    return pd.DataFrame(rows)


def tornado():
    base = float(margin())
    rows = []
    for name, (lo, hi) in p.RANGES.items():
        hi = ETA_CYCLE if hi is None else hi
        rows.append({"input": name, "low": lo, "high": hi, "margin_low": float(margin(**{name: lo})),
                     "margin_high": float(margin(**{name: hi})), "base": base})
    return pd.DataFrame(rows)


def draws(n=p.MC_DRAWS, seed=p.MC_SEED):
    """Independent uniform draws over the ranges for fuel price, tariffs, efficiency and capital cost."""
    rng = np.random.default_rng(seed)
    d = {k: rng.uniform(*p.RANGES[k], n) for k in ("price_gas", "tariff_gas", "tariff_biogas", "capex")}
    d["eta"] = rng.uniform(ETA_EPA, ETA_CYCLE, n)
    d["price_biogas"] = rng.uniform(*p.RANGES["price_biogas"], n)
    return d


def upgrading_cost(d):
    """Biogas break-even and the share of draws in which biogas ranks first, at each upgrading cost."""
    grid = np.geomspace(500, 400_000, 121)
    other = {k: v for k, v in d.items() if k != "price_biogas"}
    rows = [{"price_biogas": u, "breakeven_biogas": float(plant("biogas", price=u)["breakeven"]),
             "breakeven_biogas_epa_engine": float(plant("biogas", price=u, eta=ETA_EPA)["breakeven"]),
             "margin_base": float(margin(price_biogas=u)),
             "share_biogas_first": float((margin(price_biogas=u, **other) > 0).mean())} for u in grid]
    return pd.DataFrame(rows)


def crossing(df, share):
    """Upgrading cost at which the Monte Carlo share falls to `share` (log-linear interpolation)."""
    s = df.share_biogas_first.to_numpy()[::-1]
    return float(np.exp(np.interp(share, s, np.log(df.price_biogas.to_numpy()[::-1]))))


def thresholds(d, up):
    gas = plant("gas")
    bio_even = lambda eta: brentq(lambda u: float(plant("biogas", price=u, eta=eta)["npv"]), 0, 1e6)
    rank_even = lambda eta: brentq(lambda u: float(margin(price_biogas=u, eta=eta)), 0, 1e6)
    rows = [
        ("ranking margin, workbook as printed", float(margin(annual_fuel=False)), "rials/kWh"),
        ("ranking margin, fuel annualised", float(margin()), "rials/kWh"),
        ("biogas break-even below which biogas ranks first", p.TARIFF["biogas"] - p.TARIFF["gas"]
         + float(gas["breakeven"]), "rials/kWh"),
        ("upgrading cost at which biogas breaks even at its tariff", bio_even(ETA_CYCLE), "rials/m3"),
        ("same, EPA engine efficiency", bio_even(ETA_EPA), "rials/m3"),
        ("upgrading cost below which biogas ranks first at the two tariffs", rank_even(ETA_CYCLE), "rials/m3"),
        ("same, EPA engine efficiency", rank_even(ETA_EPA), "rials/m3"),
        ("biogas break-even with free upgrading", float(plant("biogas", price=0.0)["breakeven"]), "rials/kWh"),
        ("Monte Carlo: share with biogas first, upgrading cost within +/-50% of the workbook",
         float((margin(**d) > 0).mean()), "share"),
        ("Monte Carlo: upgrading cost at which biogas ranks first in 95% of draws", crossing(up, 0.95), "rials/m3"),
        ("Monte Carlo: upgrading cost at which biogas ranks first in 50% of draws", crossing(up, 0.5), "rials/m3"),
        ("Monte Carlo: upgrading cost at which biogas ranks first in 5% of draws", crossing(up, 0.05), "rials/m3"),
        ("ranking threshold as a share of the workbook's upgrading cost",
         rank_even(ETA_CYCLE) / p.FUEL_PRICE["biogas"], "share"),
        ("workbook upgrading cost relative to the gas price", p.FUEL_PRICE["biogas"] / p.FUEL_PRICE["gas"], "ratio"),
        ("biogas volume per kWh relative to gas",
         fuel_use("biogas")["m3_per_kwh"] / fuel_use("gas")["m3_per_kwh"], "ratio"),
        ("gas fuel cost as a share of gas cash costs", float(gas["fuel_cost"] / gas["cash_cost"]), "share"),
        ("gas cash costs per kWh", float(gas["cash_cost"] / gas["kwh"]), "rials/kWh"),
        ("electricity and land rent per kWh", p.UTILITY_BILLS / float(gas["kwh"]), "rials/kWh"),
        ("workbook machinery cost per kW, gas", float(gas["machinery"]) / p.POWER_KW / p.RIALS_PER_USD, "US$/kW"),
        ("EPA installed cost per kW, 633 kW unit (2013)", p.EPA_COST_USD_PER_KW, "US$/kW"),
        ("EPA engine efficiency, LHV basis", ETA_EPA, "share"),
        ("discount rate", p.RATE, "share"),
        ("life", p.LIFE, "years"),
    ]
    out = pd.DataFrame(rows, columns=["item", "value", "unit"])
    out["us_dollars"] = np.where(out.unit.str.startswith("rials"), out.value / p.RIALS_PER_USD, np.nan)
    return out


def rials_per_m3(ct_per_kwh, rials_per_usd=p.RIALS_PER_USD):
    """A cost in euro cents per kWh (gross calorific value) as rials per m3 of the study's biogas. The gas carries the
    report's 21,000 kJ/kg at 1.2 kg/m3 (net), raised to a gross value with methane's ratio of 55.5 to 50 MJ/kg."""
    kwh_gross_per_m3 = p.LHV["biogas"] * p.DENSITY["biogas"] * (p.METHANE_HHV / p.LHV["gas"]) / 3600
    return ct_per_kwh / 100 * kwh_gross_per_m3 * p.USD_PER_EUR * rials_per_usd


def benchmark():
    """Biogas at published upgrading costs, against the study's 200,000 rials per m3."""
    cases = [("standard plants, low", p.UPGRADE_CT_STANDARD[0]), ("standard plants, high", p.UPGRADE_CT_STANDARD[1]),
             ("plants of this size, low", p.UPGRADE_CT_SMALL[0]), ("plants of this size, high", p.UPGRADE_CT_SMALL[1]),
             ("study's figure", p.FUEL_PRICE["biogas"] / rials_per_m3(1.0))]
    rows = []
    for label, ct in cases:
        u = rials_per_m3(ct)
        rows.append({"case": label, "ct_per_kwh": ct, "rials_per_m3": u, "rials_per_m3_market_rate": rials_per_m3(ct, p.RIALS_PER_USD_MARKET),
                     "breakeven_biogas": float(plant("biogas", price=u)["breakeven"]),
                     "breaks_even_at_tariff": bool(plant("biogas", price=u)["breakeven"] <= p.TARIFF["biogas"]),
                     "ranking_margin": float(margin(price_biogas=u)), "biogas_ranks_first": bool(margin(price_biogas=u) > 0)})
    return pd.DataFrame(rows)


def main():
    p.OUTPUT.mkdir(exist_ok=True)
    benchmark().to_csv(p.OUTPUT / "benchmark.csv", index=False)
    sweep, best = cycle_tables()
    sweep.to_csv(p.OUTPUT / "cycle.csv", index=False)
    best.to_csv(p.OUTPUT / "cycle_optimum.csv", index=False)
    fuel_table().to_csv(p.OUTPUT / "fuel.csv", index=False)
    workbook_check().to_csv(p.OUTPUT / "workbook_check.csv", index=False)
    economics().to_csv(p.OUTPUT / "economics.csv", index=False)
    tornado().to_csv(p.OUTPUT / "tornado.csv", index=False)
    d = draws()
    up = upgrading_cost(d)
    up.to_csv(p.OUTPUT / "upgrading_cost.csv", index=False)
    thresholds(d, up).to_csv(p.OUTPUT / "thresholds.csv", index=False)


if __name__ == "__main__":
    main()
