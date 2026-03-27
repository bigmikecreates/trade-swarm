"""Risk management metrics."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class RiskMetrics:
    """Metrics for risk management performance."""
    max_drawdown: float
    max_drawdown_pct: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    avg_position_heat: float
    max_position_heat: float
    risk_events_triggered: int
    total_warnings: int


def compute_risk_metrics(
    equity_curve: pd.DataFrame,
    risk_events: list[dict],
    positions: pd.Series | None = None
) -> RiskMetrics:
    """Compute risk management metrics.
    
    Args:
        equity_curve: DataFrame with 'equity' column
        risk_events: List of risk event dicts from RiskAgent
        positions: Optional series of position sizes
        
    Returns:
        RiskMetrics object
    """
    if equity_curve.empty:
        return RiskMetrics(
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            cvar_99=0.0,
            avg_position_heat=0.0,
            max_position_heat=0.0,
            risk_events_triggered=0,
            total_warnings=0,
        )
    
    equity = equity_curve["equity"]
    returns = equity.pct_change().dropna()
    
    var_95 = compute_var(returns, 0.95)
    var_99 = compute_var(returns, 0.99)
    cvar_95 = compute_cvar(returns, 0.95)
    cvar_99 = compute_cvar(returns, 0.99)
    
    peak = equity.expanding().max()
    drawdown = (peak - equity) / peak
    max_drawdown = drawdown.max()
    max_drawdown_dollar = (peak - equity).max()
    
    total_warnings = sum(
        len(event.get("warnings", [])) 
        for event in risk_events
    )
    
    heat_values = []
    if positions is not None:
        for pos in positions:
            if pos is not None and abs(pos) > 0:
                heat_values.append(abs(pos) * 0.02)
    
    avg_heat = np.mean(heat_values) if heat_values else 0.0
    max_heat = np.max(heat_values) if heat_values else 0.0
    
    return RiskMetrics(
        max_drawdown=max_drawdown_dollar,
        max_drawdown_pct=max_drawdown,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        avg_position_heat=avg_heat,
        max_position_heat=max_heat,
        risk_events_triggered=len(risk_events),
        total_warnings=total_warnings,
    )


def compute_var(returns: pd.Series, confidence: float) -> float:
    """Compute Value at Risk.
    
    Args:
        returns: Series of returns
        confidence: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        VaR as positive number
    """
    if len(returns) < 2:
        return 0.0
    
    var = np.percentile(returns, (1 - confidence) * 100)
    return abs(var)


def compute_cvar(returns: pd.Series, confidence: float) -> float:
    """Compute Conditional Value at Risk (Expected Shortfall).
    
    Args:
        returns: Series of returns
        confidence: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        CVaR as positive number
    """
    if len(returns) < 2:
        return 0.0
    
    var = np.percentile(returns, (1 - confidence) * 100)
    cvar = returns[returns <= var].mean()
    
    return abs(cvar) if not pd.isna(cvar) else 0.0


def compute_sharpe_ratio(
    returns: pd.Series, 
    risk_free_rate: float = 0.0
) -> float:
    """Compute Sharpe ratio.
    
    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def compute_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    target_return: float = 0.0
) -> float:
    """Compute Sortino ratio (uses downside deviation).
    
    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate
        target_return: Target return threshold
        
    Returns:
        Sortino ratio
    """
    if len(returns) < 2:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < target_return]
    
    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0
    
    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()


def compute_calmar_ratio(
    returns: pd.Series,
    equity: pd.Series
) -> float:
    """Compute Calmar ratio (return / max drawdown).
    
    Args:
        returns: Series of returns
        equity: Series of equity values
        
    Returns:
        Calmar ratio
    """
    if len(returns) < 2 or len(equity) < 2:
        return 0.0
    
    annual_return = returns.mean() * 252
    
    peak = equity.expanding().max()
    drawdown = (peak - equity) / peak
    max_drawdown = drawdown.max()
    
    if max_drawdown == 0:
        return 0.0
    
    return annual_return / max_drawdown
