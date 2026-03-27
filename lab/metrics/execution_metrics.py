"""Execution quality metrics."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class ExecutionMetrics:
    """Metrics for order execution quality."""
    total_orders: int
    market_orders: int
    limit_orders: int
    stop_orders: int
    avg_slippage: float
    max_slippage: float
    avg_fill_time: float
    fills: int
    rejections: int
    fill_rate: float


def compute_execution_metrics(
    execution_events: list[dict],
    trades: pd.DataFrame | None = None
) -> ExecutionMetrics:
    """Compute execution quality metrics.
    
    Args:
        execution_events: List of execution event dicts
        trades: Optional DataFrame of trades for fill rate calculation
        
    Returns:
        ExecutionMetrics object
    """
    if not execution_events:
        return ExecutionMetrics(
            total_orders=0,
            market_orders=0,
            limit_orders=0,
            stop_orders=0,
            avg_slippage=0.0,
            max_slippage=0.0,
            avg_fill_time=0.0,
            fills=0,
            rejections=0,
            fill_rate=0.0,
        )
    
    order_types = [e.get("order_type", "unknown") for e in execution_events]
    slippage = [e.get("slippage_estimate", 0.0) for e in execution_events]
    fill_times = [e.get("expected_fill_time", 0.0) for e in execution_events]
    
    market_orders = order_types.count("market")
    limit_orders = order_types.count("limit")
    stop_orders = order_types.count("stop")
    
    total = len(execution_events)
    fills = total - execution_events.count({"status": "rejected"})
    fill_rate = fills / total if total > 0 else 0.0
    
    return ExecutionMetrics(
        total_orders=total,
        market_orders=market_orders,
        limit_orders=limit_orders,
        stop_orders=stop_orders,
        avg_slippage=np.mean(slippage) if slippage else 0.0,
        max_slippage=np.max(slippage) if slippage else 0.0,
        avg_fill_time=np.mean(fill_times) if fill_times else 0.0,
        fills=fills,
        rejections=execution_events.count({"status": "rejected"}),
        fill_rate=fill_rate,
    )


def compute_slippage_impact(
    execution_events: list[dict],
    trades: pd.DataFrame
) -> dict[str, float]:
    """Compute slippage impact on P&L.
    
    Args:
        execution_events: List of execution event dicts
        trades: DataFrame with 'entry_price', 'exit_price', 'size' columns
        
    Returns:
        Dict of slippage metrics
    """
    if not execution_events or trades.empty:
        return {
            "total_slippage_cost": 0.0,
            "avg_slippage_pct": 0.0,
            "slippage_per_order": 0.0,
        }
    
    total_slippage = 0.0
    
    for i, event in enumerate(execution_events):
        slippage_pct = event.get("slippage_estimate", 0.0)
        quantity = event.get("quantity", 0.0)
        price = event.get("limit_price") or event.get("stop_price") or 0.0
        
        if quantity > 0 and price > 0:
            total_slippage += slippage_pct * quantity * price
    
    avg_slippage_pct = np.mean([
        e.get("slippage_estimate", 0.0) 
        for e in execution_events
    ]) if execution_events else 0.0
    
    return {
        "total_slippage_cost": total_slippage,
        "avg_slippage_pct": avg_slippage_pct,
        "slippage_per_order": total_slippage / len(execution_events) if execution_events else 0.0,
    }


def compute_order_efficiency(
    execution_events: list[dict],
    prices: pd.Series
) -> float:
    """Compute order execution efficiency score.
    
    Args:
        execution_events: List of execution event dicts
        prices: Series of market prices
        
    Returns:
        Efficiency score (0-1)
    """
    if not execution_events or prices.empty:
        return 0.0
    
    market_orders = sum(1 for e in execution_events if e.get("order_type") == "market")
    limit_orders = sum(1 for e in execution_events if e.get("order_type") == "limit")
    
    if market_orders + limit_orders == 0:
        return 0.0
    
    market_efficiency = 0.5 * (market_orders / (market_orders + limit_orders))
    limit_efficiency = 0.5 * (limit_orders / (market_orders + limit_orders))
    
    return market_efficiency + limit_efficiency
