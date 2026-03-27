"""Persistence layer interfaces — abstract contract for all data stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import json


class ExperimentStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExperimentRecord:
    run_id: str
    name: str
    strategy: str
    status: ExperimentStatus
    config: dict
    data_source: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class TradeRecord:
    trade_id: int | None
    run_id: str
    asset: str
    direction: str
    action: str
    size: float
    entry_price: float | None = None
    exit_price: float | None = None
    pnl: float | None = None
    stop_loss: float | None = None
    order_id: str | None = None
    status: str = "open"
    indicators: dict | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SignalRecord:
    signal_id: int | None
    run_id: str
    agent_id: str
    asset: str
    direction: str
    strength: float
    confidence: float
    indicators: dict | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EquityPoint:
    run_id: str
    timestamp: datetime
    equity: float
    drawdown: float | None = None


@dataclass
class MetricRecord:
    metric_id: int | None
    run_id: str
    metric_name: str
    metric_value: float


class DataStore(ABC):
    """Abstract interface for all data stores.
    
    Implement this contract for SQLite, PostgreSQL, or any other store.
    The harness always uses this interface — stores are swappable.
    """

    @abstractmethod
    def init(self) -> None:
        """Initialize the store (create tables, connect, etc.)."""

    @abstractmethod
    def create_experiment(self, name: str, strategy: str, config: dict, data_source: str) -> str:
        """Create a new experiment record. Returns run_id."""

    @abstractmethod
    def update_experiment_status(self, run_id: str, status: ExperimentStatus, error: str | None = None) -> None:
        """Update experiment status."""

    @abstractmethod
    def log_trade(self, trade: TradeRecord) -> int:
        """Log a trade. Returns trade_id."""

    @abstractmethod
    def log_signal(self, signal: SignalRecord) -> int:
        """Log a signal. Returns signal_id."""

    @abstractmethod
    def append_equity(self, point: EquityPoint) -> None:
        """Append an equity point."""

    @abstractmethod
    def save_metric(self, metric: MetricRecord) -> int:
        """Save a metric. Returns metric_id."""

    @abstractmethod
    def get_experiment(self, run_id: str) -> ExperimentRecord | None:
        """Retrieve an experiment by run_id."""

    @abstractmethod
    def list_experiments(self, strategy: str | None = None, limit: int = 100) -> list[ExperimentRecord]:
        """List experiments, optionally filtered by strategy."""

    @abstractmethod
    def get_trades(self, run_id: str) -> list[TradeRecord]:
        """Get all trades for an experiment."""

    @abstractmethod
    def get_signals(self, run_id: str) -> list[SignalRecord]:
        """Get all signals for an experiment."""

    @abstractmethod
    def get_equity_curve(self, run_id: str) -> list[EquityPoint]:
        """Get equity curve for an experiment."""

    @abstractmethod
    def get_metrics(self, run_id: str) -> list[MetricRecord]:
        """Get all metrics for an experiment."""

    @abstractmethod
    def close(self) -> None:
        """Close connections, cleanup."""
