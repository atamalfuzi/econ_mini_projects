"""The fixed-effects estimator against statsmodels and simulated panels, and the data against Dee and Fu (2004)."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

import data
from estimate import REF, event_study, sample, two_period, twfe


def panel(units=60, years=range(1990, 2006), effect=0.0, slope=0.0, seed=0):
    """Half the units treated from 1995. Treated units can also follow their own linear trend."""
    rng = np.random.default_rng(seed)
    rows = [(u, t) for u in range(units) for t in years]
    d = pd.DataFrame(rows, columns=["ncessch", "year"])
    d["az"] = (d.ncessch < units // 2).astype(int)
    d["leaid"] = d.ncessch // 3
    unit_fe, year_fe = rng.normal(0, 1, units), dict(zip(years, rng.normal(0, 1, len(years))))
    d["y"] = (unit_fe[d.ncessch] + d.year.map(year_fe) + effect * d.az * (d.year > REF)
              + slope * d.az * (d.year - REF) + rng.normal(0, 0.1, len(d)))
    return d


@pytest.fixture(scope="module")
def schools():
    return sample(data.load())


def test_twfe_matches_least_squares_with_dummies():
    d = panel(units=30, years=range(1990, 1996))
    d["treat"] = d.az * (d.year > 1992)
    beta, V = twfe(d, "y", ["treat"], absorbed_k=30 - 1 + 6 - 1 + 1)  # all dummies and a constant, as statsmodels
    fit = smf.ols("y ~ treat + C(ncessch) + C(year)", d).fit(cov_type="cluster", cov_kwds={"groups": d.leaid})
    assert beta.treat == pytest.approx(fit.params.treat, rel=1e-8)
    assert np.sqrt(V.loc["treat", "treat"]) == pytest.approx(fit.bse.treat, rel=1e-8)


def test_event_study_recovers_a_known_effect():
    d = panel(effect=0.5)
    out, summary = event_study(d, "y")
    post = out[out.year > REF]
    assert post.coef.to_numpy() == pytest.approx(0.5, abs=0.05)
    assert summary["pretrend_p"] > 0.01


def test_own_trend_removes_a_pretrend_with_no_effect():
    d = panel(slope=-0.05)
    _, plain = event_study(d, "y")
    _, adjusted = event_study(d, "y", trend=True)
    assert plain["pretrend_p"] < 0.001
    assert plain["post_1999_2005_mean"] < -0.3
    assert adjusted["post_1999_2005_mean"] == pytest.approx(0, abs=0.05)
    assert adjusted["pretrend_slope"] == pytest.approx(-0.05, abs=0.01)


def test_two_period_difference_equals_fixed_effects_on_two_years(schools):
    b = schools[schools.year.isin([REF, 1999]) & schools.white_share.notna()]
    b = b[b.groupby("ncessch").year.transform("nunique") == 2].copy()
    b["az_1999"] = b.az * (b.year == 1999)
    beta, _ = twfe(b, "white_share", ["az_1999"])
    assert two_period(schools, "white_share", "none")["estimate"] == pytest.approx(beta.az_1999, rel=1e-8)


def test_two_period_estimates_are_close_to_dee_and_fu(schools):
    white = two_period(schools, "white_share", "none")
    ptr = two_period(schools, "ptr", "none")
    assert white["estimate"] == pytest.approx(-0.026, abs=0.005)  # their Table 3, column 1
    assert ptr["estimate"] == pytest.approx(1.26, abs=0.3)        # their Table 4, column 1


def test_panel_is_one_row_per_school_and_year():
    d = data.load()
    assert not d.duplicated(["ncessch", "year"]).any()
    assert set(d.state) == {"AZ", "NM"}
    assert d.groupby("state").year.nunique().eq(len(data.YEARS)).all()


def test_shares_are_shares(schools):
    assert schools.white_share.between(0, 1).all()
    assert schools.youth_white_share.dropna().between(0, 1).all()
    assert (schools.ptr.dropna() > 0).all()
