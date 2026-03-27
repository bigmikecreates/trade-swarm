"""Pepperstone cTrader Open API implementation.

Setup:
  1. Open demo account: https://www.pepperstone.com/en/register
  2. Get cTrader Open API credentials from Pepperstone developer portal
  3. Set env vars: export CTRADER_PEPPERSTONE_CLIENT_ID=xxx CTRADER_PEPPERSTONE_CLIENT_SECRET=xxx
"""

from __future__ import annotations

import requests
import pandas as pd
from datetime import datetime, timedelta

from lab.data.sources.ctrader.base import BaseCTraderBroker


class PepperstoneCTrader(BaseCTraderBroker):
    """Pepperstone cTrader Open API broker."""

    ENDPOINT = "https://pepperstone.com"
    NAME = "Pepperstone"
    AUTH_URL = "https://pepperstone.com/ctid/token"
    API_URL = "https://api.pepperstone.com"

    TIMEFRAMES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
    ):
        import os
        self.client_id = client_id or os.environ.get("CTRADER_PEPPERSTONE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("CTRADER_PEPPERSTONE_CLIENT_SECRET", "")
        self.access_token = access_token
        if self.client_id and self.client_secret and not self.access_token:
            self._authenticate()

    def _authenticate(self) -> None:
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Pepperstone cTrader credentials not set. "
                "Set CTRADER_PEPPERSTONE_CLIENT_ID and CTRADER_PEPPERSTONE_CLIENT_SECRET env vars."
            )

        response = requests.post(
            self.AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Pepperstone auth failed: {response.status_code} {response.text}")
        data = response.json()
        self.access_token = data["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_symbols(self) -> list[str]:
        if not self.access_token:
            return []
        try:
            response = requests.get(
                f"{self.API_URL}/v2/symbols",
                headers=self._headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return [s["symbol"] for s in response.json().get("symbols", [])]
        except Exception:
            pass
        return []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "M1",
        count: int = 1000,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        if not self.access_token:
            raise RuntimeError("Not authenticated with Pepperstone. Provide credentials first.")

        tf_id = self.TIMEFRAMES.get(timeframe, 1)
        period_start = int((start or datetime.utcnow() - timedelta(days=7)).timestamp())
        period_end = int((end or datetime.utcnow()).timestamp())

        response = requests.get(
            f"{self.API_URL}/v2/candles",
            headers=self._headers(),
            params={
                "symbol": symbol,
                "timeframe": tf_id,
                "from": period_start,
                "to": period_end,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Pepperstone API error: {response.status_code} {response.text}")

        data = response.json()
        candles = data.get("candles", [])

        if not candles:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        rows = []
        for c in candles:
            rows.append({
                "timestamp": datetime.fromtimestamp(c["timestamp"]),
                "Open": c["open"],
                "High": c["high"],
                "Low": c["low"],
                "Close": c["close"],
                "Volume": c["volume"],
            })

        df = pd.DataFrame(rows).set_index("timestamp")
        return df[["Open", "High", "Low", "Close", "Volume"]]
