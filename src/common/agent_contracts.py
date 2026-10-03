"""Agents return owned sections; the orchestrator merges them into state.

Passed state is read-only by convention: agents must not mutate it. A future
orchestrator will pass isolated snapshots and append logs centrally.
"""

from typing import Protocol, TypedDict, runtime_checkable

from src.common.schema import (
    AgentLogEntry, AgentState, DataAgentReport, Decision, FrontendData,
    ModelingResult, OptimizationResult, SafetyResult, ToolCall, WeatherFeatures,
)


class StageTrace(TypedDict):
    agent_log: list[AgentLogEntry]
    tool_calls: list[ToolCall]


class DataAgentUpdate(StageTrace):
    data: DataAgentReport
    weather: WeatherFeatures | None


class ModelingAgentUpdate(StageTrace):
    modeling: ModelingResult


class OptimizationAgentUpdate(StageTrace):
    optimization: OptimizationResult


class ManagerAgentUpdate(StageTrace):
    safety: SafetyResult
    decision: Decision


@runtime_checkable
class DataAgentContract(Protocol):
    def run(self, state: AgentState) -> DataAgentUpdate: ...


@runtime_checkable
class ModelingAgentContract(Protocol):
    def run(self, state: AgentState) -> ModelingAgentUpdate: ...


@runtime_checkable
class OptimizationAgentContract(Protocol):
    def run(self, state: AgentState) -> OptimizationAgentUpdate: ...


@runtime_checkable
class ManagerAgentContract(Protocol):
    def run(self, state: AgentState) -> ManagerAgentUpdate: ...


@runtime_checkable
class OrchestratorContract(Protocol):
    def run(self, state: AgentState) -> FrontendData: ...
