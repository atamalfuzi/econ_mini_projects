"""Air-standard cycle, fuel use and the workbooks' cost build-up turned into a discounted cash flow."""
import numpy as np
from scipy.optimize import brentq

import parameters as p


def cycle(cr, cp=p.CP_CODE, cv=p.CV, t1=p.T1, t3=p.T3):
    """Air-standard Otto cycle with a fixed peak temperature T3, per kg of air (kJ/kg). Works on arrays."""
    k = cp / cv
    t2 = t1 * cr ** (k - 1)
    t4 = t3 / cr ** (k - 1)
    q_in, q_out = cv * (t3 - t2), cv * (t4 - t1)
    return {"k": k, "t2": t2, "t4": t4, "q_in": q_in, "q_out": q_out, "w_net": q_in - q_out,
            "eta": (q_in - q_out) / q_in}


def optimum_cr(cp=p.CP_CODE, cv=p.CV, t1=p.T1, t3=p.T3):
    """Compression ratio that maximises net work with T3 fixed. Setting dw/dr = 0 gives T2 = T4 = sqrt(T1 T3),
    so r* = (T3/T1)^(1/(2(k-1))) and w* = c_v (sqrt(T3) - sqrt(T1))^2, which does not depend on k."""
    return (t3 / t1) ** (1 / (2 * (cp / cv - 1)))


ETA_CYCLE = cycle(optimum_cr())["eta"]   # 1 - sqrt(T1/T3); the same for either c_p


def fuel_use(fuel, eta=ETA_CYCLE):
    """Fuel per kWh of electricity. At the cycle's own efficiency this is the report's q_in / LHV per kg of air."""
    kg = 3600 / (eta * p.LHV[fuel])
    return {"kg_per_kwh": kg, "m3_per_kwh": kg / p.DENSITY[fuel], "mj_per_kwh": 3.6 / eta,
            "kg_per_s": kg * p.POWER_KW / 3600, "m3_per_h": kg / p.DENSITY[fuel] * p.POWER_KW}


def annuity(rate, life):
    rate = np.asarray(rate, dtype=float)
    safe = np.where(rate == 0, 1.0, rate)
    return np.where(rate == 0, life, (1 - (1 + safe) ** -life) / safe)


def plant(fuel, tariff=None, price=None, eta=ETA_CYCLE, capex=1.0, rate=p.RATE, life=p.LIFE, annual_fuel=True):
    """The workbook's cost build-up for one fuel, then a cash flow: the whole investment in year 0, revenue less
    cash costs in years 1 to `life`, and land and working capital recovered at the end. No tax, as in the workbooks.
    annual_fuel=False reproduces the workbooks, which enter one hour of fuel (E145 x G145) as the year's cost.
    Every argument except `fuel` and `annual_fuel` may be a numpy array."""
    tariff = p.TARIFF[fuel] if tariff is None else tariff
    price = p.FUEL_PRICE[fuel] if price is None else price
    kwh = p.POWER_KW * p.HOURS
    fuel_cost = fuel_use(fuel, eta)["m3_per_h"] * price * (p.HOURS if annual_fuel else 1)

    engine = p.ENGINE_USD_PER_KW * p.POWER_KW * p.RIALS_PER_USD
    machinery = capex * (engine * (1 + p.TRANSFORMER_SHARE + p.INSTALL_SHARE) + p.COMPRESSOR[fuel])
    building, utilities = capex * p.BUILDING, capex * p.UTILITIES
    contingency = p.CONTINGENCY * (p.LAND + building + machinery + utilities)
    fixed = p.LAND + building + machinery + utilities + contingency
    working = (fuel_cost + p.SALARIES + p.UTILITY_BILLS) * p.WORKING_MONTHS / 12
    investment = fixed + working

    m = p.MAINTENANCE
    items_1_4 = fuel_cost + p.SALARIES + p.UTILITY_BILLS + m["building"] * building + m["machinery"] * machinery \
        + m["utilities"] * utilities
    items_1_5 = items_1_4 * (1 + p.OPEX_CONTINGENCY)
    cash_cost = items_1_5 * (1 + p.ADMIN) + p.INSURANCE * investment
    d = p.DEPRECIATION
    depreciation = d["building"] * building + d["machinery"] * machinery + d["utilities"] * utilities \
        + d["contingency"] * contingency

    a = annuity(rate, life)
    capital = investment - (p.LAND + working) * (1 + np.asarray(rate, dtype=float)) ** -life  # net of recovery
    revenue = tariff * kwh
    return {"fuel": fuel, "tariff": tariff, "kwh": kwh, "fuel_cost": fuel_cost, "machinery": machinery,
            "fixed": fixed, "working": working, "investment": investment, "cash_cost": cash_cost,
            "depreciation": depreciation, "annual_cost": cash_cost + depreciation,
            "unit_cost": (cash_cost + depreciation) / kwh,          # the workbooks' break-even price (H225)
            "profit": revenue - cash_cost - depreciation,
            "payback": investment / (revenue - cash_cost),           # the workbooks' payback (D12)
            "npv": (revenue - cash_cost) * a - capital,
            "breakeven": (capital / a + cash_cost) / kwh}            # tariff at which npv = 0


def irr(fuel, **kw):
    """Internal rate of return at the given settings (scalars only); nan when there is none in (-99%, 1000%)."""
    f = lambda r: float(plant(fuel, **{**kw, "rate": r})["npv"])
    return brentq(f, -0.99, 10.0) if f(-0.99) * f(10.0) < 0 else np.nan


def margin(tariff_gas=p.TARIFF["gas"], tariff_biogas=p.TARIFF["biogas"], price_gas=p.FUEL_PRICE["gas"],
           price_biogas=p.FUEL_PRICE["biogas"], **shared):
    """Biogas's tariff headroom over its break-even price minus gas's, rials/kWh. Both plants make the same kWh over
    the same life, so NPV(biogas) - NPV(gas) = margin x kWh x annuity: biogas ranks first when this is positive."""
    g = plant("gas", tariff_gas, price_gas, **shared)
    b = plant("biogas", tariff_biogas, price_biogas, **shared)
    return (tariff_biogas - b["breakeven"]) - (tariff_gas - g["breakeven"])
