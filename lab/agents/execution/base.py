"""Base class for execution agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

import pandas as pd


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class ExecutionEvent:
    """Output from an execution agent."""
    order_type: OrderType
    side: OrderSide
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    slippage_estimate: float = 0.0
    expected_fill_time: float = 0.0
    indicators: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class BaseExecutionAgent(ABC):
    """Abstract base class for execution agents.
    
    Execution agents determine order type, sizing, and execution
    parameters based on market conditions.
    """

    def __init__(self, symbol: str = "SYNTHETIC", **kwargs):
        self.symbol = symbol
        self._params = kwargs

    @abstractmethod
    def prepare_order(
        self, 
        df: pd.DataFrame, 
        signal_direction: str,
        position_size_pct: float,
        equity: float
    ) -> ExecutionEvent:
        """Prepare an order for execution.
        
        Args:
            df: DataFrame with OHLCV columns
            signal_direction: "long", "short", or "flat"
            position_size_pct: Percentage of equity to use for position
            equity: Current portfolio equity
            
        Returns:
            ExecutionEvent with order details
        """
        ...
