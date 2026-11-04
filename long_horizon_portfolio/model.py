"""Kim and Omberg (1996): an investor with CRRA utility over wealth at a fixed horizon, a constant short rate r,
and a stock whose risk premium x follows an Ornstein-Uhlenbeck process:

    dS/S = (r + x) dt + sigma dZ_s
    dx   = kappa (xbar - x) dt + sigma_x dZ_x,      dZ_s dZ_x = rho dt

With tau years to the horizon the value function is

    J(W, x, tau) = W^(1-g) / (1-g) * exp(A(tau) + B(tau) x + C(tau) x^2 / 2)

and the optimal share of wealth in stocks is

    pi = x / (g sigma^2)  +  rho sigma_x (B + C x) / (g sigma)
         myopic              intertemporal hedging

Putting J into the HJB equation and matching powers of x gives, with d = (1 - g) / g and A(0) = B(0) = C(0) = 0,

    C' = a + b C + c C^2,     a = d / sigma^2,  b = 2 (d rho sigma_x / sigma - kappa),  c = sigma_x^2 (1 + d rho^2)
    B' = (b / 2 + c C) B + kappa xbar C
    A' = (1 - g) r + kappa xbar B + sigma_x^2 ((1 + d rho^2) B^2 + C) / 2

A does not enter the share. It is solved only to check the HJB equation in the tests.
"""
from typing import NamedTuple

import numpy as np
from scipy.integrate import solve_ivp


class Params(NamedTuple):
    kappa: float    # speed of mean reversion of the premium, per year
    xbar: float     # long-run premium
    sigma: float    # stock volatility
    sigma_x: float  # volatility of the premium
    rho: float      # correlation between stock and premium shocks


def riccati(p, gamma):
    d = (1 - gamma) / gamma
    return d / p.sigma**2, 2 * (d * p.rho * p.sigma_x / p.sigma - p.kappa), p.sigma_x**2 * (1 + d * p.rho**2)


def closed_form(p, gamma, tau):
    """B(tau) and C(tau) in closed form.

    For g >= 1, a <= 0 < c, so b^2 - 4ac > 0 and this is Kim and Omberg's 'normal' case: B and C stay finite at
    every horizon. For g < 1 the discriminant can be negative; the complex square root then turns cosh and sinh
    into cos and sin, and the solution can explode at a finite horizon. That region is not used here.
    """
    a, b, c = riccati(p, gamma)
    tau = np.asarray(tau, float)
    eta = np.sqrt(complex(b * b - 4 * a * c)) or 1e-12  # eta = 0 needs kappa = 0 and a c = 0: then B = 0 and C = a tau, which these formulas give
    ch, sh = np.cosh(eta * tau / 2), np.sinh(eta * tau / 2)
    den = eta * ch - b * sh
    C = 2 * a * sh / den
    B = p.kappa * p.xbar * 4 * a * (ch - 1) / (eta * den)
    return B.real, C.real


def numerical(p, gamma, tau, r=0.0):
    """A(tau), B(tau) and C(tau) by integrating the ODEs."""
    a, b, c = riccati(p, gamma)
    d = (1 - gamma) / gamma

    def rhs(_, y):
        A, B, C = y
        return [(1 - gamma) * r + p.kappa * p.xbar * B + p.sigma_x**2 * ((1 + d * p.rho**2) * B**2 + C) / 2,
                (b / 2 + c * C) * B + p.kappa * p.xbar * C,
                a + b * C + c * C**2]

    tau = np.atleast_1d(np.asarray(tau, float))
    sol = solve_ivp(rhs, (0, tau.max()), [0.0, 0.0, 0.0], t_eval=tau, method="DOP853", rtol=1e-11, atol=1e-13)
    return sol.y


def share(p, gamma, x, tau, numeric=False):
    """Myopic and hedging shares of wealth in stocks, for premium x and tau years to the horizon."""
    B, C = numerical(p, gamma, tau)[1:] if numeric else closed_form(p, gamma, tau)
    return x / (gamma * p.sigma**2), p.rho * p.sigma_x * (B + C * x) / (gamma * p.sigma)
