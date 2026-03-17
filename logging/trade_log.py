"""Trade logger — SQLite persistence for audit trail."""

import json
import sqlite3
import numpy as np
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "trades.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT,
            asset         TEXT,
            direction     TEXT,
            action        TEXT,
            size          REAL,
            entry_price   REAL,
            exit_price    REAL,
            pnl           REAL,
            stop_loss     REAL,
            order_id      TEXT,
            status        TEXT,
            indicators    TEXT
        )
    """)
    conn.commit()
    conn.close()


def _json_default(obj):
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def log_trade(trade: dict):
    indicators = trade.get("indicators", {})
    indicators_clean = {
        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
        for k, v in indicators.items()
    }
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades
        (timestamp, asset, direction, action, size, entry_price,
         exit_price, pnl, stop_loss, order_id, status, indicators)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.utcnow().isoformat(),
        trade.get("asset"),
        trade.get("direction"),
        trade.get("action"),
        trade.get("size"),
        trade.get("entry_price"),
        trade.get("exit_price"),
        trade.get("pnl"),
        trade.get("stop_loss"),
        trade.get("order_id"),
        trade.get("status"),
        json.dumps(indicators_clean, default=_json_default),
    ))
    conn.commit()
    conn.close()
