"""Asset prices in an exchange economy where consumption growth follows a finite-state Markov chain.

The setting is Mehra and Prescott (1985): a representative agent with power utility, u(c) = c^(1-gamma)/(1-gamma),
discount factor beta, and equity that is a claim to aggregate consumption. Growth x(t+1) = C(t+1)/C(t) takes
values x[j] with transition probabilities P[i, j]. Returns are gross and real; means are over the chain's
stationary distribution.
"""
import numpy as np


def two_state(mean, sd, autocorr):
    """Mehra and Prescott's symmetric chain: growth 1 + mean + sd or 1 + mean - sd, staying in the same state
    with probability phi = (1 + autocorr) / 2. Its stationary mean, s.d. and autocorrelation are the inputs."""
    phi = (1 + autocorr) / 2
    return np.array([1 + mean + sd, 1 + mean - sd]), np.array([[phi, 1 - phi], [1 - phi, phi]])


def stationary(P):
    values, vectors = np.linalg.eig(P.T)
    pi = np.real(vectors[:, np.argmin(np.abs(values - 1))])
    return pi / pi.sum()


def with_disaster(x, P, prob, size):
    """Add a disaster state in which consumption falls by `size` (Rietz 1988). Each year a disaster happens with
    probability `prob`, whatever the current state. Otherwise the economy moves as in P; after a disaster it
    returns to the normal states in their stationary proportions."""
    n = len(x)
    Q = np.zeros((n + 1, n + 1))
    Q[:n, :n] = (1 - prob) * P
    Q[n, :n] = (1 - prob) * stationary(P)
    Q[:, n] = prob
    return np.append(x, 1 - size), Q


def riskfree_beta(x, P, gamma, riskfree):
    """The beta that makes the model's mean risk-free rate equal `riskfree` (net). Rf(i) = 1 / (beta E[x^-gamma | i])."""
    return stationary(P) @ (1 / (P @ x ** -gamma)) / (1 + riskfree)


def price(x, P, beta, gamma):
    """Mean net returns on equity and the one-period riskless bond, and the equity premium.
    The price-dividend ratio w solves w(i) = beta sum_j P[i, j] x[j]^(1-gamma) (w(j) + 1). It is finite only
    when the spectral radius of beta P x^(1-gamma) is below one; otherwise the equity results are NaN."""
    A, pi = beta * P * x ** (1 - gamma), stationary(P)
    Rf = 1 / (beta * P @ x ** -gamma)
    out = {"beta": beta, "gamma": gamma, "riskfree": pi @ Rf - 1}
    if np.max(np.abs(np.linalg.eigvals(A))) >= 1:
        return out | {"equity": np.nan, "premium": np.nan, "equity_sd": np.nan}
    w = np.linalg.solve(np.eye(len(x)) - A, A.sum(axis=1))
    R = (x * (w + 1))[None, :] / w[:, None]  # R[i, j]: equity return from state i to state j
    Re = (P * R).sum(axis=1)
    sd = np.sqrt(pi @ (P * R ** 2).sum(axis=1) - (pi @ Re) ** 2)
    return out | {"equity": pi @ Re - 1, "premium": pi @ (Re - Rf), "equity_sd": sd}
