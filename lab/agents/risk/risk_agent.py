"""Risk agent — evaluates portfolio risk and position limits."""

from __future__ import annotations

import numpy as np
import pandas as pd

from lab.agents.risk.base import BaseRiskAgent, RiskEvent, RiskLevel


class RiskAgent(BaseRiskAgent):
    """Risk agent that evaluates:
    - Value at Risk (VaR) at 95% confidence
    - Current drawdown
    - Position heat (% of equity at risk)
    - Maximum position size allowed
    """

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        max_position_pct: float = 0.95,
        max_heat_pct: float = 0.10,
        max_drawdown_pct: float = 0.20,
        var_confidence: float = 0.95,
        **kwargs,
    ):
        super().__init__(symbol, **kwargs)
        self.max_position_pct = max_position_pct
        self.max_heat_pct = max_heat_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.var_confidence = var_confidence

    def evaluate(
        self, 
        df: pd.DataFrame, 
        equity: float, 
        position: float | None,
        entry_price: float | None
    ) -> RiskEvent:
        """Evaluate current risk and return position limits."""
        warnings = []
        
        returns = df["Close"].pct_change().dropna()
        
        var_95 = self._calculate_var(returns)
        drawdown_pct = self._calculate_drawdown(df, equity)
        heat_pct = self._calculate_heat(position, entry_price, equity)
        
        risk_level = self._determine_risk_level(
            var_95, drawdown_pct, heat_pct, equity
        )
        
        max_position = self._calculate_max_position(
            equity, var_95, drawdown_pct, heat_pct
        )
        
        if drawdown_pct > self.max_drawdown_pct:
            warnings.append(f"Max drawdown exceeded: {drawdown_pct:.1%}")
        
        if heat_pct > self.max_heat_pct:
            warnings.append(f"Position heat exceeded: {heat_pct:.1%}")
        
        if risk_level == RiskLevel.CRITICAL:
            warnings.append("CRITICAL risk level - consider reducing exposure")
        
        return RiskEvent(
            risk_level=risk_level,
            max_position_pct=max_position,
            var_95=var_95,
            drawdown_pct=drawdown_pct,
            heat_pct=heat_pct,
            warnings=warnings,
        )

    def _calculate_var(self, returns: pd.Series, window: int = 252) -> float:
        """Calculate Value at Risk at configured confidence level."""
        if len(returns) < 2:
            return 0.0
        
        recent = returns.tail(min(window, len(returns)))
        var = np.percentile(recent, (1 - self.var_confidence) * 100)
        return abs(var)

    def _calculate_drawdown(self, df: pd.DataFrame, current_equity: float) -> float:
        """Calculate current drawdown from peak equity."""
        if len(df) < 2:
            return 0.0
        
        equity_curve = df["Close"] / df["Close"].iloc[0]
        peak = equity_curve.expanding().max()
        current = equity_curve.iloc[-1]
        drawdown = (peak - current) / peak
        
        return drawdown

    def _calculate_heat(
        self, 
        position: float | None, 
        entry_price: float | None,
        equity: float
    ) -> float:
        """Calculate position heat (% of equity at risk)."""
        if position is None or entry_price is None or equity <= 0:
            return 0.0
        
        position_value = abs(position * entry_price)
        risk_per_unit = entry_price * 0.02
        total_risk = risk_per_unit * abs(position)
        
        return total_risk / equity

    def _determine_risk_level(
        self,
        var_95: float,
        drawdown_pct: float,
        heat_pct: float,
        equity: float
    ) -> RiskLevel:
        """Determine overall risk level."""
        if equity <= 0:
            return RiskLevel.CRITICAL
        
        if drawdown_pct > 0.25 or heat_pct > 0.20:
            return RiskLevel.CRITICAL
        
        if drawdown_pct > 0.15 or heat_pct > 0.15:
            return RiskLevel.HIGH
        
        if drawdown_pct > 0.08 or heat_pct > 0.10:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW

    def _calculate_max_position(
        self,
        equity: float,
        var_95: float,
        drawdown_pct: float,
        heat_pct: float
    ) -> float:
        """Calculate maximum position percentage allowed."""
        if equity <= 0:
            return 0.0
        
        max_allowed = self.max_position_pct
        
        if drawdown_pct > 0.10:
            max_allowed *= 0.5
        if drawdown_pct > 0.15:
            max_allowed *= 0.25
        
        if heat_pct > 0.05:
            reduction_factor = max(0, 1 - (heat_pct / self.max_heat_pct))
            max_allowed *= reduction_factor
        
        return max(0, min(max_allowed, self.max_position_pct))
