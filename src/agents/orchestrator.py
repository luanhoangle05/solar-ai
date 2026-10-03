"""Lightweight state-machine interface. Owners: all three at integration."""

from src.common.agent_contracts import (
    DataAgentContract, ManagerAgentContract, ModelingAgentContract,
    OptimizationAgentContract,
)
from src.common.schema import AgentState, FrontendData


class Orchestrator:
    """Proposed flow: Data -> Modeling -> Optimization -> Safety -> frontend.

    Errors and unreliable data must route to Safety before any command;
    no model/optimizer success may be fabricated to complete the normal path.
    """

    def __init__(self, data: DataAgentContract, modeling: ModelingAgentContract,
                 optimization: OptimizationAgentContract, manager: ManagerAgentContract) -> None:
        self.data, self.modeling = data, modeling
        self.optimization, self.manager = optimization, manager

    def run(self, state: AgentState) -> FrontendData:
        """Proposed: own lifecycle, merge outputs, record traces and errors."""
        raise NotImplementedError("Orchestration implementation awaits approval")
