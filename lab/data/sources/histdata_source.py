"""HISTDATA.com source — free M1 forex data.

HISTDATA.com provides free historical forex data in CSV format.

Setup:
  1. Download data from https://www.histdata.com/download-free-forex-data/
  2. Extract to lab/data/histdata/ directory
  3. Files should follow pattern: EURUSD/M1/DAT_ASCII_M1_EURUSD.txt

The download is free but requires manual download. Download once, use forever.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime


class HistDataFetcher:
    """Fetch M1 forex data from locally downloaded HISTDATA.com files.

    Expected directory structure:
        lab/data/histdata/
            EURUSD/M1/DAT_ASCII_M1_EURUSD.txt
            GBPUSD/M1/DAT_ASCII_M1_GBPUSD.txt
            ...

    Download from: https://www.histdata.com/download-free-forex-data/
    """

    TIMEFRAME_MAP = {
        "M1": "M1",
        "1m": "M1",
    }

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "histdata"
        else:
            self.data_dir = Path(data_dir)

    def fetch(
        self,
        symbol: str,
        timeframe: str = "M1",
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        symbol_upper = symbol.upper()
        tf_folder = self.TIMEFRAME_MAP.get(timeframe, "M1")
        file_path = self.data_dir / symbol_upper / tf_folder / f"DAT_ASCII_{tf_folder}_{symbol_upper}.txt"

        if not file_path.exists():
            raise FileNotFoundError(
                f"HISTDATA file not found: {file_path}\n"
                f"Download from: https://www.histdata.com/download-free-forex-data/\n"
                f"Extract to: {file_path.parent.parent.parent / symbol_upper / 'M1'}/"
            )

        df = pd.read_csv(
            file_path,
            names=["Date", "Time", "Open", "High", "Low", "Close", "Volume"],
            sep=";",
        )

        df["timestamp"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H%M%S")
        df = df.set_index("timestamp")
        df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)

        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]

        return df

    def available_symbols(self) -> list[str]:
        """List available symbols based on downloaded files."""
        symbols = []
        if not self.data_dir.exists():
            return symbols
        for sym_dir in self.data_dir.iterdir():
            if sym_dir.is_dir():
                m1_dir = sym_dir / "M1"
                if m1_dir.exists() and any(m1_dir.glob("*.txt")):
                    symbols.append(sym_dir.name)
        return sorted(symbols)
