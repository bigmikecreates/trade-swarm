"""Agent factory — build agents by name from registry."""

from __future__ import annotations

from typing import Any


class AgentFactory:
    """Factory for building agents by name.
    
    Add new agents to the REGISTRY dict.
    No other code changes needed to add a new agent.
    """

    REGISTRY: dict[str, type] = {}

    def __init__(self):
        self._instances: dict[str, object] = {}

    def register(self, name: str, agent_cls: type) -> None:
        """Register an agent class under a name."""
        self.REGISTRY[name] = agent_cls

    def build(self, name: str, **params: Any) -> object:
        """Build an agent by name with given parameters."""
        if name not in self.REGISTRY:
            available = ", ".join(self.REGISTRY.keys())
            raise ValueError(f"Unknown agent: {name}. Available: {available}")
        agent_cls = self.REGISTRY[name]
        return agent_cls(**params)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self.REGISTRY.keys())


def register_agent(name: str):
    """Decorator to register an agent class."""
    def decorator(cls: type):
        AgentFactory.REGISTRY[name] = cls
        return cls
    return decorator
