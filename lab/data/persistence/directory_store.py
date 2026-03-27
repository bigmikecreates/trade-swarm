"""Directory-based data store — canonical local storage for experiments."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentRecord,
    ExperimentStatus,
    TradeRecord,
    SignalRecord,
    EquityPoint,
    MetricRecord,
)


class DirectoryStore(DataStore):
    """Store experiment data in canonical directories on disk.
    
    Directory structure:
        experiments/
            [DD-Mon-YY][HH:MM:SS]-experiment_run-[strategy_name]/
                config.json
                metrics.json
                trades.parquet
                equity_curve.parquet
                signals.db   (SQLite for high-frequency signal writes)
    """

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        pass

    def create_experiment(self, name: str, strategy: str, config: dict, data_source: str) -> str:
        run_id = self._generate_run_id()
        exp_dir = self._get_experiment_dir(name)
        exp_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "run_id": run_id,
            "name": name,
            "strategy": strategy,
            "config": config,
            "data_source": data_source,
            "status": ExperimentStatus.RUNNING.value,
            "created_at": datetime.utcnow().isoformat(),
        }
        with open(exp_dir / "config.json", "w") as f:
            json.dump(meta, f, indent=2)

        signals_db = exp_dir / "signals.db"
        conn = sqlite3.connect(signals_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                strength REAL NOT NULL,
                confidence REAL NOT NULL,
                indicators TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_run ON signals(agent_id, timestamp)")
        conn.commit()
        conn.close()

        return run_id

    def update_experiment_status(self, run_id: str, status: ExperimentStatus, error: str | None = None) -> None:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return

        config_path = exp_dir / "config.json"
        with open(config_path) as f:
            meta = json.load(f)

        meta["status"] = status.value
        if status == ExperimentStatus.COMPLETED:
            meta["completed_at"] = datetime.utcnow().isoformat()
        if error:
            meta["error"] = error

        with open(config_path, "w") as f:
            json.dump(meta, f, indent=2)

    def log_trade(self, trade: TradeRecord) -> int:
        exp_dir = self._find_experiment_dir(trade.run_id)
        if exp_dir is None:
            return -1

        trade_file = exp_dir / "trades.parquet"
        trade_dict = {
            "trade_id": trade.trade_id,
            "run_id": trade.run_id,
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
            "indicators": json.dumps(trade.indicators) if trade.indicators else None,
            "created_at": trade.created_at.isoformat(),
        }

        df = pd.DataFrame([trade_dict])
        if trade_file.exists():
            existing = pd.read_parquet(trade_file)
            if len(existing) > 0:
                existing_filtered = existing.dropna(how="all").dropna(axis=1, how="all")
                df_filtered = df.dropna(axis=1, how="all")
                if len(existing_filtered) > 0 and len(df_filtered.columns) > 0:
                    df = pd.concat([existing_filtered, df_filtered], ignore_index=True)

        df.to_parquet(trade_file, index=False)
        return trade.trade_id or 0

    def log_signal(self, signal: SignalRecord) -> int:
        exp_dir = self._find_experiment_dir(signal.run_id)
        if exp_dir is None:
            return -1

        signals_db = exp_dir / "signals.db"
        conn = sqlite3.connect(signals_db)
        cursor = conn.execute(
            """
            INSERT INTO signals (agent_id, asset, direction, strength, confidence, indicators, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.agent_id,
                signal.asset,
                signal.direction,
                signal.strength,
                signal.confidence,
                json.dumps(signal.indicators) if signal.indicators else None,
                signal.timestamp.isoformat(),
            ),
        )
        conn.commit()
        signal_id = cursor.lastrowid
        conn.close()
        return signal_id

    def append_equity(self, point: EquityPoint) -> None:
        exp_dir = self._find_experiment_dir(point.run_id)
        if exp_dir is None:
            return

        if not hasattr(self, "_equity_buffer"):
            self._equity_buffer: dict[str, list[dict]] = {}

        run_key = point.run_id
        if run_key not in self._equity_buffer:
            self._equity_buffer[run_key] = []

        self._equity_buffer[run_key].append({
            "run_id": point.run_id,
            "timestamp": point.timestamp.isoformat(),
            "equity": point.equity,
            "drawdown": point.drawdown,
        })

    def flush_equity(self, run_id: str) -> None:
        """Write all buffered equity points to disk. Call at end of experiment."""
        if not hasattr(self, "_equity_buffer") or run_id not in self._equity_buffer:
            return

        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return

        equity_file = exp_dir / "equity_curve.parquet"
        pts = self._equity_buffer[run_id]
        if not pts:
            return

        df = pd.DataFrame(pts)
        if equity_file.exists():
            existing = pd.read_parquet(equity_file)
            if len(existing) > 0:
                existing_filtered = existing.dropna(how="all").dropna(axis=1, how="all")
                df_filtered = df.dropna(axis=1, how="all")
                if len(existing_filtered) > 0 and len(df_filtered.columns) > 0:
                    df = pd.concat([existing_filtered, df_filtered], ignore_index=True)

        df.to_parquet(equity_file, index=False)
        self._equity_buffer[run_id] = []

    def save_metric(self, metric: MetricRecord) -> int:
        exp_dir = self._find_experiment_dir(metric.run_id)
        if exp_dir is None:
            return -1

        metrics_file = exp_dir / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)
        else:
            metrics = {}

        metrics[metric.metric_name] = metric.metric_value

        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)

        return metric.metric_id or 0

    def get_experiment(self, run_id: str) -> ExperimentRecord | None:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return None

        config_path = exp_dir / "config.json"
        if not config_path.exists():
            return None

        with open(config_path) as f:
            meta = json.load(f)

        return ExperimentRecord(
            run_id=meta["run_id"],
            name=meta["name"],
            strategy=meta["strategy"],
            status=ExperimentStatus(meta["status"]),
            config=meta["config"],
            data_source=meta["data_source"],
            created_at=datetime.fromisoformat(meta["created_at"]),
        )

    def list_experiments(self, strategy: str | None = None, limit: int = 100) -> list[ExperimentRecord]:
        records = []
        for exp_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if not exp_dir.is_dir():
                continue
            config_path = exp_dir / "config.json"
            if not config_path.exists():
                continue

            with open(config_path) as f:
                meta = json.load(f)

            if strategy and meta.get("strategy") != strategy:
                continue

            records.append(ExperimentRecord(
                run_id=meta["run_id"],
                name=meta["name"],
                strategy=meta["strategy"],
                status=ExperimentStatus(meta["status"]),
                config=meta["config"],
                data_source=meta["data_source"],
                created_at=datetime.fromisoformat(meta["created_at"]),
            ))

            if len(records) >= limit:
                break

        return records

    def get_trades(self, run_id: str) -> list[TradeRecord]:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return []

        trade_file = exp_dir / "trades.parquet"
        if not trade_file.exists():
            return []

        df = pd.read_parquet(trade_file)
        return [
            TradeRecord(
                trade_id=int(row.trade_id) if row.trade_id else None,
                run_id=row.run_id,
                asset=row.asset,
                direction=row.direction,
                action=row.action,
                size=row.size,
                entry_price=row.entry_price,
                exit_price=row.exit_price,
                pnl=row.pnl,
                stop_loss=row.stop_loss,
                order_id=row.order_id,
                status=row.status,
                indicators=json.loads(row.indicators) if row.indicators else None,
                created_at=datetime.fromisoformat(row.created_at),
            )
            for row in df.itertuples()
        ]

    def get_signals(self, run_id: str) -> list[SignalRecord]:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return []

        signals_db = exp_dir / "signals.db"
        if not signals_db.exists():
            return []

        conn = sqlite3.connect(signals_db)
        rows = conn.execute("SELECT * FROM signals").fetchall()
        conn.close()

        return [
            SignalRecord(
                signal_id=row[0],
                run_id=run_id,
                agent_id=row[1],
                asset=row[2],
                direction=row[3],
                strength=row[4],
                confidence=row[5],
                indicators=json.loads(row[6]) if row[6] else None,
                timestamp=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]

    def get_equity_curve(self, run_id: str) -> list[EquityPoint]:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return []

        equity_file = exp_dir / "equity_curve.parquet"
        if not equity_file.exists():
            return []

        df = pd.read_parquet(equity_file)
        return [
            EquityPoint(
                run_id=row.run_id,
                timestamp=datetime.fromisoformat(row.timestamp),
                equity=row.equity,
                drawdown=row.drawdown if pd.notna(row.drawdown) else None,
            )
            for row in df.itertuples()
        ]

    def get_metrics(self, run_id: str) -> list[MetricRecord]:
        exp_dir = self._find_experiment_dir(run_id)
        if exp_dir is None:
            return []

        metrics_file = exp_dir / "metrics.json"
        if not metrics_file.exists():
            return []

        with open(metrics_file) as f:
            metrics = json.load(f)

        return [
            MetricRecord(
                metric_id=None,
                run_id=run_id,
                metric_name=name,
                metric_value=value,
            )
            for name, value in metrics.items()
        ]

    def close(self) -> None:
        pass

    def _generate_run_id(self) -> str:
        return f"exp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    def _get_experiment_dir(self, name: str) -> Path:
        safe_name = name.replace(" ", "_").replace(":", "-")
        return self.base_dir / safe_name

    def _find_experiment_dir(self, run_id: str) -> Path | None:
        for exp_dir in self.base_dir.iterdir():
            if not exp_dir.is_dir():
                continue
            config_path = exp_dir / "config.json"
            if not config_path.exists():
                continue
            with open(config_path) as f:
                meta = json.load(f)
            if meta.get("run_id") == run_id:
                return exp_dir
        return None

    def list_all_dirs(self) -> list[Path]:
        """List all experiment directories."""
        return sorted(self.base_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_dir_age_days(self, exp_dir: Path) -> float:
        """Return age of experiment directory in days."""
        mtime = exp_dir.stat().st_mtime
        age = datetime.now().timestamp() - mtime
        return age / 86400
