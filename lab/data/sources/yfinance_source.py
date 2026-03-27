"""Yahoo Finance data source — free, real market data for equities, ETFs, crypto."""

from __future__ import annotations

import pandas as pd
import yfinance as yf
from datetime import datetime


class YahooFinanceFetcher:
    """Fetch OHLCV data from Yahoo Finance.

    Supports: equities, ETFs, crypto, indices.
    Timeframes: 1m (7d), 5m (60d), 15m (60d), 1h (730d), 1d (max), 1wk (max), 1mo (max)

    Usage:
        fetcher = YahooFinanceFetcher()
        df = fetcher.fetch(symbol="SPY", period="5y", timeframe="1d")
    """

    TIMEFRAME_MAP = {
        "1m": ("1m", "7d"),
        "5m": ("5m", "60d"),
        "15m": ("15m", "60d"),
        "1h": ("60m", "730d"),
        "1d": ("1d", "max"),
        "1wk": ("1wk", "max"),
        "1mo": ("1mo", "max"),
        "M1": ("1m", "7d"),
        "M5": ("5m", "60d"),
        "M15": ("15m", "60d"),
        "H1": ("60m", "730d"),
        "H4": ("240m", "730d"),
    }

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir

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
        yf_timeframe, yf_period = self._map_timeframe(timeframe, period, start, end)

        ticker = yf.Ticker(symbol)
        df = ticker.history(
            period=yf_period,
            start=start,
            end=end,
            interval=yf_timeframe,
            auto_adjust=True,
        )

        if df.empty:
            raise ValueError(f"No data returned for {symbol}. Check symbol is valid on Yahoo Finance.")

        df = df.rename(columns={
            "Open": "Open",
            "High": "High",
            "Low": "Low",
            "Close": "Close",
            "Volume": "Volume",
        })
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.index = df.index.tz_localize(None) if df.index.tz else df.index

        return df

    def _map_timeframe(self, timeframe: str, period: str | None, start: str | None, end: str | None) -> tuple[str, str]:
        if period:
            if timeframe in self.TIMEFRAME_MAP:
                return self.TIMEFRAME_MAP[timeframe]
            return "1d", period

        if start and end:
            return timeframe, "1d"

        return "1d", "1mo"

    def list_symbols(self, query: str) -> list[str]:
        """Search for symbols by query."""
        import yfinance as yf
        results = yf.search(query)
        if results is None or results.empty:
            return []
        return results["symbol"].tolist()[:20]
