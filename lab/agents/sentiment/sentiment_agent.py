"""Sentiment agent — analyzes news and alternative data for sentiment."""

from __future__ import annotations

import random

from lab.agents.sentiment.base import (
    BaseSentimentAgent, 
    SentimentEvent, 
    SentimentDirection
)


class SentimentAgent(BaseSentimentAgent):
    """Sentiment agent that:
    - Placeholder for real sentiment analysis (FinBERT, etc.)
    - Returns neutral sentiment by default
    - Can integrate with news APIs when configured
    """

    def __init__(
        self,
        symbol: str = "SYNTHETIC",
        use_news_api: bool = False,
        news_api_key: str = "",
        cache_minutes: int = 15,
        **kwargs,
    ):
        super().__init__(symbol, **kwargs)
        self.use_news_api = use_news_api
        self.news_api_key = news_api_key
        self.cache_minutes = cache_minutes
        self._cache = {}

    def analyze(self, symbol: str) -> SentimentEvent:
        """Analyze sentiment for a symbol.
        
        In backtest mode, returns neutral sentiment.
        In live mode with API configured, fetches real sentiment.
        """
        if self.use_news_api and self.news_api_key:
            return self._analyze_with_api(symbol)
        
        return self._analyze_placeholder(symbol)

    def _analyze_placeholder(self, symbol: str) -> SentimentEvent:
        """Placeholder sentiment analysis.
        
        Returns neutral sentiment for backtesting.
        In production, this would integrate with:
        - FinBERT for financial news
        - Twitter/Reddit sentiment
        - Analyst ratings
        """
        return SentimentEvent(
            sentiment=SentimentDirection.NEUTRAL,
            score=0.0,
            confidence=0.0,
            sources=["placeholder"],
            indicators={
                "mode": "backtest",
                "note": "Configure news API for live sentiment",
            },
        )

    def _analyze_with_api(self, symbol: str) -> SentimentEvent:
        """Analyze sentiment using news API.
        
        Placeholder for real implementation.
        Would integrate with:
        - NewsAPI.org
        - Alpha Vantage News Sentiment
        - FinBERT model
        """
        return SentimentEvent(
            sentiment=SentimentDirection.NEUTRAL,
            score=0.0,
            confidence=0.5,
            sources=["news_api"],
            indicators={
                "mode": "api_configured_but_not_implemented",
                "symbol": symbol,
            },
        )


class DummySentimentAgent(BaseSentimentAgent):
    """Dummy sentiment agent for testing - returns random sentiment.
    
    Use only for testing/development.
    """

    def analyze(self, symbol: str) -> SentimentEvent:
        """Return random sentiment for testing."""
        sentiments = [
            SentimentDirection.BULLISH,
            SentimentDirection.NEUTRAL,
            SentimentDirection.BEARISH,
        ]
        
        sentiment = random.choice(sentiments)
        
        score_map = {
            SentimentDirection.BULLISH: 0.6,
            SentimentDirection.NEUTRAL: 0.0,
            SentimentDirection.BEARISH: -0.6,
        }
        
        return SentimentEvent(
            sentiment=sentiment,
            score=score_map[sentiment],
            confidence=0.5,
            sources=["dummy"],
            indicators={"mode": "dummy_for_testing"},
        )
