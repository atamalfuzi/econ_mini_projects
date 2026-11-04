"""Calibrate the model to Canada, estimate technology from a Solow residual, and compare HP cycles in model and data."""
import numpy as np
import pandas as pd

import data
import model

SAMPLE = ("1976Q1", "2019Q4")  # hours start in 1976; the pandemic quarters are left out of the main comparison
RATIOS = ("1990Q1", "2019Q4")  # the balance sheet capital stock starts in 1990
WEEK = 100                     # discretionary hours in a week, as in Cooley and Prescott (1995)
LAMBDA = 1600
SIMULATIONS, SEED = 1000, 0
SERIES = ["y", "c", "i", "h", "y_h"]
NAMES = {"y": "Output", "c": "Consumption", "i": "Investment", "h": "Hours", "y_h": "Output per hour"}
STATISTICS = ["sd", "relative_sd", "corr_output", "autocorr"]
# Peak and trough quarters inside the sample, from the C.D. Howe Institute Business Cycle Council's 2021 chronology:
# https://cdhowe.org/wp-content/uploads/2024/06/Recession_Chronology_0.xlsx
RECESSIONS = {"1981-82": ("1981Q2", "1982Q4"), "1990-92": ("1990Q1", "1992Q2"), "2008-09": ("2008Q3", "2009Q2")}


def hp_filter(x, lamb=LAMBDA):
    """Cycle and trend along the first axis. The trend solves (I + lamb D'D) trend = x, with D the second difference."""
    x = np.asarray(x, float)
    n = len(x)
    D = np.diff(np.eye(n), 2, axis=0)
    # ponytail: dense solve, fine for a few hundred quarters; a banded solver if series get much longer
    trend = np.linalg.solve(np.eye(n) + lamb * D.T @ D, x.reshape(n, -1)).reshape(x.shape)
    return x - trend, trend


def moments(x):
    """Statistics of cycles x, shape (..., quarters, len(SERIES)): standard deviation in per cent, standard deviation
    relative to output, correlation with output, first-order autocorrelation, and hours against output per hour."""
    x = x - x.mean(axis=-2, keepdims=True)
    sd = np.sqrt((x ** 2).mean(axis=-2))
    y, h, yh = (SERIES.index(v) for v in ("y", "h", "y_h"))
    corr = (x * x[..., [y]]).mean(axis=-2) / (sd * sd[..., [y]])
    return {"sd": 100 * sd, "relative_sd": sd / sd[..., [y]], "corr_output": corr,
            "autocorr": (x[..., 1:, :] * x[..., :-1, :]).sum(axis=-2) / (x ** 2).sum(axis=-2),
            "corr_hours_productivity": (x[..., h] * x[..., yh]).mean(axis=-1) / (sd[..., h] * sd[..., yh])}


def logs(d):
    return np.log(pd.DataFrame({"y": d.Y, "c": d.C, "i": d.I, "h": d.H, "y_h": d.Y / d.H}))[SERIES]


def calibrate(d):
    """Parameters from 1990-2019 averages. delta = I/K and beta come from the model's own steady state."""
    r = d.loc[RATIOS[0]:RATIOS[1]]
    labour = (r.compensation / (r.compensation + r.operating_surplus)).mean()  # mixed income and taxes split alike
    iy = (r.I_nominal / r.Y_nominal).mean()
    ky = (r.K_nominal / (r.Y_nominal / 4)).mean()  # national accounts flows are at annual rates
    weekly = (r.H / r.population).mean()
    alpha, delta = 1 - labour, iy / ky
    p = {"alpha": alpha, "beta": 1 / (1 + alpha / ky - delta), "delta": delta, "h": weekly / WEEK}
    targets = {"labour_share": labour, "investment_output": iy, "capital_output": ky, "hours_per_week": weekly,
               "consumption_output": (r.C_nominal / r.Y_nominal).mean()}
    return p, targets


def technology(d, p, ky):
    """Solow residual log z = log y - alpha log k - (1 - alpha) log h over SAMPLE, less a linear trend, and an AR(1)
    fitted to it. Capital is built by perpetual inventory from 1961, starting at the calibrated capital-output ratio."""
    k = np.empty(len(d))
    k[0] = ky * d.Y.iloc[0] / 4
    for t in range(len(d) - 1):
        k[t + 1] = (1 - p["delta"]) * k[t] + d.I.iloc[t] / 4
    s = d.assign(K=k).loc[SAMPLE[0]:SAMPLE[1]]
    log_z = (np.log(s.Y) - p["alpha"] * np.log(s.K) - (1 - p["alpha"]) * np.log(s.H)).to_numpy()
    t = np.arange(len(s))
    slope, intercept = np.polyfit(t, log_z, 1)
    u = log_z - (intercept + slope * t)
    rho = (u[1:] @ u[:-1]) / (u[:-1] @ u[:-1])
    sigma = np.std(u[1:] - rho * u[:-1], ddof=1)
    residual = pd.DataFrame({"quarter": s.index.astype(str), "log_z": log_z, "deviation": u})
    return {"rho": rho, "sigma": sigma, "trend_growth": 400 * slope}, residual


def compare(d, p):
    """Data and model moments. Each simulated sample has as many quarters as the data and is filtered the same way."""
    data_m = moments(hp_filter(logs(d.loc[SAMPLE[0]:SAMPLE[1]]))[0])
    full = d.loc[SAMPLE[0]:].dropna(subset=["Y", "H"])
    full_m = moments(hp_filter(logs(full))[0])
    n = len(d.loc[SAMPLE[0]:SAMPLE[1]])
    sim = model.simulate(p, n, SIMULATIONS, seed=SEED)[..., [model.VARIABLES.index(v) for v in SERIES]]
    sim_m = moments(np.moveaxis(hp_filter(np.moveaxis(sim, 1, 0))[0], 0, 1))
    rows = [(v, s, data_m[s][j], full_m[s][j], sim_m[s][:, j]) for s in STATISTICS for j, v in enumerate(SERIES)]
    s = "corr_hours_productivity"
    rows.append(("h", s, data_m[s], full_m[s], sim_m[s]))
    table = pd.DataFrame([{"variable": v, "statistic": s, "data": a, "data_to_latest": b, "model": m.mean(),
                           "model_p05": np.quantile(m, 0.05), "model_p95": np.quantile(m, 0.95)} for v, s, a, b, m in rows])
    return table, full.index[-1]


def history(d, p, residual):
    """Feed the measured technology deviations through the model and set its HP cycles beside the data's."""
    z = residual.deviation.to_numpy()
    path = model.simulate(p, len(z), z=z)[0][:, [model.VARIABLES.index(v) for v in SERIES]]
    model_cycle = hp_filter(path)[0]
    data_cycle = hp_filter(logs(d.loc[SAMPLE[0]:SAMPLE[1]]))[0]
    out = pd.DataFrame({"quarter": residual.quarter})
    for j, v in enumerate(SERIES):
        out[f"data_{v}"], out[f"model_{v}"] = 100 * data_cycle[:, j], 100 * model_cycle[:, j]
    return out


def main():
    d = data.load()
    p, targets = calibrate(d)
    tech, residual = technology(d, p, targets["capital_output"])
    p.update(rho=tech["rho"], sigma=tech["sigma"])
    sol = model.solve(p)
    ss = sol["steady_state"]
    data.OUTPUT.mkdir(exist_ok=True)

    calibration = [
        ("alpha", p["alpha"], "capital share: 1 minus compensation / (compensation + gross operating surplus), 1990-2019"),
        ("beta", p["beta"], "discount factor: from the Euler equation, 1 / (1 + alpha Y/K - delta)"),
        ("delta", p["delta"], "quarterly depreciation: investment / capital, 1990-2019"),
        ("h", p["h"], f"share of time worked: actual hours per person aged 15-64 / {WEEK} hours a week, 1990-2019"),
        ("theta", ss["theta"], "weight on leisure: set so the household works the share h"),
        ("rho", p["rho"], f"technology persistence: AR(1) of the detrended Solow residual, {SAMPLE[0]}-{SAMPLE[1]}"),
        ("sigma", p["sigma"], f"technology shock standard deviation: same regression, {SAMPLE[0]}-{SAMPLE[1]}"),
        ("labour_share", targets["labour_share"], "compensation / (compensation + gross operating surplus), 1990-2019"),
        ("investment_output", targets["investment_output"], "data and model: private investment / GDP, current prices"),
        ("capital_output", targets["capital_output"], "data and model: private produced capital / quarterly GDP"),
        ("consumption_output_data", targets["consumption_output"], "consumption / GDP in the data, current prices"),
        ("consumption_output_model", ss["c"] / ss["y"], "consumption / output in the model, which has no government or trade"),
        ("hours_per_week", targets["hours_per_week"], "actual hours worked per person aged 15-64 per week, 1990-2019"),
        ("frisch_elasticity", (1 - p["h"]) / p["h"], "Frisch elasticity of hours implied by log leisure: (1 - h) / h"),
        ("technology_trend_growth", tech["trend_growth"], "linear trend of the Solow residual, per cent a year"),
        ("stable_root", float(np.real(sol["roots"][np.abs(sol["roots"]) < 1][0])), "capital's root in the log-linear model"),
        ("unstable_root", float(np.real(sol["roots"][np.abs(sol["roots"]) > 1][0])), "consumption's root"),
    ]
    pd.DataFrame(calibration, columns=["name", "value", "description"]).to_csv(data.OUTPUT / "calibration.csv", index=False)
    residual.to_csv(data.OUTPUT / "solow_residual.csv", index=False)

    table, latest = compare(d, p)
    table.to_csv(data.OUTPUT / "moments.csv", index=False)

    irf = pd.DataFrame(100 * model.impulse_response(p), columns=model.VARIABLES)
    irf.insert(0, "quarter", irf.index)
    irf.to_csv(data.OUTPUT / "impulse_responses.csv", index=False)

    h = history(d, p, residual)
    h.to_csv(data.OUTPUT / "history.csv", index=False)
    q = h.set_index("quarter")
    lows = pd.DataFrame([{"recession": name, "start": a, "end": b, **q.loc[a:b, ["data_y", "model_y", "data_h", "model_h"]].min()}
                         for name, (a, b) in RECESSIONS.items()])
    lows.to_csv(data.OUTPUT / "recession_lows.csv", index=False)  # lowest cycle value inside each recession, per cent
    sd = table[table.statistic == "sd"].set_index("variable")
    summary = {"sample": f"{SAMPLE[0]}-{SAMPLE[1]}", "quarters": len(residual), "latest_quarter": str(latest),
               "simulations": SIMULATIONS,
               "output_sd_ratio": sd.model.y / sd.data.y, "output_variance_ratio": (sd.model.y / sd.data.y) ** 2,
               "hours_sd_ratio": sd.model.h / sd.data.h,
               "history_corr_output": h.data_y.corr(h.model_y), "history_corr_hours": h.data_h.corr(h.model_h),
               "history_sd_ratio_output": h.model_y.std() / h.data_y.std(),
               "history_sd_ratio_hours": h.model_h.std() / h.data_h.std()}
    pd.Series(summary).rename_axis("name").rename("value").to_csv(data.OUTPUT / "summary.csv")


if __name__ == "__main__":
    main()
