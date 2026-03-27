"""Synthetic market data generator using Geometric Brownian Motion."""

from __future__ import annotations

import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from typing import Literal


class SyntheticGenerator:
    """Generate synthetic OHLCV data from YAML config."""

    def __init__(self, config_path: str | Path):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str | Path) -> dict:
        with open(config_path) as f:
            return yaml.safe_load(f)

    def generate(self, seed: int | None = None) -> pd.DataFrame:
        config_type = self.config.get("type", "gbm")
        if config_type == "gbm":
            return self._generate_gbm(seed)
        else:
            raise ValueError(f"Unknown synthetic type: {config_type}")

    def _generate_gbm(self, seed: int | None = None) -> pd.DataFrame:
        bars = self.config["bars"]
        interval = self.config["interval"]
        drift = self.config.get("drift", 0.0)
        vol = self.config["volatility"]
        config_seed = self.config.get("seed", 42)
        seed = seed if seed is not None else config_seed

        rng = np.random.default_rng(seed)

        dt = self._interval_to_dt(interval)
        n = bars

        returns = rng.normal(loc=drift * dt, scale=vol * np.sqrt(dt), size=n)
        returns = self._maybe_inject_spikes(returns)
        returns = self._maybe_inject_gaps(returns)

        price = self.config.get("initial_price", 100.0)
        close_prices = [price]
        for r in returns[1:]:
            price = price * np.exp(r)
            close_prices.append(price)

        close = np.array(close_prices)

        high = close * (1 + np.abs(rng.normal(0, 0.0002, n)))
        low = close * (1 - np.abs(rng.normal(0, 0.0002, n)))
        open_prices = np.roll(close, 1)
        open_prices[0] = close[0]

        volume = rng.integers(1000, 10000, size=n).astype(float)

        timestamps = pd.date_range(
            start="2024-01-01 00:00:00",
            periods=n,
            freq=self._interval_to_freq(interval),
        )

        df = pd.DataFrame(
            {
                "Open": open_prices,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            },
            index=timestamps,
        )
        df.index.name = "timestamp"

        return df

    def _maybe_inject_spikes(self, returns: np.ndarray) -> np.ndarray:
        spike_at = self.config.get("spike_at_bar")
        multiplier = self.config.get("spike_multiplier", 1.0)
        duration = self.config.get("spike_duration", 100)

        if spike_at and multiplier > 1.0:
            end = min(spike_at + duration, len(returns))
            returns[spike_at:end] *= multiplier

        return returns

    def _maybe_inject_gaps(self, returns: np.ndarray) -> np.ndarray:
        gap_prob = self.config.get("gap_probability", 0.0)
        gap_mag = self.config.get("gap_magnitude", 0.0)

        if gap_prob > 0 and gap_mag > 0:
            mask = np.random.random(len(returns)) < gap_prob
            returns[mask] += np.random.choice([-gap_mag, gap_mag], size=mask.sum())

        return returns

    def _interval_to_dt(self, interval: str) -> float:
        mapping = {
            "M1": 1 / 1440,
            "1m": 1 / 1440,
            "5m": 5 / 1440,
            "15m": 15 / 1440,
            "1H": 1 / 24,
            "1h": 1 / 24,
            "4H": 4 / 24,
            "4h": 4 / 24,
            "1D": 1.0,
            "1d": 1.0,
        }
        return mapping.get(interval, 1 / 1440)

    def _interval_to_freq(self, interval: str) -> str:
        mapping = {
            "M1": "1min",
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1H": "1h",
            "1h": "1h",
            "4H": "4h",
            "4h": "4h",
            "1D": "1D",
            "1d": "1D",
        }
        return mapping.get(interval, "1min")


def generate(config_path: str | Path, seed: int | None = None) -> pd.DataFrame:
    """Convenience function."""
    return SyntheticGenerator(config_path).generate(seed)
