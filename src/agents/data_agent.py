"""Data Agent scaffold. Owner: Luan."""

from src.common.agent_contracts import DataAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import AgentState
from src.common.tool_contracts import WeatherRequest, WeatherTools


class DataAgent:
    def __init__(self, tools: WeatherTools, request: WeatherRequest, config: SimulationConfig) -> None:
        self.tools, self.request, self.config = tools, request, config

    def run(self, state: AgentState) -> DataAgentUpdate:
        """Proposed: coordinate validation, retries and cache fallback."""
        raise NotImplementedError("Data Agent implementation awaits approval")
