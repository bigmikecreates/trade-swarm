"""Sentiment analysis metrics."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from collections import Counter


@dataclass
class SentimentMetrics:
    """Metrics for sentiment analysis."""
    total_analyses: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_score: float
    avg_confidence: float
    sentiment_distribution: dict[str, int]
    sentiment_pct: dict[str, float]


def compute_sentiment_metrics(sentiment_events: list[dict]) -> SentimentMetrics:
    """Compute sentiment analysis metrics.
    
    Args:
        sentiment_events: List of sentiment event dicts with 'sentiment' and 'confidence'
        
    Returns:
        SentimentMetrics object
    """
    if not sentiment_events:
        return SentimentMetrics(
            total_analyses=0,
            bullish_count=0,
            bearish_count=0,
            neutral_count=0,
            avg_score=0.0,
            avg_confidence=0.0,
            sentiment_distribution={},
            sentiment_pct={},
        )
    
    sentiments = [e.get("sentiment", "neutral") for e in sentiment_events]
    scores = [e.get("score", 0.0) for e in sentiment_events]
    confidences = [e.get("confidence", 0.0) for e in sentiment_events]
    
    sentiment_counts = Counter(sentiments)
    total = len(sentiments)
    
    return SentimentMetrics(
        total_analyses=total,
        bullish_count=sentiment_counts.get("bullish", 0),
        bearish_count=sentiment_counts.get("bearish", 0),
        neutral_count=sentiment_counts.get("neutral", 0),
        avg_score=np.mean(scores) if scores else 0.0,
        avg_confidence=np.mean(confidences) if confidences else 0.0,
        sentiment_distribution=dict(sentiment_counts),
        sentiment_pct={k: v / total for k, v in sentiment_counts.items()},
    )


def compute_sentiment_return_correlation(
    sentiment_events: list[dict],
    returns: pd.Series
) -> float:
    """Compute correlation between sentiment and returns.
    
    Args:
        sentiment_events: List of sentiment event dicts
        returns: Series of returns aligned to sentiment events
        
    Returns:
        Correlation coefficient
    """
    if not sentiment_events or len(returns) == 0:
        return 0.0
    
    sentiment_map = {"bullish": 1, "neutral": 0, "bearish": -1}
    sentiment_scores = [
        sentiment_map.get(e.get("sentiment", "neutral"), 0) 
        for e in sentiment_events
    ]
    
    if len(sentiment_scores) != len(returns):
        min_len = min(len(sentiment_scores), len(returns))
        sentiment_scores = sentiment_scores[:min_len]
        returns = returns[:min_len]
    
    return pd.Series(sentiment_scores).corr(returns)


def compute_sentiment_alpha(
    sentiment_events: list[dict],
    returns: pd.Series,
    threshold: float = 0.3
) -> dict[str, float]:
    """Compute sentiment-based alpha.
    
    Args:
        sentiment_events: List of sentiment event dicts
        returns: Series of returns
        threshold: Score threshold for bullish/bearish classification
        
    Returns:
        Dict of alpha metrics
    """
    if not sentiment_events or len(returns) == 0:
        return {
            "bullish_return": 0.0,
            "bearish_return": 0.0,
            "alpha": 0.0,
        }
    
    bullish_returns = []
    bearish_returns = []
    
    for i in range(len(sentiment_events) - 1):
        score = sentiment_events[i].get("score", 0.0)
        if score > threshold:
            if i < len(returns):
                bullish_returns.append(returns.iloc[i])
        elif score < -threshold:
            if i < len(returns):
                bearish_returns.append(returns.iloc[i])
    
    bullish_return = np.mean(bullish_returns) if bullish_returns else 0.0
    bearish_return = np.mean(bearish_returns) if bearish_returns else 0.0
    alpha = bullish_return - bearish_return
    
    return {
        "bullish_return": bullish_return,
        "bearish_return": bearish_return,
        "alpha": alpha,
    }
