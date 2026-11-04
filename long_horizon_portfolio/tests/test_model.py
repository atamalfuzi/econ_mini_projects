"""The closed form against the ODEs and the HJB equation, special cases with no hedging, the bias correction in
simulation, the out-of-sample test, and the data."""
import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize_scalar

import data
from estimate import TRAIN, calibrate, out_of_sample, predictive, sample
from model import Params, closed_form, numerical, share

P = Params(kappa=0.12, xbar=0.053, sigma=0.175, sigma_x=0.0092, rho=-0.8)  # close to the full-sample calibration
STRONG = Params(kappa=0.08, xbar=0.06, sigma=0.15, sigma_x=0.04, rho=-0.95)  # larger hedging demand
HORIZONS = np.array([1, 2, 5, 10, 20, 30, 50])


@pytest.fixture(scope="module")
def annual():
    return data.load()


@pytest.mark.parametrize("p", [P, STRONG])
@pytest.mark.parametrize("gamma", [1.5, 2, 5, 10, 50])
def test_closed_form_matches_ode(p, gamma):
    B, C = closed_form(p, gamma, HORIZONS)
    _, Bn, Cn = numerical(p, gamma, HORIZONS)
    assert B == pytest.approx(Bn, rel=1e-8, abs=1e-10)
    assert C == pytest.approx(Cn, rel=1e-8, abs=1e-10)
    for x in (0.0, 0.03, 0.08):
        assert share(p, gamma, x, HORIZONS)[1] == pytest.approx(share(p, gamma, x, HORIZONS, numeric=True)[1], abs=1e-9)


@pytest.mark.parametrize("p", [P, STRONG])
@pytest.mark.parametrize("gamma", [2, 5])
def test_share_satisfies_hjb(p, gamma):
    """Build J from the ODE solution and check the HJB equation by finite differences, maximising over the
    stock share numerically. This checks the ODEs themselves, not only their solution."""
    r, tau, h = 0.02, 10.0, 2e-5  # central differences: the error falls with h^2 until rounding takes over
    A, B, C = numerical(p, gamma, [tau - h, tau, tau + h], r=r)

    def J(W, x, i=1):
        return W**(1 - gamma) / (1 - gamma) * np.exp(A[i] + B[i] * x + C[i] * x**2 / 2)

    for x in (0.0, 0.05, 0.10):
        W = 1.0
        J_tau = (J(W, x, 2) - J(W, x, 0)) / (2 * h)
        J_W = (J(W + h, x) - J(W - h, x)) / (2 * h)
        J_WW = (J(W + h, x) - 2 * J(W, x) + J(W - h, x)) / h**2
        J_x = (J(W, x + h) - J(W, x - h)) / (2 * h)
        J_xx = (J(W, x + h) - 2 * J(W, x) + J(W, x - h)) / h**2
        J_Wx = (J(W + h, x + h) - J(W + h, x - h) - J(W - h, x + h) + J(W - h, x - h)) / (4 * h * h)

        def minus_hjb(pi):
            return -(J_W * W * (r + pi * x) + J_WW * W**2 * pi**2 * p.sigma**2 / 2
                     + J_Wx * W * pi * p.sigma * p.sigma_x * p.rho)

        best = minimize_scalar(minus_hjb, bounds=(-20, 20), method="bounded", options={"xatol": 1e-10})
        residual = -J_tau - best.fun + J_x * p.kappa * (p.xbar - x) + J_xx * p.sigma_x**2 / 2
        assert residual / abs(J(W, x)) == pytest.approx(0, abs=1e-5)
        assert best.x == pytest.approx(sum(share(p, gamma, x, tau)), abs=1e-4)


def test_no_predictability_gives_merton_at_every_horizon(annual):
    """A zero slope means a constant premium (sigma_x = 0); the share is then (mu - r) / (g sigma^2)."""
    f = predictive(sample(annual))
    p = calibrate(f, 0.0, f["phi"])
    assert p.sigma_x == 0
    for gamma in (2, 5, 10):
        myopic, hedging = share(p, gamma, p.xbar, HORIZONS)
        assert hedging == pytest.approx(0, abs=1e-12)
        assert myopic + hedging == pytest.approx(p.xbar / (gamma * p.sigma**2))


@pytest.mark.parametrize("numeric", [False, True])
def test_uncorrelated_shocks_give_merton_at_every_horizon(numeric):
    p = STRONG._replace(rho=0.0)
    for gamma in (2, 5, 10):
        for x in (0.02, 0.06):
            myopic, hedging = share(p, gamma, x, HORIZONS, numeric=numeric)
            assert myopic + hedging == pytest.approx(x / (gamma * p.sigma**2), abs=1e-12)


@pytest.mark.parametrize("numeric", [False, True])
def test_log_utility_has_no_hedging_demand(numeric):
    for p in (P, STRONG):
        for x in (0.0, 0.05):
            assert share(p, 1.0, x, HORIZONS, numeric=numeric)[1] == pytest.approx(0, abs=1e-12)


def test_hedging_demand_grows_with_the_horizon():
    hedging = share(STRONG, 5, STRONG.xbar, HORIZONS)[1]
    assert (np.diff(hedging) > 0).all() and hedging[0] > 0  # rho < 0: stocks hedge falls in their own premium


def test_bias_correction_removes_most_of_the_bias():
    """Simulate the VAR with no predictability and the sample's persistence and correlation."""
    rng = np.random.default_rng(0)
    T, phi, cov = 140, 0.9, -0.8 * np.sqrt(0.03 * 0.04)
    ols, corrected = [], []
    for _ in range(500):
        shocks = rng.multivariate_normal([0, 0], [[0.03, cov], [cov, 0.04]], T + 1)
        z = np.zeros(T + 1)
        for t in range(1, T + 1):
            z[t] = phi * z[t - 1] + shocks[t, 1]
        s = pd.DataFrame({"year": np.arange(T), "log_dp": z[:-1], "log_dp_next": z[1:], "log_excess": shocks[1:, 0]})
        f = predictive(s)
        ols.append(f["beta"])
        corrected.append(f["beta_corrected"])
    assert np.mean(ols) > 0.012
    assert abs(np.mean(corrected)) < 0.25 * np.mean(ols)


def test_out_of_sample_forecasts_use_only_the_past(annual):
    s = sample(annual)
    before, _ = out_of_sample(s)
    changed = s.copy()
    changed.loc[changed.index[-1], "log_excess"] += 1.0
    after, _ = out_of_sample(changed)
    assert before.year.iloc[0] == s.year.iloc[TRAIN]
    pd.testing.assert_frame_equal(before.iloc[:-1, :5], after.iloc[:-1, :5])


def test_annual_data(annual):
    assert annual.year.is_unique and (np.diff(annual.year) == 1).all()
    assert (annual.year.min(), annual.year.max()) == (1871, 2016)
    assert annual.dividend_yield.dropna().between(0.01, 0.10).all()
    # The excess return from Shiller's real columns equals the one from nominal prices, dividends and the rate.
    nominal = np.log((annual.price.shift(-1) + annual.dividend) / annual.price) - np.log1p(annual.rate / 100)
    ok = annual.log_excess.notna()
    assert annual.log_excess[ok].to_numpy() == pytest.approx(nominal[ok].to_numpy(), abs=1e-10)
    assert data.ANNUAL.stat().st_size < 2_000_000


def test_estimation_sample(annual):
    s = sample(annual)
    assert (s.year.min(), s.year.max(), len(s)) == (1872, 2011, 140)
    assert not s[["log_dp", "log_excess", "log_dp_next"]].isna().any().any()
