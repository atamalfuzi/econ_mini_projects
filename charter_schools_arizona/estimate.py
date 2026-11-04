"""Difference-in-differences estimates for traditional public schools in Arizona against New Mexico."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

import data

REF = 1994                      # 1994-95: Arizona's charter law passed in 1994, the first charters opened in fall 1995
PRE = [1990, 1991, 1992, 1993]
OUTCOMES = {"white_share": "Share of students who are white non-Hispanic",
            "ptr": "Pupil-teacher ratio"}
DEE_FU = {("white_share", "none"): (-0.026, 0.004), ("white_share", "county"): (-0.009, 0.004),
          ("ptr", "none"): (1.26, 0.16)}  # Dee and Fu (2004), Tables 3 and 4, columns 1 and 2


def sample(d):
    """Regular traditional public schools. Charter schools are flagged only from 1998, so a school is dropped
    if it is ever flagged, and so is every school in a district (LEA) where most flagged rows are charters."""
    ever = d.groupby("ncessch").charter.transform(lambda s: (s == 1).any())
    lea = d.groupby("leaid").charter.transform(lambda s: (s == 1).mean() >= 0.5 if s.notna().any() else False)
    d = d[(d.school_type == 1) & ~ever & ~lea & (d.students > 0) & d.white.between(0, d.students)].copy()
    d["az"] = (d.state == "AZ").astype(int)
    d["white_share"] = d.white / d.students
    d["ptr"] = d.students / d.teachers_fte.where(d.teachers_fte > 0)
    # Dee and Fu's trim: ratios above 150% of the 99th percentile or below half the 1st percentile are errors.
    q = d.groupby("year").ptr.quantile([0.01, 0.99]).unstack()
    lo, hi = d.year.map(q[0.01]) * 0.5, d.year.map(q[0.99]) * 1.5
    d.loc[(d.ptr < lo) | (d.ptr > hi), "ptr"] = np.nan
    # Locale and level are fixed at their first observed values, so they cannot respond to treatment.
    first = d.sort_values("year").groupby("ncessch")
    locale = first.urban_centric_locale.transform(lambda s: s[s > 0].iloc[0] if (s > 0).any() else np.nan)
    d["locale"] = pd.cut(locale, [0, 2, 6, 8], labels=["city", "suburb or town", "rural"])
    low = first.lowest_grade_offered.transform("first")
    d["level"] = np.where(low.between(-1, 6) | (low == 15), "elementary", np.where(low.between(7, 12), "secondary", None))
    return d


def balanced(d, outcome, years):
    keep = d[d.year.isin(years) & d[outcome].notna()]
    n = keep.groupby("ncessch").year.transform("nunique")
    return keep[n == len(years)]


def demean(cols, groups, tol=1e-10, max_iter=1000):
    """Remove group means for two sets of fixed effects by alternating projections."""
    out = cols.copy()
    for _ in range(max_iter):
        before = out.copy()
        for g in groups:
            out = out - out.groupby(g).transform("mean")
        if np.abs(out - before).to_numpy().max() < tol:
            return out
    raise RuntimeError("demeaning did not converge")


def cluster_vcov(X, u, clusters, k):
    """Cluster-robust covariance with the usual G/(G-1) * (N-1)/(N-k) small-sample factor."""
    bread = np.linalg.inv(X.T @ X)
    scores = pd.DataFrame(X * u[:, None]).groupby(np.asarray(clusters)).sum().to_numpy()
    n, g = len(u), len(scores)
    return bread @ (scores.T @ scores) @ bread * g / (g - 1) * (n - 1) / (n - k)


def twfe(d, y, x, unit="ncessch", time="year", cluster="leaid", absorbed_k=None):
    """OLS of y on x with unit and time fixed effects; clustered standard errors.
    absorbed_k is the number of fixed effects counted in the degrees of freedom. The default counts only the
    time effects, since unit effects are nested within clusters (as Stata's areg and reghdfe do)."""
    cols = d[[y] + x].astype(float)
    dm = demean(cols, [d[unit].to_numpy(), d[time].to_numpy()])
    Y, X = dm[y].to_numpy(), dm[x].to_numpy()
    beta = np.linalg.lstsq(X, Y, rcond=None)[0]
    k = len(x) + (d[time].nunique() - 1 if absorbed_k is None else absorbed_k)
    V = cluster_vcov(X, Y - X @ beta, d[cluster], k)
    return pd.Series(beta, index=x), pd.DataFrame(V, index=x, columns=x)


def two_period(d, outcome, spec):
    """Change from 1994-95 to 1999-2000 within school, Arizona against New Mexico (Dee and Fu's design)."""
    b = balanced(d, outcome, [REF, 1999]).sort_values(["ncessch", "year"])
    if spec != "none":
        b = b[b.youth_white_share.notna()]
    first, last = b[b.year == REF].set_index("ncessch"), b[b.year == 1999].set_index("ncessch")
    X = pd.DataFrame({"const": 1.0, "az": last.az})
    if spec in ("county", "county+locale+level"):
        X["d_youth_white"] = last.youth_white_share - first.youth_white_share
    if spec == "county+locale+level":
        X = X.join(pd.get_dummies(last.locale, prefix="loc", drop_first=True, dtype=float))
        X = X.join(pd.get_dummies(last.level, prefix="lvl", drop_first=True, dtype=float))
    dy = last[outcome] - first[outcome]
    ok = X.notna().all(axis=1) & dy.notna()
    fit_hc = sm.OLS(dy[ok], X[ok]).fit(cov_type="HC1")
    fit_cl = sm.OLS(dy[ok], X[ok]).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(last.leaid[ok])[0]})
    ref = DEE_FU.get((outcome, spec), (np.nan, np.nan))
    return {"outcome": outcome, "spec": spec, "estimate": fit_hc.params.az, "se_hc1": fit_hc.bse.az,
            "se_district": fit_cl.bse.az, "schools": int(ok.sum()), "schools_az": int(last.az[ok].sum()),
            "dee_fu": ref[0], "dee_fu_se": ref[1]}


def event_study(d, outcome, control=False, balanced_panel=True, trend=False):
    """Arizona x year effects relative to 1994-95, with school and year fixed effects.
    With trend=True, Arizona gets its own linear trend, identified from 1990-91 to 1994-95 because every later
    year has its own dummy; the later effects are then deviations from that trend carried forward."""
    years = sorted(d.year.unique())
    e = d[d[outcome].notna()]
    if control:
        e = e[e.youth_white_share.notna()]
    if balanced_panel:
        e = balanced(e, outcome, years)
    e = e.copy()
    terms = []
    for t in years:
        if t != REF and not (trend and t < REF):
            e[f"az_{t}"] = e.az * (e.year == t)
            terms.append(f"az_{t}")
    extra = (["az_trend"] if trend else []) + (["youth_white_share"] if control else [])
    if trend:
        e["az_trend"] = e.az * (e.year - REF)
    beta, V = twfe(e, outcome, terms + extra)
    se = np.sqrt(np.diag(V.loc[terms, terms]))
    out = pd.DataFrame({"year": [int(t[3:]) for t in terms], "coef": beta[terms].to_numpy(), "se": se})
    out = pd.concat([out, pd.DataFrame({"year": [REF], "coef": [0.0], "se": [0.0]})]).sort_values("year")
    g = e.leaid.nunique()
    summary = {"outcome": outcome, "control": control, "balanced": balanced_panel, "trend": trend,
               "schools": e.ncessch.nunique(), "districts": g}
    if trend:
        summary.update({"pretrend_slope": beta.az_trend, "pretrend_slope_se": float(np.sqrt(V.loc["az_trend", "az_trend"]))})
    else:
        pre = [f"az_{t}" for t in PRE]
        b, v = beta[pre].to_numpy(), V.loc[pre, pre].to_numpy()
        f = float(b @ np.linalg.solve(v, b)) / len(pre)
        summary.update({"pretrend_F": f, "pretrend_p": float(stats.f.sf(f, len(pre), g - 1))})
    post = [f"az_{t}" for t in years if t >= 1999]
    w = np.ones(len(post)) / len(post)
    summary.update({"post_1999_2005_mean": float(w @ beta[post]),
                    "post_1999_2005_se": float(np.sqrt(w @ V.loc[post, post].to_numpy() @ w))})
    for i, (k, v) in enumerate([("outcome", outcome), ("control", control), ("balanced", balanced_panel), ("trend", trend)]):
        out.insert(i, k, v)
    return out, summary


def charter_share(raw):
    """Charter schools' share of public school students, from the CCD charter flag (filled from 1998-99)."""
    r = raw[raw.students > 0]
    g = r.groupby(["state", "year"])
    s = pd.DataFrame({"charter_students": g.apply(lambda x: x.students[x.charter == 1].sum()), "students": g.students.sum(),
                      "flag_filled": g.charter.apply(lambda s: s.notna().mean())}).reset_index()
    s["charter_share"] = s.charter_students / s.students
    return s


def main():
    raw = data.load()
    d = sample(raw)
    data.OUTPUT.mkdir(exist_ok=True)
    rows = [two_period(d, "white_share", s) for s in ("none", "county", "county+locale+level")]
    rows += [two_period(d, "ptr", s) for s in ("none", "county+locale+level")]
    pd.DataFrame(rows).to_csv(data.OUTPUT / "two_period.csv", index=False)
    paths, summaries = [], []
    for outcome in OUTCOMES:
        for control in (False, True):
            for bal, trend in ((True, False), (False, False), (True, True)):
                p, s = event_study(d, outcome, control, bal, trend)
                paths.append(p)
                summaries.append(s)
    pd.concat(paths).to_csv(data.OUTPUT / "event_study.csv", index=False)
    pd.DataFrame(summaries).to_csv(data.OUTPUT / "event_study_summary.csv", index=False)
    charter_share(raw).to_csv(data.OUTPUT / "charter_share.csv", index=False)
    yt = d.groupby(["state", "year"]).agg(schools=("ncessch", "nunique"), white_share=("white_share", "mean"),
                                         ptr=("ptr", "mean"), youth_white_share=("youth_white_share", "mean"))
    yt.reset_index().to_csv(data.OUTPUT / "means.csv", index=False)


if __name__ == "__main__":
    main()
