"""Regime detection metrics."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from collections import Counter


@dataclass
class RegimeMetrics:
    """Metrics for regime detection performance."""
    total_regime_changes: int
    most_common_regime: str
    regime_distribution: dict[str, int]
    regime_pct: dict[str, float]
    avg_regime_duration: float
    avg_confidence: float


def compute_regime_metrics(regime_events: list[dict]) -> RegimeMetrics:
    """Compute regime detection metrics.
    
    Args:
        regime_events: List of regime event dicts with 'regime' and 'confidence'
        
    Returns:
        RegimeMetrics object
    """
    if not regime_events:
        return RegimeMetrics(
            total_regime_changes=0,
            most_common_regime="unknown",
            regime_distribution={},
            regime_pct={},
            avg_regime_duration=0.0,
            avg_confidence=0.0,
        )
    
    regimes = [e.get("regime", "unknown") for e in regime_events]
    confidences = [e.get("confidence", 0.0) for e in regime_events]
    
    regime_counts = Counter(regimes)
    total = len(regimes)
    
    regime_dist = dict(regime_counts)
    regime_pct = {k: v / total for k, v in regime_counts.items()}
    
    regime_changes = 0
    prev_regime = None
    for regime in regimes:
        if prev_regime is not None and regime != prev_regime:
            regime_changes += 1
        prev_regime = regime
    
    most_common = regime_counts.most_common(1)[0][0] if regime_counts else "unknown"
    
    return RegimeMetrics(
        total_regime_changes=regime_changes,
        most_common_regime=most_common,
        regime_distribution=regime_dist,
        regime_pct=regime_pct,
        avg_regime_duration=0.0,
        avg_confidence=np.mean(confidences) if confidences else 0.0,
    )


def compute_regime_returns(
    regime_events: list[dict],
    returns: pd.Series
) -> dict[str, dict[str, float]]:
    """Compute returns by regime.
    
    Args:
        regime_events: List of regime event dicts
        returns: Series of returns aligned to regime events
        
    Returns:
        Dict mapping regime to return metrics
    """
    if not regime_events or len(returns) == 0:
        return {}
    
    regime_returns = {}
    
    for i in range(len(regime_events) - 1):
        regime = regime_events[i].get("regime", "unknown")
        if regime not in regime_returns:
            regime_returns[regime] = []
        regime_returns[regime].append(returns.iloc[i])
    
    result = {}
    for regime, rets in regime_returns.items():
        if rets:
            result[regime] = {
                "mean": np.mean(rets),
                "std": np.std(rets),
                "sharpe": np.mean(rets) / np.std(rets) * np.sqrt(252) if np.std(rets) > 0 else 0.0,
                "count": len(rets),
            }
    
    return result


def compute_regime_stability(regime_events: list[dict], window: int = 5) -> float:
    """Compute regime stability score (0-1).
    
    Higher score = more stable regimes.
    
    Args:
        regime_events: List of regime event dicts
        window: Window size for stability calculation
        
    Returns:
        Stability score
    """
    if not regime_events or len(regime_events) < window:
        return 0.0
    
    regimes = [e.get("regime", "unknown") for e in regime_events]
    
    stability_scores = []
    for i in range(len(regimes) - window + 1):
        window_regimes = regimes[i:i + window]
        unique = len(set(window_regimes))
        stability_scores.append(1.0 / unique if unique > 0 else 0.0)
    
    return np.mean(stability_scores) if stability_scores else 0.0
