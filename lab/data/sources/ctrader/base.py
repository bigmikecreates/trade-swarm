"""Base interface for cTrader Open API brokers.

Each broker implements this interface with their specific:
  - API endpoint
  - OAuth2 credentials
  - Symbol naming conventions

To set up cTrader:
  1. Open a demo account with IC Markets, Pepperstone, or Eightcap
  2. Register an app on the broker's developer portal to get Client ID + Client Secret
  3. Configure broker credentials in lab/config/lab_config.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd
import time
from datetime import datetime


class BaseCTraderBroker(ABC):
    """Abstract base for cTrader broker implementations."""

    ENDPOINT: str = ""
    NAME: str = ""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self._authenticate()

    @abstractmethod
    def _authenticate(self) -> None:
        """Authenticate with the broker's cTrader Open API."""
        ...

    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Return available symbols for this broker."""
        ...

    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "M1",
        count: int = 1000,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol.

        Args:
            symbol: Broker-specific symbol name (e.g., "EURUSD")
            timeframe: Candle timeframe (M1, M5, M15, H1, H4, D1)
            count: Number of candles to fetch
            start: Start datetime
            end: End datetime

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        ...

    def _parse_timeframe(self, timeframe: str) -> int:
        """Map human timeframe to cTrader timeframe ID."""
        mapping = {
            "M1": 1,
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "D1": 1440,
            "W1": 10080,
            "MN1": 43200,
        }
        return mapping.get(timeframe, 1)

    def _timeframe_to_string(self, timeframe_id: int) -> str:
        """Map cTrader timeframe ID to string."""
        mapping = {
            1: "M1",
            5: "M5",
            15: "M15",
            30: "M30",
            60: "H1",
            240: "H4",
            1440: "D1",
            10080: "W1",
            43200: "MN1",
        }
        return mapping.get(timeframe_id, "M1")
