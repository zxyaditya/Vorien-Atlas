import numpy as np
import pandas as pd
import statsmodels.api as sm

def estimate_ou_parameters(spread, dt=1.0):
    # S_t = a + b * S_{t-1} + e
    y = spread.values[1:]
    x = spread.values[:-1]
    
    x_const = sm.add_constant(x)
    model = sm.OLS(y, x_const).fit()
    
    a = model.params[0]
    b = model.params[1]
    sigma_e = np.sqrt(model.mse_resid)
    
    theta = -np.log(b) / dt
    mu = a / (1 - b)
    sigma = sigma_e * np.sqrt(2 * theta / (1 - np.exp(-2 * theta * dt)))
    
    sigma_eq = sigma / np.sqrt(2 * theta)
    half_life = np.log(2) / theta
    
    return mu, theta, sigma, sigma_eq, half_life

# Test with synthetic OU process
np.random.seed(42)
dt = 1.0
theta_true = 0.1
mu_true = 2.0
sigma_true = 0.5
n = 1000

s = np.zeros(n)
s[0] = mu_true
for i in range(1, n):
    s[i] = s[i-1] + theta_true * (mu_true - s[i-1]) * dt + sigma_true * np.random.normal(0, np.sqrt(dt))

spread = pd.Series(s)
mu, theta, sigma, sigma_eq, half_life = estimate_ou_parameters(spread)

print(f"True: mu={mu_true}, theta={theta_true}, sigma={sigma_true}")
print(f"Est:  mu={mu:.4f}, theta={theta:.4f}, sigma={sigma:.4f}, sigma_eq={sigma_eq:.4f}, hl={half_life:.2f}")
