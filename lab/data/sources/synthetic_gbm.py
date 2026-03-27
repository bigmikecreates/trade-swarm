"""Synthetic GBM data source for the data fetcher."""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from lab.synthetic.generator import SyntheticGenerator


class SyntheticGBMFetcher:
    """Data source that generates synthetic OHLCV using GBM.
    
    Uses the synthetic generator to produce reproducible market data.
    """

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = config_path

    def fetch(
        self,
        symbol: str,
        timeframe: str = "M1",
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
        seed: int | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data.
        
        The symbol is used for reference only — all synthetic data is generated
        based on the configured GBM parameters.
        """
        if self.config_path is None:
            default_path = Path(__file__).resolve().parents[2] / "synthetic" / "configs" / "default.yaml"
            self.config_path = default_path

        generator = SyntheticGenerator(self.config_path)
        df = generator.generate(seed=seed)

        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]

        return df
