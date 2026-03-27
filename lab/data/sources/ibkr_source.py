"""Interactive Brokers TWS API source — free market data for all asset classes.

Requires:
  1. IBKR account (free demo or live)
  2. TWS (Trader Workstation) or IB Gateway running
  3. API connections enabled in TWS settings (File > Global Configuration > API > Settings)

Setup:
  1. Download TWS from: https://www.interactivebrokers.com/en/trading/tws.php
  2. Enable API connections in TWS settings
  3. Set port in config: Paper Trading API port 4002 (demo) or 7496 (live)
  4. Optionally set env vars: export IBKR_HOST=127.0.0.1 IBKR_PORT=4002
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime
from typing import Literal


class IBKRSource:
    """Fetch OHLCV data via Interactive Brokers TWS API.

    Supports: stocks, options, futures, forex, crypto — everything IBKR offers.
    Requires TWS or IB Gateway running with API connections enabled.

    Usage:
        source = IBKRSource(host="127.0.0.1", port=4002)  # paper trading
        df = source.fetch(symbol="SPY", timeframe="1d", period="5y")
    """

    TIMEFRAME_MAP = {
        "1m": ("1 min", 1),
        "5m": ("5 mins", 5),
        "15m": ("15 mins", 15),
        "30m": ("30 mins", 30),
        "1h": ("1 hour", 60),
        "4h": ("4 hours", 240),
        "1d": ("1 day", 1440),
        "M1": ("1 min", 1),
        "M5": ("5 mins", 5),
        "M15": ("15 mins", 15),
        "H1": ("1 hour", 60),
        "H4": ("4 hours", 240),
        "D1": ("1 day", 1440),
    }

    def __init__(self, host: str = "127.0.0.1", port: int = 4002):
        import os
        self.host = os.environ.get("IBKR_HOST", host)
        self.port = int(os.environ.get("IBKR_PORT", str(port)))
        self._client = None

    def _connect(self) -> None:
        try:
            from ib_insync import IB
            self._ib = IB()
            self._ib.connect(self.host, self.port, clientId=1)
        except ImportError:
            raise ImportError(
                "ib_insync not installed. Run: pip install ib_insync\n"
                "Or install via: pip install -e lab[ibkr]"
            )

    def _ensure_connected(self) -> None:
        if self._ib is None or not self._ib.isConnected():
            self._connect()

    def fetch(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        self._ensure_connected()

        tf_label, tf_bar_size = self._map_timeframe(timeframe)

        bar_size_setting = self._ib.barSizeToStr(tf_bar_size)

        contract = self._resolve_contract(symbol)

        end_dt = None
        if end:
            end_dt = pd.to_datetime(end)
        else:
            end_dt = datetime.now()

        duration = self._period_to_duration(period, timeframe) if period else "1 Y"

        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime=end_dt,
            durationStr=duration,
            barSizeSetting=bar_size_setting,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )

        if not bars:
            raise ValueError(f"No data returned for {symbol} from IBKR")

        df = pd.DataFrame([{
            "timestamp": bar.date,
            "Open": bar.open,
            "High": bar.high,
            "Low": bar.low,
            "Close": bar.close,
            "Volume": bar.volume,
        } for bar in bars])

        df = df.set_index("timestamp")

        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]

        return df

    def _map_timeframe(self, timeframe: str) -> tuple[str, int]:
        if timeframe in self.TIMEFRAME_MAP:
            return self.TIMEFRAME_MAP[timeframe]
        return "1 day", 1440

    def _period_to_duration(self, period: str, timeframe: str) -> str:
        """Convert period string to IBKR duration."""
        duration_map = {
            "1d": "1 D",
            "5d": "5 D",
            "1mo": "1 M",
            "3mo": "3 M",
            "6mo": "6 M",
            "1y": "1 Y",
            "2y": "2 Y",
            "5y": "5 Y",
            "10y": "10 Y",
        }
        return duration_map.get(period, "1 Y")

    def _resolve_contract(self, symbol: str):
        self._ensure_connected()
        from ib_insync import Stock, Forex, Contract

        forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
        if symbol.upper() in [p.upper() for p in forex_pairs]:
            pair = symbol.replace("/", "").upper()
            if len(pair) == 6:
                base = pair[:3]
                quote = pair[3:]
                return Forex(pair, exchange="IDEALPRO")
            return Forex(symbol.upper(), exchange="IDEALPRO")

        return Stock(symbol, "SMART", "USD")

    def close(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
