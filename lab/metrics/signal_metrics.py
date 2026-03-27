"""Signal generation metrics."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class SignalMetrics:
    """Metrics for signal generation performance."""
    total_signals: int
    long_signals: int
    short_signals: int
    flat_signals: int
    long_pct: float
    short_pct: float
    avg_signal_strength: float
    avg_confidence: float


def compute_signal_metrics(signals: pd.DataFrame) -> SignalMetrics:
    """Compute signal generation metrics.
    
    Args:
        signals: DataFrame with 'direction', 'strength', 'confidence' columns
        
    Returns:
        SignalMetrics object
    """
    if signals.empty:
        return SignalMetrics(
            total_signals=0,
            long_signals=0,
            short_signals=0,
            flat_signals=0,
            long_pct=0.0,
            short_pct=0.0,
            avg_signal_strength=0.0,
            avg_confidence=0.0,
        )
    
    total = len(signals)
    long_signals = len(signals[signals["direction"] == "long"])
    short_signals = len(signals[signals["direction"] == "short"])
    flat_signals = len(signals[signals["direction"] == "flat"])
    
    return SignalMetrics(
        total_signals=total,
        long_signals=long_signals,
        short_signals=short_signals,
        flat_signals=flat_signals,
        long_pct=long_signals / total if total > 0 else 0.0,
        short_pct=short_signals / total if total > 0 else 0.0,
        avg_signal_strength=signals["strength"].mean() if "strength" in signals else 0.0,
        avg_confidence=signals["confidence"].mean() if "confidence" in signals else 0.0,
    )


def compute_signal_quality(
    signals: pd.DataFrame, 
    returns: pd.Series
) -> dict[str, float]:
    """Compute signal quality metrics (how well signals predict returns).
    
    Args:
        signals: DataFrame with 'direction' column
        returns: Series of returns aligned to signals
        
    Returns:
        Dict of quality metrics
    """
    if signals.empty or len(returns) == 0:
        return {
            "directional_accuracy": 0.0,
            "long_accuracy": 0.0,
            "short_accuracy": 0.0,
            "signal_return_correlation": 0.0,
        }
    
    signal_direction = signals["direction"].shift(1).fillna("flat")
    
    long_returns = returns[signal_direction == "long"]
    short_returns = returns[signal_direction == "short"]
    
    long_accuracy = (long_returns > 0).mean() if len(long_returns) > 0 else 0.0
    short_accuracy = (short_returns < 0).mean() if len(short_returns) > 0 else 0.0
    
    direction_map = {"long": 1, "short": -1, "flat": 0}
    signal_numeric = signals["direction"].map(direction_map).fillna(0)
    
    correlation = signal_numeric.corr(returns) if len(returns) > 1 else 0.0
    
    return {
        "directional_accuracy": (long_accuracy + short_accuracy) / 2,
        "long_accuracy": long_accuracy,
        "short_accuracy": short_accuracy,
        "signal_return_correlation": correlation,
    }
