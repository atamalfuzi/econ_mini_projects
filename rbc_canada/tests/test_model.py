"""The model's steady state and log-linear solution, and the HP filter against statsmodels."""
import numpy as np
import pytest
from statsmodels.tsa.filters.hp_filter import hpfilter
from statsmodels.tsa.stattools import acf

import data
from estimate import SAMPLE, calibrate, hp_filter, logs, moments
from model import VARIABLES, equations, impulse_response, simulate, solve, steady_state

TEXTBOOK = {"alpha": 0.36, "beta": 0.99, "delta": 0.025, "h": 1 / 3, "rho": 0.95, "sigma": 0.007}  # close to Hansen (1985)


@pytest.fixture(scope="module")
def canada():
    p, _ = calibrate(data.load())
    return {**p, "rho": 0.97, "sigma": 0.006}


def levels(ss, x):
    return {v: ss[v] * np.exp(x[VARIABLES.index(v)]) for v in ("y", "c", "i", "h", "k", "z")}


@pytest.mark.parametrize("p", [TEXTBOOK, "canada"])
def test_steady_state_solves_the_equations(p, request):
    p = request.getfixturevalue(p) if isinstance(p, str) else p
    ss = steady_state(**p)
    assert equations(p, ss["theta"], ss, ss) == pytest.approx(0, abs=1e-12)
    assert ss["h"] == p["h"]


@pytest.mark.parametrize("p", [TEXTBOOK, "canada"])
def test_blanchard_kahn_one_stable_root_for_capital(p, request):
    p = request.getfixturevalue(p) if isinstance(p, str) else p
    sol = solve(p)
    stable = sol["roots"][np.abs(sol["roots"]) < 1]
    assert len(stable) == 1 and 0 < stable[0] < 1
    assert np.abs(sol["roots"]).max() > 1
    assert sol["P"][0, 0] == pytest.approx(stable[0], rel=1e-10)  # capital's own coefficient is the stable root


def test_log_linear_solution_is_right_to_first_order():
    """On the linear policy, the nonlinear equations miss by a second-order amount: halving the distance from the
    steady state divides the largest miss by four. A wrong coefficient would leave a first-order miss (ratio two)."""
    sol = solve(TEXTBOOK)
    ss = sol["steady_state"]

    def miss(e):
        s = np.array([e, e])
        return np.abs(equations(TEXTBOOK, ss["theta"], levels(ss, sol["G"] @ s), levels(ss, sol["G"] @ sol["P"] @ s))).max()

    assert miss(0.01) / miss(0.005) == pytest.approx(4, rel=0.05)


def test_impulse_responses_have_the_expected_signs():
    irf = dict(zip(VARIABLES, impulse_response(TEXTBOOK).T))
    for v in ("y", "c", "i", "h"):
        assert irf[v][0] > 0
    assert irf["k"][0] == 0 and irf["k"][1] > 0                 # capital is predetermined
    assert irf["i"][0] > irf["y"][0] > irf["c"][0]               # investment moves most, consumption least
    assert irf["z"][0] == pytest.approx(TEXTBOOK["sigma"])
    assert np.abs(impulse_response(TEXTBOOK, 400)[-1]).max() < 1e-5  # and everything returns to steady state


def test_simulation_feeds_through_a_given_technology_path():
    z = np.random.default_rng(1).normal(0, 0.01, 50)
    path = simulate(TEXTBOOK, 50, z=z)[0]
    assert path[:, VARIABLES.index("z")] == pytest.approx(z)
    assert path[0, VARIABLES.index("k")] == 0


def test_hp_filter_matches_statsmodels():
    y = logs(data.load().loc[SAMPLE[0]:SAMPLE[1]]).y.to_numpy()
    cycle, trend = hp_filter(y)
    sm_cycle, sm_trend = hpfilter(y, lamb=1600)
    assert cycle == pytest.approx(sm_cycle, abs=1e-10)
    assert trend == pytest.approx(sm_trend, abs=1e-10)
    walk = np.random.default_rng(0).normal(size=(120, 3)).cumsum(axis=0)
    both = hp_filter(walk)[0]
    for j in range(3):
        assert both[:, j] == pytest.approx(hpfilter(walk[:, j], lamb=1600)[0], abs=1e-10)


def test_moments_match_pandas_and_statsmodels():
    d = logs(data.load().loc[SAMPLE[0]:SAMPLE[1]])
    cycles = d.apply(lambda s: hp_filter(s.to_numpy())[0])
    m = moments(cycles.to_numpy())
    assert m["sd"] == pytest.approx(100 * cycles.std(ddof=0).to_numpy())
    assert m["corr_output"] == pytest.approx(cycles.corrwith(cycles.y).to_numpy())
    assert m["autocorr"] == pytest.approx([acf(cycles[v], nlags=1)[1] for v in cycles])
    assert m["corr_hours_productivity"] == pytest.approx(cycles.h.corr(cycles.y_h))
