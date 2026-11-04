"""The Markov pricer against closed forms and Mehra and Prescott (1985), and the data against their Table 1."""
import numpy as np
import pandas as pd
import pytest

import data
import model
from estimate import MEHRA_PRESCOTT, calibrations, mehra_prescott, moments


@pytest.fixture(scope="module")
def d():
    return data.load()


@pytest.mark.parametrize("gamma", [0.5, 2, 5, 10])
def test_two_state_iid_matches_closed_form(gamma):
    """With phi = 0.5 growth is i.i.d., the price-dividend ratio is constant and
    E[Re] = E[x] / (beta E[x^(1-gamma)]), Rf = 1 / (beta E[x^-gamma])."""
    x, P = model.two_state(0.018, 0.036, 0.0)
    beta = 0.95
    r = model.price(x, P, beta, gamma)
    assert 1 + r["equity"] == pytest.approx(x.mean() / (beta * np.mean(x ** (1 - gamma))), rel=1e-12)
    assert 1 + r["riskfree"] == pytest.approx(1 / (beta * np.mean(x ** -gamma)), rel=1e-12)


@pytest.mark.parametrize("gamma", [1, 3, 8])
def test_lognormal_iid_matches_closed_form(gamma):
    """i.i.d. lognormal growth on Gauss-Hermite nodes: Rf = exp(-ln beta + gamma mu - gamma^2 sigma^2 / 2) and
    E[Re] / Rf = exp(gamma sigma^2)."""
    mu, sigma, beta = 0.018, 0.036, 0.97
    t, w = np.polynomial.hermite.hermgauss(30)
    x, P = np.exp(mu + np.sqrt(2) * sigma * t), np.tile(w / np.sqrt(np.pi), (30, 1))
    r = model.price(x, P, beta, gamma)
    rf = np.exp(-np.log(beta) + gamma * mu - gamma ** 2 * sigma ** 2 / 2)
    assert 1 + r["riskfree"] == pytest.approx(rf, rel=1e-10)
    assert (1 + r["equity"]) / (1 + r["riskfree"]) == pytest.approx(np.exp(gamma * sigma ** 2), rel=1e-10)


def test_mehra_prescott_published_economy():
    """Their parameters (growth 1.8%, s.d. 3.6%, phi 0.43): the largest premium with gamma up to 10, beta below 1
    and a risk-free rate of at most 4% is 0.35% (their Figure 4)."""
    _, summary = mehra_prescott({"published": (0.018, 0.036, -0.14, 0.008, 0.0618)})
    assert summary.max_premium_mp_region.iloc[0] == pytest.approx(0.0035, abs=0.0002)


def test_disaster_chain():
    x0, P0 = model.two_state(0.02, 0.035, -0.1)
    x, P = model.with_disaster(x0, P0, 0.02, 0.3)
    assert np.allclose(P.sum(axis=1), 1)
    assert model.stationary(P)[-1] == pytest.approx(0.02)
    beta = model.riskfree_beta(x, P, 4, 0.01)
    assert model.price(x, P, beta, 4)["riskfree"] == pytest.approx(0.01)
    # A disaster with zero probability changes nothing.
    xz, Pz = model.with_disaster(x0, P0, 0.0, 0.3)
    assert model.price(xz, Pz, 0.97, 4)["premium"] == pytest.approx(model.price(x0, P0, 0.97, 4)["premium"])


def test_1889_1978_moments_are_close_to_mehra_and_prescott(d):
    """Within 1 point for returns and 0.5 points for consumption. Shiller's short rate is commercial paper
    throughout, where theirs is Treasury bills from 1931, and consumption has been revised since 1985."""
    m = moments(d, 1889, 1978)
    assert m["years"] == 90
    assert m["stock_mean"] == pytest.approx(MEHRA_PRESCOTT["stock_mean"], abs=0.01)
    assert m["bill_mean"] == pytest.approx(MEHRA_PRESCOTT["bill_mean"], abs=0.01)
    assert m["consumption_mean"] == pytest.approx(MEHRA_PRESCOTT["consumption_mean"], abs=0.005)
    assert m["consumption_sd"] == pytest.approx(MEHRA_PRESCOTT["consumption_sd"], abs=0.005)
    assert m["consumption_autocorr"] < 0


def test_calibrations_use_matching_years(d):
    cal = calibrations(pd.DataFrame([moments(d, 1889, 1978), moments(d, 1889, 2007)]))
    assert cal["Mehra-Prescott published"][:3] == (0.0183, 0.0357, -0.14)
    assert cal["1889-2007"][0] == pytest.approx(d[d.year.between(1889, 2007)].consumption_growth.mean())


def test_series_invariants(d):
    assert d.year.is_unique and d.year.diff().dropna().eq(1).all()
    assert d.year.min() == 1871
    assert (d[["price", "cpi"]].dropna() > 0).all().all()
    assert (d.consumption.dropna() > 0).all()
    assert d.consumption.notna().sum() == 2008 - 1889 + 1  # 1889-2008; the partial 2009 value is dropped
    assert d.excess.notna().sum() == 2011 - 1871 + 1


def test_rebuilt_returns_match_shiller(d):
    both = d.dropna(subset=["stock", "shiller_return"])
    assert len(both) == 2012 - 1871 + 1
    assert np.allclose(both.stock, both.shiller_return, atol=1e-9)
    rate = d.dropna(subset=["bill"])
    assert np.allclose(1 + rate.bill, rate.shiller_real_rate, atol=1e-9)
