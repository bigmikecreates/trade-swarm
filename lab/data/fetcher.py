"""Data fetcher — unified interface for all market data sources."""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from lab.data.sources.synthetic_gbm import SyntheticGBMFetcher


class DataFetcher:
    """Unified interface for all data sources.

    Agents and harness always call fetcher.get_ohlcv().
    The source is configured per call — no code changes needed to swap sources.
    """

    _SOURCES: dict[str, type] = {}

    def __init__(self):
        self._fetchers: dict[str, object] = {}
        self._register_all_sources()

    def _register_all_sources(self) -> None:
        from lab.data.sources.yfinance_source import YahooFinanceFetcher
        from lab.data.sources.histdata_source import HistDataFetcher
        from lab.data.sources.ibkr_source import IBKRSource

        DataFetcher._SOURCES = {
            "synthetic": SyntheticGBMFetcher,
            "yfinance": YahooFinanceFetcher,
            "histdata": HistDataFetcher,
            "ibkr": IBKRSource,
        }

    def get_ohlcv(
        self,
        symbol: str,
        source: str,
        timeframe: str = "1d",
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch OHLCV data from the specified source.

        Args:
            symbol: Asset symbol (e.g. "EURUSD", "SPY")
            source: Data source name
            timeframe: Candle timeframe (e.g. "M1", "1d")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            period: Alternative to start/end (e.g. "1y", "60d")
            use_cache: Whether to use cached data if available
            **kwargs: Source-specific parameters

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        if source not in DataFetcher._SOURCES:
            available = ", ".join(DataFetcher._SOURCES.keys())
            raise ValueError(f"Unknown source: {source}. Available: {available}")

        if source not in self._fetchers:
            self._fetchers[source] = DataFetcher._SOURCES[source]()

        fetcher = self._fetchers[source]
        return fetcher.fetch(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            period=period,
            use_cache=use_cache,
            **kwargs,
        )

    @classmethod
    def register_source(cls, name: str, fetcher_cls: type) -> None:
        """Register a new data source at runtime."""
        cls._SOURCES[name] = fetcher_cls

    @classmethod
    def available_sources(cls) -> list[str]:
        """Return list of available data sources."""
        return list(cls._SOURCES.keys())
