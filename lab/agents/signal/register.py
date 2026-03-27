"""Register all signal agents with the factory."""

from lab.harness.factory import AgentFactory

AgentFactory.REGISTRY["trend_signal"] = __import__(
    "lab.agents.signal.trend_agent", fromlist=["TrendSignalAgent"]
).TrendSignalAgent

AgentFactory.REGISTRY["mean_reversion"] = __import__(
    "lab.agents.signal.mean_reversion", fromlist=["MeanReversionSignalAgent"]
).MeanReversionSignalAgent

AgentFactory.REGISTRY["breakout"] = __import__(
    "lab.agents.signal.breakout", fromlist=["BreakoutSignalAgent"]
).BreakoutSignalAgent

AgentFactory.REGISTRY["momentum"] = __import__(
    "lab.agents.signal.momentum", fromlist=["MomentumSignalAgent"]
).MomentumSignalAgent
