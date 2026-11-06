import numpy as np
import pandas as pd
from statsmodels.distributions.empirical_distribution import ECDF
import scipy.stats as stats
from scipy.stats import kendalltau

# Generate synthetic returns
np.random.seed(42)
ret_x = np.random.normal(0, 0.01, 1000)
# Make Y dependent on X (linear + noise)
ret_y = 0.8 * ret_x + np.random.normal(0, 0.005, 1000)

# Convert to uniform using ECDF
ecdf_x = ECDF(ret_x)
ecdf_y = ECDF(ret_y)

u = ecdf_x(ret_x)
v = ecdf_y(ret_y)

# Fit a Gaussian Copula (simplified via Kendall's Tau)
tau, _ = kendalltau(u, v)
rho = np.sin(tau * np.pi / 2) # relationship between Kendall's Tau and Pearson correlation for Gaussian Copula

print(f"Kendall's Tau: {tau:.4f}, Implied Rho: {rho:.4f}")

# Conditional probability formula for Gaussian Copula:
# P(V <= v | U = u) = Phi( (Phi^-1(v) - rho * Phi^-1(u)) / sqrt(1 - rho^2) )
u_inv = stats.norm.ppf(u[1:-1]) # avoid 0 and 1
v_inv = stats.norm.ppf(v[1:-1])

cond_prob_v_given_u = stats.norm.cdf((v_inv - rho * u_inv) / np.sqrt(1 - rho**2))

print("Min Prob:", np.min(cond_prob_v_given_u))
print("Max Prob:", np.max(cond_prob_v_given_u))
