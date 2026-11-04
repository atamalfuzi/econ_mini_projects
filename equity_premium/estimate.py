"""Return and consumption moments, the Mehra-Prescott economy, the Hansen-Jagannathan bound and rare disasters."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq

import data
import model

# Return samples. Consumption growth is available for 1889-2007 only, so consumption moments use the overlap.
SAMPLES = [(1871, 2011), (1889, 2007), (1889, 1978), (1871, 1949), (1950, 2011)]
HJ_SAMPLES = [(1889, 2007), (1889, 1978), (1889, 1949), (1950, 2007)]  # years with both returns and consumption
# Mehra and Prescott (1985), Table 1 and section 3, 1889-1978: arithmetic means of annual real returns.
MEHRA_PRESCOTT = {"stock_mean": 0.0698, "bill_mean": 0.0080, "premium": 0.0618,
                  "consumption_mean": 0.0183, "consumption_sd": 0.0357, "consumption_autocorr": -0.14}
GAMMAS = np.round(np.arange(0.5, 50.01, 0.5), 2)
BETAS = (0.96, 0.99)
DISASTER_GAMMAS = (3, 4, 5)
PROBS = np.round(np.arange(0, 0.0501, 0.001), 3)
SIZES = np.round(np.arange(0, 0.601, 0.02), 2)
BARRO = (0.017, 0.29)  # Barro (2006): disasters 1.7% a year; per capita GDP falls of 15% to 64%, 29% on average
FIXED_BETA = 0.97      # Barro's 3% rate of time preference, used only to show how disasters move the risk-free rate


def crossing(f, xs):
    """First upward root of f on the grid xs, refined by brentq. NaN values (infinite prices) never count."""
    v = np.array([f(x) for x in xs])
    i = np.flatnonzero((v[:-1] < 0) & (v[1:] >= 0))
    return brentq(f, xs[i[0]], xs[i[0] + 1]) if len(i) else np.nan


def moments(d, first, last):
    s = d[d.year.between(first, last)]
    r, c = s.dropna(subset=["excess"]), s.dropna(subset=["excess", "consumption_growth"])
    return {"sample": f"{first}-{last}", "years": len(r),
            "stock_mean": r.stock.mean(), "stock_sd": r.stock.std(), "stock_geometric": np.expm1(np.log1p(r.stock).mean()),
            "bill_mean": r.bill.mean(), "bill_sd": r.bill.std(), "bill_geometric": np.expm1(np.log1p(r.bill).mean()),
            "premium": r.excess.mean(), "excess_sd": r.excess.std(), "sharpe": r.excess.mean() / r.excess.std(),
            "consumption_years": f"{c.year.min()}-{c.year.max()}",
            "consumption_mean": c.consumption_growth.mean(), "consumption_sd": c.consumption_growth.std(),
            "consumption_autocorr": s.consumption_growth.autocorr(),
            "corr_stock": c.consumption_growth.corr(c.stock), "corr_excess": c.consumption_growth.corr(c.excess),
            "corr_stock_end": s.consumption_growth_end.corr(s.stock)}


def hj_ratio(growth, gamma):
    """sigma(m)/E(m) for m = beta (C'/C)^-gamma, using the sample distribution of growth; beta cancels."""
    m = np.asarray(growth) ** -gamma
    return m.std(ddof=1) / m.mean()


def hansen_jagannathan(d, first, last):
    s = d[d.year.between(first, last)].dropna(subset=["excess", "consumption_growth"])
    x, sharpe = 1 + s.consumption_growth, s.excess.mean() / s.excess.std()
    gamma = brentq(lambda g: hj_ratio(x, g) - sharpe, 0.01, 200)
    return {"sample": f"{first}-{last}", "years": len(s), "sharpe": sharpe, "gamma_bound": gamma,
            # beta that also gives E(m) = 1 / E(1 + risk-free rate) at that gamma
            "beta_at_bound": 1 / ((1 + s.bill.mean()) * np.mean(x ** -gamma)),
            "gamma_lognormal": sharpe / np.log(x).std(),
            # first-order approximation E(R - Rf) = gamma cov(growth, R - Rf), so correlation counts as well
            "gamma_covariance": s.excess.mean() / np.cov(s.consumption_growth, s.excess)[0, 1]}


def calibrations(m):
    """Consumption growth moments and return targets for the two-state chain."""
    rows = {"Mehra-Prescott published": MEHRA_PRESCOTT}
    rows |= {k: m.set_index("sample").loc[k] for k in ("1889-1978", "1889-2007")}
    return {k: (v["consumption_mean"], v["consumption_sd"], v["consumption_autocorr"], v["bill_mean"], v["premium"])
            for k, v in rows.items()}


def mehra_prescott(cal):
    """The two-state economy over a grid of gamma, with beta fixed or set to match the risk-free rate ("riskfree")."""
    grid, summary = [], []
    for name, (mean, sd, rho, rf, premium) in cal.items():
        x, P = model.two_state(mean, sd, rho)
        rules = {b: (lambda g, b=b: b) for b in BETAS} | {"riskfree": lambda g, x=x, P=P, rf=rf: model.riskfree_beta(x, P, g, rf)}
        for rule, beta in rules.items():
            for g in GAMMAS:
                grid.append({"calibration": name, "beta_rule": str(rule)} | model.price(x, P, beta(g), g))
        gap = lambda beta: lambda g: model.price(x, P, beta(g), g)["premium"] - premium
        g99, g_rf = crossing(gap(rules[0.99]), GAMMAS), crossing(gap(rules["riskfree"]), GAMMAS)
        at99 = model.price(x, P, 0.99, g99)
        # Mehra and Prescott's admissible region: gamma up to 10, beta below 1, risk-free rate at most 4%.
        region = [model.price(x, P, b, g) for g in np.linspace(0.05, 10, 200) for b in np.linspace(0.8, 0.9999, 60)]
        best = np.nanmax([r["premium"] for r in region if r["riskfree"] <= 0.04])
        summary.append({"calibration": name, "growth_mean": mean, "growth_sd": sd, "growth_autocorr": rho,
                        "target_riskfree": rf, "target_premium": premium,
                        "premium_gamma10_beta099": model.price(x, P, 0.99, 10)["premium"],
                        "riskfree_gamma10_beta099": model.price(x, P, 0.99, 10)["riskfree"],
                        "gamma_needed_beta099": g99, "riskfree_at_gamma_needed": at99["riskfree"],
                        "equity_sd_at_gamma_needed": at99["equity_sd"],
                        "beta_for_riskfree_at_gamma_needed": model.riskfree_beta(x, P, g99, rf),
                        "gamma_needed_beta_matched": g_rf, "max_premium_mp_region": best})
    return pd.DataFrame(grid), pd.DataFrame(summary)


def disasters(cal):
    """Three-state chain: the 1889-2007 two-state chain plus a disaster state. beta is set in every case so the
    mean risk-free rate equals the 1889-2007 average; a case is admissible if that beta is below one."""
    mean, sd, rho, rf, premium = cal["1889-2007"]
    x0, P0 = model.two_state(mean, sd, rho)

    def solve(gamma, prob, size):
        x, P = model.with_disaster(x0, P0, prob, size)
        return (model.price(x, P, model.riskfree_beta(x, P, gamma, rf), gamma)
                | {"riskfree_fixed_beta": model.price(x, P, FIXED_BETA, gamma)["riskfree"]})

    def size_needed(gamma, prob):
        """Smallest disaster size that gives the data's premium (premium rises with size until prices explode)."""
        b = crossing(lambda b: solve(gamma, prob, b)["premium"] - premium, np.linspace(0, 0.9, 181))
        return b, (solve(gamma, prob, b) if b == b else {"beta": np.nan, "equity_sd": np.nan, "riskfree_fixed_beta": np.nan})

    grid = [{"gamma": g, "prob": p, "size": b} | solve(g, p, b) for g in DISASTER_GAMMAS for p in PROBS for b in SIZES]
    match = []
    for g in DISASTER_GAMMAS:
        for p in PROBS[PROBS > 0]:
            b, r = size_needed(g, p)
            match.append({"gamma": g, "prob": p, "size_needed": b, "beta": r["beta"], "equity_sd": r["equity_sd"],
                          "riskfree_fixed_beta": r["riskfree_fixed_beta"]})
    summary = []
    for g in DISASTER_GAMMAS:
        none, barro = solve(g, 0.0, 0.0), solve(g, *BARRO)
        b, r = size_needed(g, BARRO[0])
        summary.append({"gamma": g, "target_premium": premium, "target_riskfree": rf,
                        "premium_no_disaster": none["premium"], "beta_no_disaster": none["beta"],
                        "riskfree_fixed_beta_no_disaster": none["riskfree_fixed_beta"],
                        "premium_barro": barro["premium"], "beta_barro": barro["beta"],
                        "riskfree_fixed_beta_barro": barro["riskfree_fixed_beta"],
                        "size_needed_at_barro_prob": b, "beta_at_size_needed": r["beta"],
                        "riskfree_fixed_beta_at_size_needed": r["riskfree_fixed_beta"],
                        "equity_sd_at_size_needed": r["equity_sd"]})
    return pd.DataFrame(grid), pd.DataFrame(match), pd.DataFrame(summary)


def annual(d):
    a = d[d.year.between(1871, 2011)][["year", "stock", "bill", "excess", "consumption_growth"]].copy()
    a["stock_wealth"], a["bill_wealth"] = (1 + a.stock).cumprod(), (1 + a.bill).cumprod()  # $1 in January 1871
    a["premium_30y"] = a.excess.rolling(30).mean()  # average over the 30 years ending with this one
    return a


def main():
    d = data.load()
    data.OUTPUT.mkdir(exist_ok=True)
    m = pd.DataFrame([moments(d, *s) for s in SAMPLES])
    m.to_csv(data.OUTPUT / "moments.csv", index=False)
    here = m.set_index("sample").loc["1889-1978"]
    pd.DataFrame([{"measure": k, "published": v, "here": here[k], "gap": here[k] - v} for k, v in MEHRA_PRESCOTT.items()]
                 ).to_csv(data.OUTPUT / "mehra_prescott_check.csv", index=False)
    annual(d).to_csv(data.OUTPUT / "annual.csv", index=False)
    pd.DataFrame([hansen_jagannathan(d, *s) for s in HJ_SAMPLES]).to_csv(data.OUTPUT / "hansen_jagannathan.csv", index=False)
    curve = [{"sample": f"{a}-{b}", "gamma": g,
              "ratio": hj_ratio(1 + d[d.year.between(a, b)].dropna(subset=["excess", "consumption_growth"]).consumption_growth, g)}
             for a, b in HJ_SAMPLES for g in np.arange(0, 30.01, 0.25)]
    pd.DataFrame(curve).to_csv(data.OUTPUT / "hj_curve.csv", index=False)
    cal = calibrations(m)
    grid, summary = mehra_prescott(cal)
    grid.to_csv(data.OUTPUT / "mp_grid.csv", index=False)
    summary.to_csv(data.OUTPUT / "mp_summary.csv", index=False)
    grid, match, summary = disasters(cal)
    grid.to_csv(data.OUTPUT / "disaster_grid.csv", index=False, float_format="%.6g")
    match.to_csv(data.OUTPUT / "disaster_match.csv", index=False)
    summary.to_csv(data.OUTPUT / "disaster_summary.csv", index=False)


if __name__ == "__main__":
    main()
