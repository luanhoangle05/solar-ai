"""Modeling Agent scaffold. Owner: Duy."""

from src.common.agent_contracts import ModelingAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import AgentState
from src.common.tool_contracts import ModelingTools


class ModelingAgent:
    def __init__(self, tools: ModelingTools, config: SimulationConfig) -> None:
        self.tools, self.config = tools, config

    def run(self, state: AgentState) -> ModelingAgentUpdate:
        """Proposed: compare available models and predict candidate energy."""
        raise NotImplementedError("Modeling Agent implementation awaits approval")
