"""Manager / Safety Agent scaffold. Owner: Duy."""

from src.common.agent_contracts import ManagerAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import AgentState
from src.common.tool_contracts import SafetyTools


class ManagerAgent:
    def __init__(self, tools: SafetyTools, config: SimulationConfig) -> None:
        self.tools, self.config = tools, config

    def run(self, state: AgentState) -> ManagerAgentUpdate:
        """Proposed: deterministic STOW > safe HOLD > economic ROTATE."""
        raise NotImplementedError("Manager / Safety Agent implementation awaits approval")
