"""A standard real business cycle model: steady state, log-linear solution, impulse responses and simulation.

A household values log(c) + theta log(1 - h) each quarter, discounted by beta, where h is the share of its time spent
working. Output is y = z k^alpha h^(1 - alpha), and is consumed or invested: c + i = y, k' = (1 - delta) k + i.
Technology follows log z' = rho log z + e', with e' normal with standard deviation sigma.

The solution is in log deviations from the steady state. The state is s = (k, z); every other variable is a linear
function of it, x = G s, and the state moves as s' = P s + (0, e').
"""
import numpy as np

VARIABLES = ["y", "c", "i", "h", "k", "z", "y_h"]  # y_h is output per hour


def steady_state(alpha, beta, delta, h, **_):
    """Levels at z = 1. theta, the weight on leisure, is set so that the household works the share h of its time."""
    ky = alpha / (1 / beta - 1 + delta)  # capital over quarterly output, from the Euler equation
    k = h * ky ** (1 / (1 - alpha))      # y = k^alpha h^(1 - alpha), so k / h = (k / y)^(1 / (1 - alpha))
    y = k / ky
    i = delta * k
    c = y - i
    theta = (1 - alpha) * (y / h) * (1 - h) / c
    return {"y": y, "c": c, "i": i, "h": h, "k": k, "z": 1.0, "theta": theta}


def equations(p, theta, now, nxt):
    """Residuals of the equilibrium conditions, each scaled to be unit-free. now holds y, c, i, h, k, z in levels for
    one quarter and nxt holds y, c, k for the next. The Euler equation is the one without uncertainty."""
    a, b, d = p["alpha"], p["beta"], p["delta"]
    return np.array([
        theta * now["c"] / (1 - now["h"]) / ((1 - a) * now["y"] / now["h"]) - 1,  # leisure against consumption
        b * now["c"] / nxt["c"] * (a * nxt["y"] / nxt["k"] + 1 - d) - 1,          # consumption today against tomorrow
        now["z"] * now["k"] ** a * now["h"] ** (1 - a) / now["y"] - 1,            # production
        (now["c"] + now["i"]) / now["y"] - 1,                                     # output is consumed or invested
        ((1 - d) * now["k"] + now["i"]) / nxt["k"] - 1,                           # capital accumulation
    ])


def solve(p):
    """Log-linearise and solve by Blanchard and Kahn (1980).

    The two hours and output conditions are solved out, leaving A E[x'] = B x + C z for x = (k, c). Capital is
    predetermined and consumption can jump, so a unique stable solution needs exactly one root of A^-1 B inside the
    unit circle. Consumption is then the combination of k and z that keeps the unstable root from exploding."""
    a, d, rho = p["alpha"], p["delta"], p["rho"]
    ss = steady_state(**p)
    ky, sc, h = ss["k"] / ss["y"], ss["c"] / ss["y"], ss["h"]
    # Labour: c + h / (1 - h) * h_hat = y - h_hat with y = z + a k + (1 - a) h, so h = (z + a k - c) / eta.
    eta = h / (1 - h) + a
    yk, yc, yz = a * (1 + (1 - a) / eta), -(1 - a) / eta, 1 + (1 - a) / eta  # output in terms of k, c and z
    g = p["beta"] * a / ky  # elasticity of the gross return on capital to the output-capital ratio
    # Row 1: resource constraint, k' = (1 - d) k + (y - sc c) / ky. Row 2: Euler, c = E[c'] - g E[y' - k'].
    A = np.array([[1, 0], [-g * (yk - 1), 1 - g * yc]])
    B = np.array([[1 - d + yk / ky, (yc - sc) / ky], [0, 1]])
    C = np.array([yz / ky, g * yz * rho])
    M, N = np.linalg.solve(A, B), np.linalg.solve(A, C)
    roots, vectors = np.linalg.eig(M)
    stable = np.abs(roots) < 1
    if stable.sum() != 1:
        raise ValueError(f"Blanchard-Kahn conditions fail: roots {roots}")
    roots, vectors = roots.real, vectors.real  # one root inside the unit circle and one outside, so both are real
    u = np.flatnonzero(~stable)[0]
    w = np.linalg.inv(vectors)[u]  # left eigenvector: w x' = root w x + w N z, solved forward
    c_k = -w[0] / w[1]
    c_z = -(w @ N) / ((roots[u] - rho) * w[1])
    k_next = np.array([M[0, 0] + M[0, 1] * c_k, M[0, 1] * c_z + N[0]])
    c = np.array([c_k, c_z])
    hours = (np.array([a, 1]) - c) / eta
    y = np.array([a, 1]) + (1 - a) * hours
    G = np.vstack([y, c, (y - sc * c) / (1 - sc), hours, [1, 0], [0, 1], y - hours])
    P = np.array([k_next, [0, rho]])
    return {"G": G, "P": P, "roots": roots, "M": M, "steady_state": ss}


def impulse_response(p, quarters=40):
    """Response to a one-standard-deviation technology shock in quarter 0, in log deviations."""
    sol = solve(p)
    s, path = np.array([0.0, p["sigma"]]), []
    for _ in range(quarters + 1):
        path.append(sol["G"] @ s)
        s = sol["P"] @ s
    return np.array(path)


def simulate(p, quarters, samples=1, burn=200, seed=0, z=None):
    """Simulated paths of every variable, shape (samples, quarters, variables), each sample after a burn-in.
    Passing z (shape (quarters,)) feeds in a given technology path instead, starting from steady-state capital."""
    sol = solve(p)
    G, P = sol["G"], sol["P"]
    if z is None:
        e = np.random.default_rng(seed).normal(0, p["sigma"], (samples, burn + quarters))
    else:
        burn, e = 0, np.r_[z[0], z[1:] - p["rho"] * z[:-1]][None, :]
    s = np.zeros((len(e), 2))
    out = np.empty((len(e), burn + quarters, len(G)))
    for t in range(burn + quarters):
        if t:
            s = s @ P.T
        s[:, 1] += e[:, t]
        out[:, t] = s @ G.T
    return out[:, burn:]
