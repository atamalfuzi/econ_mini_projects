"""Predictive regression, the continuous-time calibration, optimal stock shares by horizon, and the
out-of-sample test."""
import numpy as np
import pandas as pd

import data
from model import Params, share

GAMMAS = (2, 5, 10)
HORIZONS = np.arange(1, 31)
OOS_STARTS = (1892, 1927, 1965)  # first forecast year: 20 years of data, then two later starts as in Goyal and Welch
TRAIN = 20


def sample(d):
    """Years t with log D/P at the start of t, the excess return over t, and log D/P at the start of t + 1."""
    s = d.assign(log_dp_next=d.log_dp.shift(-1))
    return s.dropna(subset=["log_dp", "log_excess", "log_dp_next"]).reset_index(drop=True)


def ols(y, x):
    X = np.column_stack([np.ones_like(x), x])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ coef
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (e @ e) / (len(y) - 2))
    return coef, se, e


def predictive(s):
    """r(t) = alpha + beta z(t) + e(t),  z(t+1) = mu (1 - phi) + phi z(t) + u(t+1), with Stambaugh's correction.

    beta_hat - beta = (cov(e, u) / var(u)) (phi_hat - phi), and Kendall's E[phi_hat - phi] = -(1 + 3 phi) / T.
    Shocks to returns and to the dividend yield are strongly negatively correlated, so a downward-biased phi
    biases beta upward.
    """
    r, z, z1 = s.log_excess.to_numpy(), s.log_dp.to_numpy(), s.log_dp_next.to_numpy()
    (alpha, beta), (_, se_beta), e = ols(r, z)
    (c, phi), (_, se_phi), u = ols(z1, z)
    T = len(r)
    cov = np.cov(e, u, ddof=2)
    bias_phi = -(1 + 3 * phi) / T
    return {"first_year": int(s.year.iloc[0]), "last_year": int(s.year.iloc[-1]), "years": T,
            "alpha": alpha, "beta": beta, "beta_se": se_beta, "beta_t": beta / se_beta,
            "r2": 1 - e.var() / r.var(), "phi": phi, "phi_se": se_phi,
            "mean_excess": r.mean(), "mean_log_dp": z.mean(), "sigma_e": np.sqrt(cov[0, 0]),
            "sigma_u": np.sqrt(cov[1, 1]), "corr_eu": cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1]),
            "phi_corrected": phi - bias_phi, "beta_corrected": beta - cov[0, 1] / cov[1, 1] * bias_phi}


def calibrate(f, beta, phi):
    """Map the annual VAR to the continuous-time model.

    The premium is x(t) = xbar + beta (z(t) - zbar), and xbar = E[r] + sigma^2 / 2, since the drift of the log
    return is x - sigma^2 / 2. kappa = -ln(phi). sigma_x makes the OU's one-year innovation variance equal to
    var(beta u). rho is the correlation of e with beta u.
    ponytail: first-order mapping; it ignores the premium's movement within the year, which shifts the slope
    by (1 - phi) / kappa - 1, about -4% at phi = 0.92.
    """
    kappa = -np.log(phi)
    sigma_x = abs(beta) * f["sigma_u"] * np.sqrt(2 * kappa / (1 - phi**2))
    return Params(kappa=kappa, xbar=f["mean_excess"] + f["sigma_e"]**2 / 2, sigma=f["sigma_e"],
                  sigma_x=sigma_x, rho=np.sign(beta) * f["corr_eu"])


def scenarios(f):
    return {"ols": (f["beta"], f["phi"]),
            "bias_corrected": (f["beta_corrected"], f["phi_corrected"]),
            "half_slope": (f["beta"] / 2, f["phi"])}


def allocations(d, f):
    """Myopic and hedging shares by scenario, risk aversion, horizon and starting dividend yield.
    'average' is the sample mean of log D/P; 'current' is the last year in the file."""
    last = d.dropna(subset=["log_dp"]).iloc[-1]
    points = {"average": (np.nan, f["mean_log_dp"]), "current": (int(last.year), last.log_dp)}
    rows, params = [], []
    for name, (beta, phi) in scenarios(f).items():
        p = calibrate(f, beta, phi)
        params.append({"scenario": name, "beta": beta, "phi": phi, **p._asdict(), "half_life": np.log(2) / p.kappa})
        for point, (year, z) in points.items():
            x = p.xbar + beta * (z - f["mean_log_dp"])
            for g in GAMMAS:
                myopic, hedging = share(p, g, x, HORIZONS)
                _, hedging_ode = share(p, g, x, HORIZONS, numeric=True)
                rows.append(pd.DataFrame({"scenario": name, "point": point, "year": year, "dividend_yield": np.exp(z),
                                          "premium": x, "gamma": g, "horizon": HORIZONS, "myopic": myopic,
                                          "hedging": hedging, "total": myopic + hedging,
                                          "hedging_to_myopic": hedging / myopic, "hedging_ode": hedging_ode}))
    return pd.concat(rows, ignore_index=True), pd.DataFrame(params)


def by_yield(f, gamma=5, horizon=30):
    """The share against the starting dividend yield, for one investor and each slope scenario."""
    rows = []
    yields = np.linspace(0.01, 0.07, 61)
    for name, (beta, phi) in {**scenarios(f), "no_predictability": (0.0, f["phi"])}.items():
        p = calibrate(f, beta, phi)
        x = p.xbar + beta * (np.log(yields) - f["mean_log_dp"])
        myopic, hedging = share(p, gamma, x, horizon)
        rows.append(pd.DataFrame({"scenario": name, "gamma": gamma, "horizon": horizon, "dividend_yield": yields,
                                  "myopic": myopic, "hedging": hedging, "total": myopic + hedging}))
    return pd.concat(rows, ignore_index=True)


def out_of_sample(s):
    """Goyal and Welch (2008): each year's return forecast from the regression on all earlier years (expanding
    window, at least TRAIN years), against the mean of the same earlier years."""
    rows = []
    for i in range(TRAIN, len(s)):
        past = s.iloc[:i]
        (alpha, beta), _, _ = ols(past.log_excess.to_numpy(), past.log_dp.to_numpy())
        rows.append({"year": int(s.year.iloc[i]), "actual": s.log_excess.iloc[i], "slope": beta,
                     "forecast_dp": alpha + beta * s.log_dp.iloc[i], "forecast_mean": past.log_excess.mean()})
    o = pd.DataFrame(rows)
    o["cum_sse_difference"] = ((o.actual - o.forecast_mean)**2 - (o.actual - o.forecast_dp)**2).cumsum()
    summary = []
    for start in OOS_STARTS:
        w = o[o.year >= start]
        sse_dp, sse_mean = ((w.actual - w.forecast_dp)**2).sum(), ((w.actual - w.forecast_mean)**2).sum()
        summary.append({"first_forecast": start, "last_forecast": int(w.year.max()), "forecasts": len(w),
                        "r2_oos": 1 - sse_dp / sse_mean})
    return o, pd.DataFrame(summary)


def main():
    d = data.load()
    s = sample(d)
    f = predictive(s)
    data.OUTPUT.mkdir(exist_ok=True)
    pd.DataFrame([f]).to_csv(data.OUTPUT / "predictive.csv", index=False)
    alloc, params = allocations(d, f)
    alloc.to_csv(data.OUTPUT / "allocation.csv", index=False)
    params.to_csv(data.OUTPUT / "calibration.csv", index=False)
    by_yield(f).to_csv(data.OUTPUT / "share_by_yield.csv", index=False)
    path, summary = out_of_sample(s)
    path.to_csv(data.OUTPUT / "oos_path.csv", index=False)
    summary.to_csv(data.OUTPUT / "oos.csv", index=False)


if __name__ == "__main__":
    main()
