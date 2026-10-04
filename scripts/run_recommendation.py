"""Owner: Duy. One full agent run for one recorded hour, written as a validated FrontendData JSON file.

Data -> Modeling -> Optimization -> Manager / Safety, on the default dataset
(Luan's pipeline data; real archived forecast weather with physics-simulated
energy labels). The Data Agent and the farm snapshot are labeled stand-ins; see
`src/service/recommendation_service.py`. Every figure is computed by the tools.

When ANTHROPIC_API_KEY is set (environment or .env) each deciding agent also
asks an LLM to word an explanation of its tool results; `--no-llm` turns that off.

Run from the repository root:  python -m scripts.run_recommendation
"""

import argparse
import logging
from pathlib import Path
from typing import Sequence

from src.agents.reasoning import load_reasoner
from src.agents.trace import utc_now_iso
from src.common.config import DEFAULT_CONFIG
from src.common.schema import WeatherFeatures
from src.models.advanced import lstm
from src.models.data_loader import ROOT, default_dataset_source, hourly_weather, load_dataset_split
from src.models.evaluation import ModelCandidate
from src.service.recommendation_service import build_metadata, build_modeling_tools, recommend_for_recorded_hour, save_recommendation


LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "latest_recommendation.json"
CONTROL_TARGET_ID = "row-001"
DEFAULT_ANGLE_DEG = 35.0


def pick_hour(hours: Sequence[WeatherFeatures], timestamp: str | None) -> WeatherFeatures:
    """The requested test-window hour, or by default the sunniest hour whose gust reading is not below its wind reading."""
    if timestamp is not None:
        match = next((hour for hour in hours if hour["timestamp"] == timestamp), None)
        if match is None:
            raise SystemExit(f"No test-window hour with timestamp {timestamp}")
        return match
    # The dashboard's own validation rejects a gust below the wind speed, so the default avoids such hours.
    consistent = [hour for hour in hours if hour["wind_gust_kmh"] >= hour["wind_speed_kmh"]]
    if not consistent:
        raise SystemExit("No test-window hour has a gust reading at or above its wind reading")
    return max(consistent, key=lambda hour: hour["ghi_wm2"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timestamp", help="hour to run, exactly as written in the dataset; default is the sunniest test-window hour")
    parser.add_argument("--angle", type=float, default=DEFAULT_ANGLE_DEG, help="current angle of the controlled row in degrees")
    parser.add_argument("--skip-lstm", action="store_true", help="do not train the LSTM (much faster); it is reported UNAVAILABLE")
    parser.add_argument("--no-llm", action="store_true", help="templated explanations only, no LLM calls")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    source = default_dataset_source()
    hour = pick_hour(hourly_weather(load_dataset_split(source).test), arguments.timestamp)
    weather = {**hour, "panel_angle_deg": arguments.angle}
    LOGGER.info("Dataset %s (%s, labels %s); hour %s; current angle %g deg", source.path.name, source.dataset_kind, source.label_source, weather["timestamp"], arguments.angle)

    skipped = [ModelCandidate(lstm.MODEL_NAME, lstm.IMPLEMENTATION, unavailable_reason="skipped for this run (--skip-lstm)")] if arguments.skip_lstm else []
    metadata = build_metadata(source, interval_start=weather["timestamp"], control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)
    LOGGER.info("Training and scoring models (this is the slow part)...")
    modeling_tools = build_modeling_tools(source, metadata=metadata, extra_candidates=skipped)

    reasoner = None if arguments.no_llm else load_reasoner()
    LOGGER.info("LLM explanations: %s", "off" if reasoner is None else f"on ({reasoner.model})")
    payload = recommend_for_recorded_hour(
        source, weather, modeling_tools, DEFAULT_CONFIG,
        control_target_id=CONTROL_TARGET_ID, run_id=f"run-{utc_now_iso()}", reasoner=reasoner,
    )
    path = save_recommendation(payload, arguments.output)

    decision, optimization = payload["decision"], payload["optimization"]
    LOGGER.info("Selected model: %s", payload["selected_model"])
    LOGGER.info("Decision: %s at %g deg; %s", decision["action"], decision["target_angle_deg"], decision["reason"])
    if optimization is not None:
        LOGGER.info("Net benefit: %+.4f kWh-eq", optimization["net_benefit_kwh_equivalent"])
    for entry in payload["agent_log"]:
        if entry["action"].startswith("llm_reasoning"):
            LOGGER.info("[%s] %s: %s", entry["agent"], entry["action"], entry["result"])
    for error in payload["errors"]:
        LOGGER.info("Recorded error [%s] %s: %s", error["agent"], error["code"], error["message"])
    LOGGER.info("Wrote %s", path)


if __name__ == "__main__":
    main()
