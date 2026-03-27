"""Signal agents — all registered with the agent factory."""

from __future__ import annotations

from lab.agents.signal.trend_agent import TrendSignalAgent
from lab.agents.signal.mean_reversion import MeanReversionSignalAgent
from lab.agents.signal.breakout import BreakoutSignalAgent
from lab.agents.signal.momentum import MomentumSignalAgent
from lab.agents.signal.base import SignalEvent, SignalDirection

__all__ = [
    "TrendSignalAgent",
    "MeanReversionSignalAgent",
    "BreakoutSignalAgent",
    "MomentumSignalAgent",
    "SignalEvent",
    "SignalDirection",
]
