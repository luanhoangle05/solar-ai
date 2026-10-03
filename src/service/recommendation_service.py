"""Recommendation service interface; no web framework selected yet."""

from src.common.agent_contracts import OrchestratorContract
from src.common.schema import AgentState, FrontendData


def get_recommendation(state: AgentState, orchestrator: OrchestratorContract) -> FrontendData:
    """Future validated frontend payload; safe errors must also be represented."""
    raise NotImplementedError("Recommendation service implementation awaits approval")
