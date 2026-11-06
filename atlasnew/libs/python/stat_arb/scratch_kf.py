import pandas as pd
import numpy as np
import statsmodels.api as sm
from pykalman import KalmanFilter

x = pd.Series(np.random.randn(100))
y = 2.5 * x + np.random.randn(100) * 0.1

obs_mat = sm.add_constant(x.values, prepend=False)[:, np.newaxis, :]

kf = KalmanFilter(
    n_dim_obs=1, n_dim_state=2,
    initial_state_mean=[0, 0],
    initial_state_covariance=np.ones((2, 2)),
    transition_matrices=np.eye(2),
    observation_matrices=obs_mat,
    observation_covariance=0.1,
    transition_covariance=np.eye(2) * 1e-5
)

state_means, _ = kf.filter(y.values)
print(state_means[-5:, 0]) # Should be close to 2.5
