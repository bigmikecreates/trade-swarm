"""Regime agent — classifies market regime using rule-based and HMM methods."""

from __future__ import annotations

import pandas as pd
import numpy as np

from lab.agents.regime.base import BaseRegimeAgent, RegimeEvent, MarketRegime


class RuleBasedRegimeAgent(BaseRegimeAgent):
    """Rule-based regime classifier using:
    - ADX for trend strength
    - ATR ratio for volatility
    - Price position for trend direction
    """

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        adx_period: int = 14,
        atr_period: int = 14,
        adx_strong_threshold: float = 25,
        atr_lookback: int = 20,
        **kwargs,
    ):
        super().__init__(symbol, **kwargs)
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.adx_strong_threshold = adx_strong_threshold
        self.atr_lookback = atr_lookback

    def classify(self, df: pd.DataFrame) -> RegimeEvent:
        """Classify current market regime."""
        self._require_cols(df, ["High", "Low", "Close"])
        
        adx = self._calculate_adx(df)
        atr_ratio = self._calculate_atr_ratio(df)
        trend_direction = self._calculate_trend_direction(df)
        
        regime, confidence = self._determine_regime(
            adx, atr_ratio, trend_direction
        )
        
        return RegimeEvent(
            regime=regime,
            confidence=confidence,
            indicators={
                "adx": adx,
                "atr_ratio": atr_ratio,
                "trend_direction": trend_direction,
            },
        )

    def _calculate_adx(self, df: pd.DataFrame) -> float:
        """Calculate Average Directional Index."""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=self.atr_period).mean()
        plus_di = (plus_dm.rolling(window=self.adx_period).mean() / atr) * 100
        minus_di = (minus_dm.rolling(window=self.adx_period).mean() / atr) * 100
        
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        adx = dx.rolling(window=self.adx_period).mean()
        
        return float(adx.iloc[-1]) if len(adx) > 0 else 0.0

    def _calculate_atr_ratio(self, df: pd.DataFrame) -> float:
        """Calculate ATR as ratio to historical average."""
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=self.atr_period).mean()
        current_atr = atr.iloc[-1]
        
        historical_avg = atr.tail(self.atr_lookback).mean()
        
        if historical_avg <= 0:
            return 1.0
        
        return float(current_atr / historical_avg)

    def _calculate_trend_direction(self, df: pd.DataFrame) -> str:
        """Determine trend direction from price position."""
        close = df["Close"]
        sma_20 = close.rolling(window=20).mean()
        
        if len(sma_20) < 2:
            return "neutral"
        
        current_price = close.iloc[-1]
        current_sma = sma_20.iloc[-1]
        
        if current_price > current_sma * 1.02:
            return "bullish"
        elif current_price < current_sma * 0.98:
            return "bearish"
        else:
            return "neutral"

    def _determine_regime(
        self,
        adx: float,
        atr_ratio: float,
        trend_direction: str
    ) -> tuple[MarketRegime, float]:
        """Determine regime from indicators."""
        if adx < 15:
            return MarketRegime.CONSOLIDATION, 0.6
        
        is_trending = adx >= self.adx_strong_threshold
        is_high_vol = atr_ratio > 1.5
        is_low_vol = atr_ratio < 0.7
        
        if is_high_vol:
            if is_trending:
                if trend_direction == "bullish":
                    return MarketRegime.BULL_TREND, 0.7
                elif trend_direction == "bearish":
                    return MarketRegime.BEAR_TREND, 0.7
            return MarketRegime.HIGH_VOLATILITY, 0.65
        
        if is_low_vol:
            return MarketRegime.LOW_VOLATILITY, 0.7
        
        if is_trending:
            if trend_direction == "bullish":
                return MarketRegime.BULL_TREND, 0.75
            elif trend_direction == "bearish":
                return MarketRegime.BEAR_TREND, 0.75
        
        return MarketRegime.CONSOLIDATION, 0.5


class HMMRegimeAgent(BaseRegimeAgent):
    """Hidden Markov Model regime classifier using hmmlearn.
    
    Uses Gaussian HMM to detect latent market regimes.
    """

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        n_states: int = 3,
        covariance_type: str = "full",
        n_iter: int = 100,
        **kwargs,
    ):
        super().__init__(symbol, **kwargs)
        self.n_states = n_states
        self.covariance_type = covariance_type
        self.n_iter = n_iter
        self._model = None
        self._fitted = False

    def classify(self, df: pd.DataFrame) -> RegimeEvent:
        """Classify current market regime using HMM."""
        self._require_cols(df, ["Close", "High", "Low", "Volume"])
        
        features = self._prepare_features(df)
        
        if len(features) < 50:
            return RegimeEvent(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                indicators={"error": "Insufficient data for HMM"},
            )
        
        regime_idx = self._predict_regime(features)
        regime, confidence = self._map_state_to_regime(regime_idx, features)
        
        return RegimeEvent(
            regime=regime,
            confidence=confidence,
            indicators={
                "state": int(regime_idx),
                "n_states": self.n_states,
            },
        )

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare features for HMM."""
        returns = df["Close"].pct_change().dropna()
        
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        
        volatility = returns.rolling(window=10).std()
        volume = df["Volume"]
        volume_ma = volume.rolling(window=20).mean()
        volume_ratio = volume / volume_ma
        
        atr = (high - low).rolling(window=14).mean()
        price_position = (close - low.rolling(window=20).min()) / (
            high.rolling(window=20).max() - low.rolling(window=20).min()
        )
        
        features_df = pd.DataFrame({
            "returns": returns,
            "volatility": volatility,
            "volume_ratio": volume_ratio,
            "atr": atr,
            "price_position": price_position,
        }).dropna()
        
        return features_df.values

    def _predict_regime(self, features: np.ndarray) -> int:
        """Predict regime using fitted HMM."""
        try:
            from hmmlearn.hmm import GaussianHMM
            
            if not self._fitted:
                self._model = GaussianHMM(
                    n_components=self.n_states,
                    covariance_type=self.covariance_type,
                    n_iter=self.n_iter,
                    random_state=42,
                )
                self._model.fit(features)
                self._fitted = True
            
            return self._model.predict(features[-1:])[0]
            
        except ImportError:
            return 0

    def _map_state_to_regime(
        self, 
        state: int, 
        features: np.ndarray
    ) -> tuple[MarketRegime, float]:
        """Map HMM state to market regime."""
        if self._model is None:
            return MarketRegime.UNKNOWN, 0.0
        
        try:
            means = self._model.means_
            volatilities = means[:, 1] if means.shape[1] > 1 else means[:, 0]
            
            sorted_states = np.argsort(volatilities)
            low_vol_state = sorted_states[0]
            high_vol_state = sorted_states[-1]
            
            if state == low_vol_state:
                return MarketRegime.LOW_VOLATILITY, 0.7
            elif state == high_vol_state:
                return MarketRegime.HIGH_VOLATILITY, 0.7
            
            returns = features[:, 0]
            avg_return = np.mean(returns)
            
            if avg_return > 0:
                return MarketRegime.BULL_TREND, 0.6
            else:
                return MarketRegime.BEAR_TREND, 0.6
                
        except Exception:
            return MarketRegime.UNKNOWN, 0.0
