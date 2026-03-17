"""Alpaca broker adapter for paper and live trading."""

import time
from dataclasses import dataclass
from datetime import datetime

import alpaca_trade_api as tradeapi


@dataclass
class OrderResult:
    order_id: str
    asset: str
    direction: str
    size: float
    status: str
    filled_price: float | None
    timestamp: datetime


class AlpacaAdapter:
    def __init__(self, api_key: str, secret: str, base_url: str):
        self.api = tradeapi.REST(api_key, secret, base_url)

    def place_market_order(self, asset: str, qty: float, side: str) -> OrderResult:
        order = self.api.submit_order(
            symbol=asset,
            qty=qty,
            side=side,
            type="market",
            time_in_force="gtc",
        )
        return OrderResult(
            order_id=order.id,
            asset=asset,
            direction=side,
            size=qty,
            status=order.status,
            filled_price=None,
            timestamp=datetime.utcnow(),
        )

    def get_order_status(self, order_id: str) -> dict:
        o = self.api.get_order(order_id)
        return {
            "status": o.status,
            "filled_qty": float(o.filled_qty or 0),
            "avg_price": float(o.filled_avg_price or 0),
        }

    def cancel_order(self, order_id: str):
        self.api.cancel_order(order_id)

    def get_positions(self) -> list[dict]:
        return [
            {
                "asset": p.symbol,
                "qty": float(p.qty),
                "avg_price": float(p.avg_entry_price),
            }
            for p in self.api.list_positions()
        ]

    def get_account_equity(self) -> float:
        return float(self.api.get_account().equity)

    def get_clock(self) -> dict:
        """Market clock: is_open, next_open, next_close (ISO strings)."""
        c = self.api.get_clock()
        return {
            "is_open": c.is_open,
            "timestamp": c.timestamp.isoformat() if c.timestamp else None,
            "next_open": c.next_open.isoformat() if c.next_open else None,
            "next_close": c.next_close.isoformat() if c.next_close else None,
        }

    def wait_for_fill(
        self,
        order_id: str,
        timeout_sec: float = 30.0,
        poll_interval: float = 1.0,
    ) -> dict | None:
        """
        Poll until order is filled or timeout. Returns {filled_qty, avg_price} or None.
        """
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            st = self.get_order_status(order_id)
            if st["status"] in ("filled", "closed"):
                return {"filled_qty": st["filled_qty"], "avg_price": st["avg_price"]}
            if st["status"] in ("canceled", "rejected", "expired"):
                return None
            time.sleep(poll_interval)
        return None
