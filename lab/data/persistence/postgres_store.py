"""PostgreSQL persistence layer — table-per-strategy schema."""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentRecord,
    ExperimentStatus,
    TradeRecord,
    SignalRecord,
    EquityPoint,
    MetricRecord,
)


class PostgresStore(DataStore):
    """PostgreSQL data store with table-per-strategy schema.
    
    Schema:
    - experiments: Shared experiment metadata
    - {strategy}_trades: Trades for each strategy
    - {strategy}_signals: Signals for each strategy
    - equity_curve: Shared equity data
    - metrics: Shared metrics
    
    Connection via environment variables:
    - LAB_POSTGRES_HOST (default: localhost)
    - LAB_POSTGRES_PORT (default: 5432)
    - LAB_POSTGRES_DB (default: trade_swarm_lab)
    - LAB_POSTGRES_USER (default: postgres)
    - LAB_POSTGRES_PASSWORD (default: empty)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        db: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.host = host or os.environ.get("LAB_POSTGRES_HOST", "localhost")
        self.port = port or int(os.environ.get("LAB_POSTGRES_PORT", "5432"))
        self.db = db or os.environ.get("LAB_POSTGRES_DB", "trade_swarm_lab")
        self.user = user or os.environ.get("LAB_POSTGRES_USER", "postgres")
        self.password = password or os.environ.get("LAB_POSTGRES_PASSWORD", "")
        self._conn = None

    def connect(self) -> None:
        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.db,
            user=self.user,
            password=self.password,
        )
        self._conn.autocommit = True

    def init(self) -> None:
        """Initialize the store (create tables)."""
        if self._conn is None:
            self.connect()

        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    run_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    strategy VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    config JSONB NOT NULL,
                    data_source VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(50) NOT NULL REFERENCES experiments(run_id),
                    timestamp TIMESTAMP NOT NULL,
                    equity DECIMAL(15, 2) NOT NULL,
                    drawdown DECIMAL(10, 6)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_equity_run_id 
                ON equity_curve(run_id)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(50) NOT NULL REFERENCES experiments(run_id),
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value DECIMAL(15, 6) NOT NULL
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_run_id 
                ON metrics(run_id)
            """)

    def create_experiment(
        self, 
        name: str, 
        strategy: str, 
        config: dict, 
        data_source: str
    ) -> str:
        from lab.harness.runner import ExperimentRunner
        run_id = ExperimentRunner(None, None).store._generate_run_id()  # type: ignore
        
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO experiments (run_id, name, strategy, status, config, data_source)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, name, strategy, "running", json.dumps(config), data_source)
            )
        
        self._ensure_strategy_tables(strategy)
        
        return run_id

    def _ensure_strategy_tables(self, strategy: str) -> None:
        """Create strategy-specific tables if they don't exist."""
        safe_name = self._safe_table_name(strategy)
        
        with self._conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {safe_name}_trades (
                    trade_id SERIAL PRIMARY KEY,
                    run_id VARCHAR(50) NOT NULL,
                    asset VARCHAR(20) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    action VARCHAR(10) NOT NULL,
                    size DECIMAL(15, 6) NOT NULL,
                    entry_price DECIMAL(15, 6),
                    exit_price DECIMAL(15, 6),
                    pnl DECIMAL(15, 6),
                    stop_loss DECIMAL(15, 6),
                    order_id VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'open',
                    indicators JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{safe_name}_trades_run_id 
                ON {safe_name}_trades(run_id)
            """)
            
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {safe_name}_signals (
                    signal_id SERIAL PRIMARY KEY,
                    run_id VARCHAR(50) NOT NULL,
                    agent_id VARCHAR(50) NOT NULL,
                    asset VARCHAR(20) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    strength DECIMAL(5, 4),
                    confidence DECIMAL(5, 4),
                    indicators JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{safe_name}_signals_run_id 
                ON {safe_name}_signals(run_id)
            """)

    def _safe_table_name(self, name: str) -> str:
        """Sanitize table name to prevent SQL injection."""
        return "".join(c if c.isalnum() else "_" for c in name.lower())

    def update_experiment_status(
        self, 
        run_id: str, 
        status: ExperimentStatus, 
        error: str | None = None
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE experiments 
                SET status = %s, completed_at = CURRENT_TIMESTAMP, error = %s
                WHERE run_id = %s
                """,
                (status.value, error, run_id)
            )

    def log_trade(self, trade: TradeRecord) -> int:
        safe_name = self._safe_table_name(trade.direction)  # Use direction or get from experiment
        
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {safe_name}_trades 
                (run_id, asset, direction, action, size, entry_price, exit_price, 
                 pnl, stop_loss, order_id, status, indicators, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING trade_id
                """,
                (
                    trade.run_id,
                    trade.asset,
                    trade.direction,
                    trade.action,
                    trade.size,
                    trade.entry_price,
                    trade.exit_price,
                    trade.pnl,
                    trade.stop_loss,
                    trade.order_id,
                    trade.status,
                    json.dumps(trade.indicators) if trade.indicators else None,
                    trade.created_at,
                )
            )
            result = cur.fetchone()
            return result[0] if result else 0

    def log_signal(self, signal: SignalRecord) -> int:
        exp = self.get_experiment(signal.run_id)
        strategy = exp.strategy if exp else "default"
        safe_name = self._safe_table_name(strategy)
        
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {safe_name}_signals 
                (run_id, agent_id, asset, direction, strength, confidence, indicators, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING signal_id
                """,
                (
                    signal.run_id,
                    signal.agent_id,
                    signal.asset,
                    signal.direction,
                    signal.strength,
                    signal.confidence,
                    json.dumps(signal.indicators) if signal.indicators else None,
                    signal.timestamp,
                )
            )
            result = cur.fetchone()
            return result[0] if result else 0

    def append_equity(self, point: EquityPoint) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO equity_curve (run_id, timestamp, equity, drawdown)
                VALUES (%s, %s, %s, %s)
                """,
                (point.run_id, point.timestamp, point.equity, point.drawdown)
            )

    def save_metric(self, metric: MetricRecord) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metrics (run_id, metric_name, metric_value)
                VALUES (%s, %s, %s)
                RETURNING metric_id
                """,
                (metric.run_id, metric.metric_name, metric.metric_value)
            )
            result = cur.fetchone()
            return result[0] if result else 0

    def get_experiment(self, run_id: str) -> ExperimentRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, name, strategy, status, config, data_source, created_at, completed_at, error FROM experiments WHERE run_id = %s",
                (run_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            
            return ExperimentRecord(
                run_id=row[0],
                name=row[1],
                strategy=row[2],
                status=ExperimentStatus(row[3]),
                config=row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                data_source=row[5],
                created_at=row[6],
                completed_at=row[7],
                error=row[8],
            )

    def list_experiments(
        self, 
        strategy: str | None = None, 
        limit: int = 100
    ) -> list[ExperimentRecord]:
        with self._conn.cursor() as cur:
            if strategy:
                cur.execute(
                    "SELECT run_id, name, strategy, status, config, data_source, created_at, completed_at, error FROM experiments WHERE strategy = %s ORDER BY created_at DESC LIMIT %s",
                    (strategy, limit)
                )
            else:
                cur.execute(
                    "SELECT run_id, name, strategy, status, config, data_source, created_at, completed_at, error FROM experiments ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
            
            return [
                ExperimentRecord(
                    run_id=row[0],
                    name=row[1],
                    strategy=row[2],
                    status=ExperimentStatus(row[3]),
                    config=row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                    data_source=row[5],
                    created_at=row[6],
                    completed_at=row[7],
                    error=row[8],
                )
                for row in cur.fetchall()
            ]

    def get_trades(self, run_id: str) -> list[TradeRecord]:
        exp = self.get_experiment(run_id)
        strategy = exp.strategy if exp else "default"
        safe_name = self._safe_table_name(strategy)
        
        with self._conn.cursor() as cur:
            try:
                cur.execute(
                    f"SELECT trade_id, run_id, asset, direction, action, size, entry_price, exit_price, pnl, stop_loss, order_id, status, indicators, created_at FROM {safe_name}_trades WHERE run_id = %s",
                    (run_id,)
                )
            except psycopg2.Error:
                return []
            
            return [
                TradeRecord(
                    trade_id=row[0],
                    run_id=row[1],
                    asset=row[2],
                    direction=row[3],
                    action=row[4],
                    size=float(row[5]),
                    entry_price=float(row[6]) if row[6] else None,
                    exit_price=float(row[7]) if row[7] else None,
                    pnl=float(row[8]) if row[8] else None,
                    stop_loss=float(row[9]) if row[9] else None,
                    order_id=row[10],
                    status=row[11],
                    indicators=row[12] if isinstance(row[12], dict) else json.loads(row[12]) if row[12] else None,
                    created_at=row[13],
                )
                for row in cur.fetchall()
            ]

    def get_signals(self, run_id: str) -> list[SignalRecord]:
        exp = self.get_experiment(run_id)
        strategy = exp.strategy if exp else "default"
        safe_name = self._safe_table_name(strategy)
        
        with self._conn.cursor() as cur:
            try:
                cur.execute(
                    f"SELECT signal_id, run_id, agent_id, asset, direction, strength, confidence, indicators, timestamp FROM {safe_name}_signals WHERE run_id = %s",
                    (run_id,)
                )
            except psycopg2.Error:
                return []
            
            return [
                SignalRecord(
                    signal_id=row[0],
                    run_id=row[1],
                    agent_id=row[2],
                    asset=row[3],
                    direction=row[4],
                    strength=float(row[5]) if row[5] else 0.0,
                    confidence=float(row[6]) if row[6] else 0.0,
                    indicators=row[7] if isinstance(row[7], dict) else json.loads(row[7]) if row[7] else None,
                    timestamp=row[8],
                )
                for row in cur.fetchall()
            ]

    def get_equity_curve(self, run_id: str) -> list[EquityPoint]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, timestamp, equity, drawdown FROM equity_curve WHERE run_id = %s ORDER BY timestamp",
                (run_id,)
            )
            
            return [
                EquityPoint(
                    run_id=row[0],
                    timestamp=row[1],
                    equity=float(row[2]),
                    drawdown=float(row[3]) if row[3] else None,
                )
                for row in cur.fetchall()
            ]

    def get_metrics(self, run_id: str) -> list[MetricRecord]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT metric_id, run_id, metric_name, metric_value FROM metrics WHERE run_id = %s",
                (run_id,)
            )
            
            return [
                MetricRecord(
                    metric_id=row[0],
                    run_id=row[1],
                    metric_name=row[2],
                    metric_value=float(row[3]),
                )
                for row in cur.fetchall()
            ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
