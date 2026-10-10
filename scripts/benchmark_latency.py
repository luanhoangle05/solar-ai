"""Owner: Duy. Measure how long each part of an agent run takes on this machine.

Times model training, the one-off validation scoring, single predictions, each
agent stage, a whole decision, the LLM explanation call and the live weather
fetch, and writes the measurements to `data/evaluation/latency.json`.

These are wall-clock timings of this prototype on whatever machine runs the
script (CPU only). They are not a performance guarantee and will differ elsewhere.

Run from the repository root:  python -m scripts.benchmark_latency
"""

import argparse
import json
import logging
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Callable, Sequence

from src.agents import orchestrator as stages
from src.agents.reasoning import Reasoner, load_reasoner
from src.agents.trace import TraceRecorder, utc_now_iso
from src.common.config import DEFAULT_CONFIG, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG
from src.common.schema import AgentState, WeatherFeatures
from src.common.tool_contracts import ToolError
from src.models.advanced import boosting, lstm
from src.models.advanced.features import split_for_early_stopping
from src.models.data_loader import ROOT, DatasetSource, default_dataset_source, hourly_weather, load_dataset_split
from src.models.evaluation import EvaluatedModelingTools, ModelCandidate
from src.service.live_data_agent import SystemTrustOpenMeteoClient, current_hour_request
from src.service.recommendation_service import (
    DEFAULT_IMPLEMENTATIONS, RecordedWeatherDataAgent, build_agents, build_metadata, recommend_for_recorded_hour, simulated_farm_status,
)
from scripts.run_recommendation import CONTROL_TARGET_ID, pick_hour


LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "latency.json"
CURRENT_ANGLE_DEG = 60.0
DECISION_REPEATS = 30
PREDICTION_REPEATS = 100
LLM_REPEATS = 3
FETCH_REPEATS = 3
LLM_SAMPLE_FACTS = "optimize_angle [OK]: recommended 30 deg, net benefit +0.7182 kWh-eq\nrecommendation: gain +0.808 kWh, movement cost 0.090"


def timed(run: Callable[[], object]) -> tuple[float, object]:
    start = time.perf_counter()
    result = run()
    return time.perf_counter() - start, result


def summarize(seconds: Sequence[float]) -> dict:
    """Milliseconds: median, mean and the slowest and fastest of the repeats."""
    values = sorted(value * 1000 for value in seconds)
    return {
        "repeats": len(values), "median_ms": round(statistics.median(values), 3), "mean_ms": round(statistics.fmean(values), 3),
        "min_ms": round(values[0], 3), "max_ms": round(values[-1], 3),
    }


def repeat(run: Callable[[], object], count: int) -> dict:
    return summarize([timed(run)[0] for _ in range(count)])


def train_models(source: DatasetSource, metadata: dict) -> tuple[EvaluatedModelingTools, dict]:
    split = load_dataset_split(source)
    rows = [*split.train, *split.validation, *split.test]
    fit_rows, stop_rows = split_for_early_stopping(split.train)
    boosting_seconds, boosting_model = timed(lambda: boosting.train_boosting(fit_rows, stop_rows))
    lstm_seconds, lstm_model = timed(lambda: lstm.train_lstm(fit_rows, stop_rows, hourly_weather(rows)))
    trained = {boosting.MODEL_NAME: boosting_model, lstm.MODEL_NAME: lstm_model}
    candidates = [
        ModelCandidate(model, DEFAULT_IMPLEMENTATIONS[model], predictor=trained.get(model), unavailable_reason=None if model in trained else "adapter not delivered yet")
        for model in ("linear_regression", "random_forest", "boosting", "lstm")
    ]
    tools = EvaluatedModelingTools(candidates, split.validation, metadata=metadata)
    scoring_seconds, _ = timed(tools.evaluate_models)
    report = {
        "train_rows": len(split.train), "validation_rows": len(split.validation),
        "boosting_training_s": round(boosting_seconds, 1), "lstm_training_s": round(lstm_seconds, 1),
        "validation_scoring_of_all_models_s": round(scoring_seconds, 1),
    }
    return tools, report


def measure_predictions(tools: EvaluatedModelingTools, weather: WeatherFeatures, metadata: dict) -> dict:
    angles = DEFAULT_CONFIG.candidate_angles_deg
    return {
        "candidate_angles": len(angles),
        **{model: repeat(lambda: tools.get_predictor(model).predict_kwh(weather, angles, metadata=metadata), PREDICTION_REPEATS) for model in (boosting.MODEL_NAME, lstm.MODEL_NAME)},
    }


def measure_stages(source: DatasetSource, tools: EvaluatedModelingTools, weather: WeatherFeatures, metadata: dict) -> dict:
    """Each agent timed on its own, without the LLM, on the same recorded hour."""
    farm = simulated_farm_status(weather["panel_angle_deg"])
    states = {row["row_id"]: {"angle_deg": row["angle_deg"], "current_state": row["current_state"]} for row in farm["rows"]}
    agents = build_agents(tools, DEFAULT_CONFIG, row_status=states.__getitem__)
    data_agent = RecordedWeatherDataAgent(weather, source)
    samples: dict[str, list[float]] = {"data": [], "modeling": [], "optimization": [], "manager": []}
    for _ in range(DECISION_REPEATS):
        state: AgentState = {
            "run_id": "benchmark", "timestamp": utc_now_iso(), "metadata": metadata, "stage": "PENDING",
            "weather": None, "data": None, "modeling": None, "optimization": None, "safety": None, "decision": None,
            "agent_log": [], "tool_calls": [], "errors": [],
        }
        for name, agent, stage in (("data", data_agent, "DATA"), ("modeling", agents.modeling, "MODELING"), ("optimization", agents.optimization, "OPTIMIZATION"), ("manager", agents.manager, "COMPLETE")):
            seconds, update = timed(lambda: agent.run(state))
            samples[name].append(seconds)
            state = stages.merge_update(state, update, stage)
    return {name: summarize(values) for name, values in samples.items()}


def measure_llm(reasoner: Reasoner | None) -> dict:
    if reasoner is None:
        return {"status": "not measured: no API key configured"}
    recorder_time = []
    for _ in range(LLM_REPEATS):
        recorder = TraceRecorder("optimization")
        recorder.log("recommendation", LLM_SAMPLE_FACTS)
        recorder_time.append(timed(lambda: recorder.reason(reasoner))[0])
    return {"model": getattr(reasoner, "model", "unknown"), "one_explanation_call": summarize(recorder_time)}


def measure_fetch() -> dict:
    client = SystemTrustOpenMeteoClient()
    request = current_hour_request(DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG)
    try:
        return {"provider": "open-meteo", "one_request": repeat(lambda: client.fetch_weather(request), FETCH_REPEATS)}
    except ToolError as exc:
        return {"status": f"not measured: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-llm", action="store_true", help="skip the LLM call timing")
    parser.add_argument("--no-network", action="store_true", help="skip the live weather fetch timing")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    source = default_dataset_source()
    hour = pick_hour(hourly_weather(load_dataset_split(source).test), None)
    weather = {**hour, "panel_angle_deg": CURRENT_ANGLE_DEG}
    metadata = build_metadata(source, interval_start=weather["timestamp"], control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)

    LOGGER.info("Training both models on %s (slow)...", source.path.name)
    tools, training = train_models(source, metadata)
    LOGGER.info("Timing predictions, agent stages and whole decisions...")
    reasoner = None if arguments.no_llm else load_reasoner()
    report = {
        "measured_at": utc_now_iso(),
        "note": "Wall-clock timings of this prototype on one machine, CPU only. Not a performance guarantee.",
        "machine": {"system": platform.system(), "machine": platform.machine(), "processor": platform.processor(), "logical_cpus": os.cpu_count(), "python": platform.python_version()},
        "dataset": {"name": source.path.name, "hour": weather["timestamp"], "current_angle_deg": CURRENT_ANGLE_DEG},
        "one_off_setup": training,
        "prediction_for_all_candidate_angles": measure_predictions(tools, weather, metadata),
        "agent_stages_without_llm": measure_stages(source, tools, weather, metadata),
        "whole_decision_without_llm": repeat(
            lambda: recommend_for_recorded_hour(source, weather, tools, DEFAULT_CONFIG, control_target_id=CONTROL_TARGET_ID, run_id="benchmark"), DECISION_REPEATS,
        ),
        "llm": measure_llm(reasoner),
        "live_weather_fetch": {"status": "not measured: --no-network"} if arguments.no_network else measure_fetch(),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    LOGGER.info("%s", json.dumps({key: report[key] for key in ("one_off_setup", "whole_decision_without_llm", "llm")}, indent=2))
    LOGGER.info("Wrote %s", arguments.output)


if __name__ == "__main__":
    main()
