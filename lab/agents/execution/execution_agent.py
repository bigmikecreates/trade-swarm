"""Execution agent — determines order type, sizing, and execution parameters."""

from __future__ import annotations

import pandas as pd
import numpy as np

from lab.agents.execution.base import (
    BaseExecutionAgent, 
    ExecutionEvent, 
    OrderType, 
    OrderSide
)


class ExecutionAgent(BaseExecutionAgent):
    """Execution agent that:
    - Uses market orders in trending conditions
    - Uses limit orders in ranging/mean-reversion scenarios
    - Adjusts position size based on volatility
    - Estimates slippage based on volume and volatility
    """

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        default_order_type: str = "market",
        use_volatility_sizing: bool = True,
        vol_lookback: int = 20,
        base_risk_pct: float = 0.02,
        **kwargs,
    ):
        super().__init__(symbol, **kwargs)
        self.default_order_type = OrderType(default_order_type)
        self.use_volatility_sizing = use_volatility_sizing
        self.vol_lookback = vol_lookback
        self.base_risk_pct = base_risk_pct

    def prepare_order(
        self,
        df: pd.DataFrame,
        signal_direction: str,
        position_size_pct: float,
        equity: float
    ) -> ExecutionEvent:
        """Prepare an order for execution."""
        self._require_cols(df, ["Close", "High", "Low", "Volume"])
        
        if signal_direction == "flat":
            return self._create_flat_order()
        
        current_price = df["Close"].iloc[-1]
        volatility = self._calculate_volatility(df)
        volume_ma = self._calculate_volume_ma(df)
        
        order_type = self._determine_order_type(df, signal_direction)
        quantity = self._calculate_quantity(
            equity, current_price, position_size_pct, volatility
        )
        
        side = OrderSide.BUY if signal_direction == "long" else OrderSide.SELL
        
        limit_price = None
        stop_price = None
        
        if order_type == OrderType.LIMIT:
            limit_price = self._calculate_limit_price(current_price, signal_direction)
        elif order_type == OrderType.STOP:
            stop_price = self._calculate_stop_price(current_price, signal_direction)
        elif order_type == OrderType.STOP_LIMIT:
            limit_price = self._calculate_limit_price(current_price, signal_direction)
            stop_price = self._calculate_stop_price(current_price, signal_direction)
        
        slippage = self._estimate_slippage(
            current_price, volatility, volume_ma, quantity
        )
        fill_time = self._estimate_fill_time(order_type, volatility, volume_ma)
        
        return ExecutionEvent(
            order_type=order_type,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            slippage_estimate=slippage,
            expected_fill_time=fill_time,
            indicators={
                "volatility": volatility,
                "volume_ma": volume_ma,
                "current_price": current_price,
            },
        )

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """Calculate rolling volatility."""
        returns = df["Close"].pct_change()
        volatility = returns.tail(self.vol_lookback).std()
        return float(volatility) if not pd.isna(volatility) else 0.02

    def _calculate_volume_ma(self, df: pd.DataFrame) -> float:
        """Calculate average volume."""
        volume_ma = df["Volume"].tail(self.vol_lookback).mean()
        return float(volume_ma) if not pd.isna(volume_ma) else 0

    def _determine_order_type(self, df: pd.DataFrame, signal_direction: str) -> OrderType:
        """Determine order type based on market conditions."""
        if self.default_order_type != OrderType.MARKET:
            return self.default_order_type
        
        volatility = self._calculate_volatility(df)
        volume = df["Volume"].iloc[-1]
        volume_ma = self._calculate_volume_ma(df)
        
        high_vol = volatility > 0.03
        low_volume = volume < volume_ma * 0.5
        
        if high_vol or low_volume:
            return OrderType.LIMIT
        
        return OrderType.MARKET

    def _calculate_quantity(
        self,
        equity: float,
        price: float,
        position_size_pct: float,
        volatility: float
    ) -> float:
        """Calculate position quantity."""
        if self.use_volatility_sizing:
            vol_scalar = 0.02 / max(volatility, 0.01)
            position_size_pct *= min(vol_scalar, 2.0)
        
        position_value = equity * position_size_pct
        quantity = position_value / price
        
        return max(0.01, quantity)

    def _calculate_limit_price(
        self, 
        current_price: float, 
        direction: str
    ) -> float:
        """Calculate limit price for limit orders."""
        offset = current_price * 0.002
        
        if direction == "long":
            return current_price - offset
        else:
            return current_price + offset

    def _calculate_stop_price(
        self,
        current_price: float,
        direction: str
    ) -> float:
        """Calculate stop price for stop orders."""
        offset = current_price * 0.01
        
        if direction == "long":
            return current_price - offset
        else:
            return current_price + offset

    def _estimate_slippage(
        self,
        price: float,
        volatility: float,
        volume_ma: float,
        quantity: float
    ) -> float:
        """Estimate slippage as percentage of price."""
        base_slippage = 0.0005
        
        vol_factor = min(volatility * 10, 0.01)
        
        return base_slippage + vol_factor

    def _estimate_fill_time(
        self,
        order_type: OrderType,
        volatility: float,
        volume_ma: float
    ) -> float:
        """Estimate expected fill time in seconds."""
        if order_type == OrderType.MARKET:
            return 1.0
        
        if order_type == OrderType.LIMIT:
            return 30.0 + volatility * 100
        
        return 10.0 + volatility * 50

    def _create_flat_order(self) -> ExecutionEvent:
        """Create a flat order (no action)."""
        return ExecutionEvent(
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            quantity=0.0,
            indicators={"action": "flat"},
        )
