"""Agent coordinator — wire multiple agents together in coordinated mode."""

from __future__ import annotations

from typing import Any


class AgentCoordinator:
    """Coordinates multiple agents in a pipeline.
    
    In coordinated mode, agents communicate via events.
    The coordinator wires the pipeline and manages event flow.
    
    Pipeline order:
        RegimeAgent → SignalAgent → RiskAgent → ExecutionAgent
    """

    def __init__(self):
        self.agents: dict[str, object] = {}
        self.pipeline: list[str] = []

    def register(self, name: str, agent: object) -> None:
        """Register an agent."""
        self.agents[name] = agent

    def set_pipeline(self, pipeline: list[str]) -> None:
        """Set the execution pipeline order.
        
        Args:
            pipeline: List of agent names in execution order
                      e.g. ["regime", "signal", "risk", "execution"]
        """
        self.pipeline = pipeline

    def run(self, bar: dict, context: dict) -> dict:
        """Run the pipeline for a single bar.
        
        Args:
            bar: OHLCV data for current bar
            context: Shared context (positions, equity, etc.)
            
        Returns:
            Final event from the last agent in the pipeline
        """
        event = bar

        for agent_name in self.pipeline:
            agent = self.agents.get(agent_name)
            if agent is None:
                continue

            if hasattr(agent, "process"):
                event = agent.process(event, context)
            elif hasattr(agent, "generate"):
                event = agent.generate(event)

        return event

    def broadcast_regime_change(self, regime_event: object) -> None:
        """Broadcast regime change to all agents that listen for it."""
        for agent in self.agents.values():
            if hasattr(agent, "on_regime_change"):
                agent.on_regime_change(regime_event)

    def get_active_agents(self) -> list[str]:
        """Return list of active agent names in pipeline."""
        return self.pipeline.copy()
