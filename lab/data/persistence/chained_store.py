"""Chained persistence — writes to multiple stores (Redis Stream + PostgreSQL + Directory)."""

from __future__ import annotations

from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentRecord,
    ExperimentStatus,
    TradeRecord,
    SignalRecord,
    EquityPoint,
    MetricRecord,
)


class ChainedStore(DataStore):
    """Writes to multiple stores in chain.
    
    Order of operations:
    1. Redis Stream (real-time, short-term buffer)
    2. PostgreSQL (durable, long-term storage)
    3. Directory (fast access, TTL-based cleanup)
    
    Read operations come from PostgreSQL (or Directory if PostgreSQL unavailable).
    """

    def __init__(
        self,
        redis_producer=None,
        postgres_store=None,
        directory_store=None,
    ):
        self.redis = redis_producer
        self.postgres = postgres_store
        self.directory = directory_store

    def _get_primary(self) -> DataStore:
        """Get primary store for reads."""
        if self.postgres is not None:
            return self.postgres
        return self.directory

    def init(self) -> None:
        if self.postgres:
            self.postgres.init()
        if self.directory:
            self.directory.init()

    def create_experiment(
        self,
        name: str,
        strategy: str,
        config: dict,
        data_source: str
    ) -> str:
        if self.directory:
            return self.directory.create_experiment(name, strategy, config, data_source)
        
        if self.postgres:
            return self.postgres.create_experiment(name, strategy, config, data_source)
        
        raise ValueError("No store configured")

    def update_experiment_status(
        self,
        run_id: str,
        status: ExperimentStatus,
        error: str | None = None
    ) -> None:
        if self.directory:
            self.directory.update_experiment_status(run_id, status, error)
        if self.postgres:
            self.postgres.update_experiment_status(run_id, status, error)

    def log_trade(self, trade: TradeRecord) -> int:
        trade_id = 0
        
        if self.redis:
            self.redis.publish(
                trade.run_id,
                "trade",
                {
                    "trade_id": trade.trade_id,
                    "asset": trade.asset,
                    "direction": trade.direction,
                    "action": trade.action,
                    "size": trade.size,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": trade.pnl,
                    "stop_loss": trade.stop_loss,
                    "order_id": trade.order_id,
                    "status": trade.status,
                    "indicators": trade.indicators,
                    "created_at": trade.created_at.isoformat() if trade.created_at else None,
                },
            )
        
        if self.directory:
            trade_id = self.directory.log_trade(trade)
        
        if self.postgres:
            trade_id = self.postgres.log_trade(trade)
        
        return trade_id

    def log_signal(self, signal: SignalRecord) -> int:
        signal_id = 0
        
        if self.redis:
            self.redis.publish(
                signal.run_id,
                "signal",
                {
                    "agent_id": signal.agent_id,
                    "asset": signal.asset,
                    "direction": signal.direction,
                    "strength": signal.strength,
                    "confidence": signal.confidence,
                    "indicators": signal.indicators,
                    "timestamp": signal.timestamp.isoformat() if signal.timestamp else None,
                },
            )
        
        if self.directory:
            signal_id = self.directory.log_signal(signal)
        
        if self.postgres:
            signal_id = self.postgres.log_signal(signal)
        
        return signal_id

    def append_equity(self, point: EquityPoint) -> None:
        if self.directory:
            self.directory.append_equity(point)
        
        if self.postgres:
            self.postgres.append_equity(point)

    def save_metric(self, metric: MetricRecord) -> int:
        metric_id = 0
        
        if self.directory:
            metric_id = self.directory.save_metric(metric)
        
        if self.postgres:
            metric_id = self.postgres.save_metric(metric)
        
        return metric_id

    def get_experiment(self, run_id: str) -> ExperimentRecord | None:
        return self._get_primary().get_experiment(run_id)

    def list_experiments(
        self,
        strategy: str | None = None,
        limit: int = 100
    ) -> list[ExperimentRecord]:
        return self._get_primary().list_experiments(strategy, limit)

    def get_trades(self, run_id: str) -> list[TradeRecord]:
        return self._get_primary().get_trades(run_id)

    def get_signals(self, run_id: str) -> list[SignalRecord]:
        return self._get_primary().get_signals(run_id)

    def get_equity_curve(self, run_id: str) -> list[EquityPoint]:
        return self._get_primary().get_equity_curve(run_id)

    def get_metrics(self, run_id: str) -> list[MetricRecord]:
        return self._get_primary().get_metrics(run_id)

    def close(self) -> None:
        if self.redis:
            self.redis.close()
        if self.postgres:
            self.postgres.close()
        if self.directory:
            self.directory.close()
