"""The processed quarterly file, and the calibration's consistency with the model's steady state."""
import pandas as pd
import pytest

import data
from estimate import RATIOS, SAMPLE, calibrate
from model import steady_state


@pytest.fixture(scope="module")
def d():
    return data.load()


def test_file_is_small_and_quarters_are_consecutive(d):
    assert data.QUARTERLY.stat().st_size < 2_000_000
    assert (d.index == pd.period_range(d.index[0], d.index[-1], freq="Q")).all()
    assert d.index[0] == pd.Period("1961Q1")


def test_series_cover_the_samples(d):
    assert d.loc["1961Q1":SAMPLE[1], ["Y", "C", "I", "Y_nominal", "I_nominal", "compensation"]].notna().all().all()
    assert d.loc[SAMPLE[0]:SAMPLE[1], ["H", "population"]].notna().all().all()
    assert d.loc[RATIOS[0]:RATIOS[1], "K_nominal"].notna().all()
    assert d.H.first_valid_index() == pd.Period(SAMPLE[0]) and d.K_nominal.first_valid_index() == pd.Period(RATIOS[0])


def test_levels_and_ratios_are_plausible(d):
    s = d.loc[SAMPLE[0]:SAMPLE[1]]
    assert (s[["Y", "C", "I", "H", "population"]] > 0).all().all()
    assert (s.C_nominal + s.I_nominal < s.Y_nominal).all()  # government and net exports make up the rest
    assert (s.compensation / (s.compensation + s.operating_surplus)).between(0.55, 0.8).all()
    assert (s.H / s.population).between(15, 35).all()      # weekly hours per person aged 15 to 64
    r = d.loc[RATIOS[0]:RATIOS[1]]
    assert (r.K_nominal / (r.Y_nominal / 4)).between(6, 14).all()


def test_steady_state_reproduces_the_calibration_targets(d):
    p, targets = calibrate(d)
    ss = steady_state(**p)
    assert ss["k"] / ss["y"] == pytest.approx(targets["capital_output"])
    assert ss["i"] / ss["y"] == pytest.approx(targets["investment_output"])
    assert 0.98 < p["beta"] < 1 and 0 < p["delta"] < 0.05 and 0.25 < p["alpha"] < 0.45
