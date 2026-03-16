"""HMM-based market regime detection.

Fits a 3-state Gaussian HMM on observable market features to classify each bar
into one of three regimes:

  trending       - directional moves with moderate volatility
  mean_reverting - range-bound, low volatility, returns revert to zero
  volatile       - high volatility, no clear direction (crisis / chop)

The state labels are assigned after fitting by inspecting the learned means
and covariances: the state with the highest absolute mean return is 'trending',
the one with highest volatility but low mean is 'volatile', and the remaining
state is 'mean_reverting'.

Usage:
    from data.regime import detect_regimes
    regimes = detect_regimes(df)  # returns pd.Series aligned to df.index
"""

from enum import Enum

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM


class Regime(Enum):
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    VOLATILE = "volatile"


# Feature construction parameters
_LOG_RETURN_COL = "log_return"
_VOLATILITY_COL = "rolling_vol"
_AUTOCORR_COL = "return_autocorr"
_ROLLING_WINDOW = 20


def _build_features(df: pd.DataFrame, window: int = _ROLLING_WINDOW) -> pd.DataFrame:
    """Construct observable features for the HMM from OHLCV data."""
    close = df["Close"]

    features = pd.DataFrame(index=df.index)
    features[_LOG_RETURN_COL] = np.log(close / close.shift(1))
    features[_VOLATILITY_COL] = features[_LOG_RETURN_COL].rolling(window).std()
    features[_AUTOCORR_COL] = (
        features[_LOG_RETURN_COL]
        .rolling(window)
        .apply(lambda x: x.autocorr(lag=1) if len(x.dropna()) > 2 else 0.0, raw=False)
    )

    features.dropna(inplace=True)
    return features


def _label_states(model: GaussianHMM, n_states: int = 3) -> dict[int, Regime]:
    """Map HMM state indices to Regime labels using learned parameters.

    Heuristic:
      - Trending: highest |mean log return|
      - Volatile: highest volatility mean among the remaining states
      - Mean-reverting: the leftover state
    """
    means = model.means_  # shape (n_states, n_features)
    abs_return_mean = np.abs(means[:, 0])
    vol_mean = means[:, 1]

    trending_idx = int(np.argmax(abs_return_mean))

    remaining = [i for i in range(n_states) if i != trending_idx]
    volatile_idx = remaining[int(np.argmax([vol_mean[i] for i in remaining]))]

    mean_rev_idx = [i for i in remaining if i != volatile_idx][0]

    return {
        trending_idx: Regime.TRENDING,
        volatile_idx: Regime.VOLATILE,
        mean_rev_idx: Regime.MEAN_REVERTING,
    }


def detect_regimes(
    df: pd.DataFrame,
    n_states: int = 3,
    window: int = _ROLLING_WINDOW,
    n_iter: int = 100,
    random_state: int = 42,
) -> pd.Series:
    """Fit an HMM and return a Regime label per bar.

    Args:
        df: OHLCV DataFrame with at least a 'Close' column.
        n_states: Number of hidden states (default 3).
        window: Rolling window for feature construction.
        n_iter: Max EM iterations for fitting.
        random_state: Seed for reproducibility.

    Returns:
        pd.Series of Regime values, indexed to match `df` (NaN-rows from
        feature construction are excluded — the series is shorter than df).
    """
    features = _build_features(df, window=window)
    X = features.values

    model = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=n_iter,
        random_state=random_state,
    )
    model.fit(X)
    hidden_states = model.predict(X)

    label_map = _label_states(model, n_states)
    labels = pd.Series(
        [label_map[s] for s in hidden_states],
        index=features.index,
        name="regime",
    )
    return labels
