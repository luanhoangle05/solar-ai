"""Optimization Agent scaffold. Owner: Duy."""

from src.common.agent_contracts import OptimizationAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import AgentState
from src.common.tool_contracts import OptimizationTools


class OptimizationAgent:
    def __init__(self, tools: OptimizationTools, config: SimulationConfig) -> None:
        self.tools, self.config = tools, config

    def run(self, state: AgentState) -> OptimizationAgentUpdate:
        """Proposed: maximize net gain using modeling.candidate_predictions."""
        raise NotImplementedError("Optimization Agent implementation awaits approval")
