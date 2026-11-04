"""The cycle against the report, the cost build-up against the workbooks, and the break-even and ranking logic.
Nothing here downloads or reads the source folder: workbook values come from parameters.py and data/."""
import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize_scalar

import parameters as p
from model import ETA_CYCLE, cycle, fuel_use, irr, margin, optimum_cr, plant


def test_optimum_matches_the_report():
    r = optimum_cr(p.CP_CODE)
    numeric = minimize_scalar(lambda x: -cycle(x)["w_net"], bounds=(2, 30), method="bounded", options={"xatol": 1e-9}).x
    assert r == pytest.approx(numeric, abs=1e-5)
    # The exact optimum is 8.2123. Net work there and at the report's 8.211 differ by 3e-6 kJ/kg, far below what a
    # numerical maximiser stopping on W_net can resolve, so a 0.005 tolerance on CR is as tight as the report allows.
    assert r == pytest.approx(p.REPORTED_CR, abs=0.005)
    # 538.3 is printed to one decimal.
    assert cycle(r)["w_net"] == pytest.approx(p.REPORTED_WNET, abs=0.05)
    assert cycle(r)["w_net"] == pytest.approx(p.CV * (p.T3 ** 0.5 - p.T1 ** 0.5) ** 2, rel=1e-12)


def test_text_value_of_cp_moves_the_optimum_but_not_its_height():
    assert optimum_cr(p.CP_TEXT) == pytest.approx(10.69, abs=0.01)
    assert cycle(optimum_cr(p.CP_TEXT), p.CP_TEXT)["w_net"] == pytest.approx(cycle(optimum_cr())["w_net"], rel=1e-12)


@pytest.mark.parametrize("cp", [p.CP_CODE, p.CP_TEXT])
def test_efficiency_matches_closed_form(cp):
    cr = np.linspace(2, 20, 50)
    assert cycle(cr, cp)["eta"] == pytest.approx(1 - cr ** (1 - cp / p.CV), rel=1e-12)


def test_fuel_flows_match_the_report():
    for fuel in p.FUELS:
        f = fuel_use(fuel, ETA_CYCLE)
        assert f["kg_per_s"] == pytest.approx(p.REPORTED_FUEL_KG_S[fuel], abs=5e-6)   # printed to 4 significant digits
        assert f["m3_per_h"] == pytest.approx(p.WORKBOOK_FUEL_M3_H[fuel], rel=2e-4)


@pytest.mark.parametrize("fuel", p.FUELS)
def test_cost_build_up_reproduces_the_workbooks(fuel):
    # The fuel flow comes from the cycle, not the workbook's rounded m3/h, so totals agree to about 1e-6.
    tariff = p.TARIFF_GAS_WORKBOOK if fuel == "gas" else p.TARIFF["biogas"]
    r = plant(fuel, tariff, annual_fuel=False)
    for item, value in p.WORKBOOK[fuel].items():
        assert float(r[item]) == pytest.approx(value, rel=1e-5), item


def test_parameters_match_the_extracted_cells():
    c = pd.read_csv(p.DATA / "workbook_cells.csv").set_index("cell")
    for fuel in p.FUELS:
        cell = lambda ref: float(c.loc[ref, fuel])
        assert cell("E36") == pytest.approx(p.POWER_KW * p.HOURS)
        assert cell("G145") == p.FUEL_PRICE[fuel]
        assert cell("E145") == p.WORKBOOK_FUEL_M3_H[fuel]
        assert cell("I174") == p.LAND and cell("I176") == p.BUILDING and cell("I178") == p.UTILITIES
        assert cell("I106") == pytest.approx(p.ENGINE_USD_PER_KW * p.POWER_KW * p.RIALS_PER_USD)
        assert cell("I108") == p.COMPRESSOR[fuel]
        assert cell("I213") == p.SALARIES and cell("I214") == p.UTILITY_BILLS
        for item, ref in (("fixed", "I185"), ("working", "I191"), ("depreciation", "I209"), ("annual_cost", "I223"),
                          ("unit_cost", "H225"), ("profit", "D10"), ("payback", "D12")):
            assert cell(ref) == pytest.approx(p.WORKBOOK[fuel][item], rel=1e-12)
    assert float(c.loc["G36", "biogas"]) == p.TARIFF["biogas"]
    assert float(c.loc["G36", "gas"]) == p.TARIFF_GAS_WORKBOOK


@pytest.mark.parametrize("fuel", p.FUELS)
@pytest.mark.parametrize("kw", [{}, {"annual_fuel": False}, {"eta": 0.38, "rate": 0.0, "life": 15}, {"capex": 1.4}])
def test_npv_is_zero_at_break_even(fuel, kw):
    b = float(plant(fuel, **kw)["breakeven"])
    scale = float(plant(fuel, **kw)["investment"])
    assert float(plant(fuel, tariff=b, **kw)["npv"]) == pytest.approx(0, abs=1e-9 * scale)
    assert plant(fuel, tariff=b * 1.001, **kw)["npv"] > 0 > plant(fuel, tariff=b * 0.999, **kw)["npv"]


def test_npv_is_zero_at_the_irr():
    r = irr("biogas", annual_fuel=False)
    assert 0 < r < 0.2
    assert float(plant("biogas", annual_fuel=False, rate=r)["npv"]) == pytest.approx(0, abs=1)
    assert np.isnan(irr("gas"))   # costs exceed revenue every year at 1,000 rials/kWh


@pytest.mark.parametrize("kw", [{}, {"annual_fuel": False}, {"eta": 0.4}])
def test_ranking_flips_at_the_break_even_point(kw):
    """Holding gas at its tariff, biogas overtakes gas exactly where its headroom over break-even equals gas's."""
    b_gas = float(plant("gas", **kw)["breakeven"])
    b_bio = float(plant("biogas", **kw)["breakeven"])
    flip = b_bio + (p.TARIFF["gas"] - b_gas)
    npv_gas = float(plant("gas", **kw)["npv"])
    assert float(plant("biogas", tariff=flip, **kw)["npv"]) == pytest.approx(npv_gas, rel=1e-9)
    for step, sign in ((10.0, 1), (-10.0, -1)):
        assert np.sign(float(margin(tariff_biogas=flip + step, **kw))) == sign
        assert np.sign(float(plant("biogas", tariff=flip + step, **kw)["npv"]) - npv_gas) == sign


def test_margin_is_the_npv_gap_per_discounted_kwh():
    g, b = plant("gas"), plant("biogas")
    a = (1 - (1 + p.RATE) ** -p.LIFE) / p.RATE
    assert float(margin()) * g["kwh"] * a == pytest.approx(float(b["npv"] - g["npv"]), rel=1e-9)


def test_model_works_on_arrays():
    eta = np.array([0.35, 0.5, ETA_CYCLE])
    out = margin(eta=eta, capex=np.array([0.8, 1.0, 1.2]))
    assert out.shape == (3,)
    assert out[2] == pytest.approx(float(margin(capex=1.2)), rel=1e-12)


def test_published_cost_conversion():
    from estimate import rials_per_m3
    gross_kwh_per_m3 = 21000 * 1.2 * (55.5 / 50) / 3600  # the study's biogas, raised to a gross value
    assert rials_per_m3(1.0) == pytest.approx(0.01 * gross_kwh_per_m3 * p.USD_PER_EUR * 42000, rel=1e-9)
    assert rials_per_m3(1.0, p.RIALS_PER_USD_MARKET) / rials_per_m3(1.0) == pytest.approx(60000 / 42000)


def test_biogas_does_not_break_even_at_published_upgrading_costs():
    from estimate import benchmark
    b = benchmark().set_index("case")
    assert not b.breaks_even_at_tariff.any()
    assert (b.breakeven_biogas > p.TARIFF["biogas"]).all()
