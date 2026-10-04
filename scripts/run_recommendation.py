"""Owner: Duy. One full agent run for one recorded hour, written as a validated FrontendData JSON file.

Data -> Modeling -> Optimization -> Manager / Safety, on the default dataset
(Luan's pipeline data; real archived forecast weather with physics-simulated
energy labels). The Data Agent and the farm snapshot are labeled stand-ins; see
`src/service/recommendation_service.py`. Every figure is computed by the tools.

When ANTHROPIC_API_KEY is set (environment or .env) each deciding agent also
asks an LLM to word an explanation of its tool results; `--no-llm` turns that off.

`--live` fetches the current hour's forecast for the demo site with the live Data
Agent instead of replaying a dataset hour. The provider gives no forecast issue
time, so the validation tool reports the data INVALID and the Manager holds:
that is the system's real answer today, not an error. The LSTM is not used in a
live run because it needs look-back weather history that a single fetch does not give.

Run from the repository root:  python -m scripts.run_recommendation
"""

import argparse
import logging
from pathlib import Path
from typing import Sequence

from src.agents.reasoning import load_reasoner
from src.agents.trace import utc_now_iso
from src.common.config import DEFAULT_CONFIG, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG
from src.common.schema import WeatherFeatures
from src.models.advanced import lstm
from src.models.data_loader import ROOT, default_dataset_source, hourly_weather, load_dataset_split
from src.models.evaluation import ModelCandidate
from src.service.live_data_agent import current_hour_request, recommend_live
from src.service.recommendation_service import build_metadata, build_modeling_tools, recommend_for_recorded_hour, recommend_for_zones, save_recommendation


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
    parser.add_argument("--live", action="store_true", help="fetch the current hour's forecast for the demo site instead of replaying a dataset hour")
    parser.add_argument("--timestamp", help="hour to run, exactly as written in the dataset; default is the sunniest test-window hour")
    parser.add_argument("--zone-angles", help="comma-separated starting angle for each of the four zones, for example 60,45,35,30; runs the agents once per zone")
    parser.add_argument("--angle", type=float, default=DEFAULT_ANGLE_DEG, help="current angle of the controlled row in degrees")
    parser.add_argument("--skip-lstm", action="store_true", help="do not train the LSTM (much faster); it is reported UNAVAILABLE")
    parser.add_argument("--no-llm", action="store_true", help="templated explanations only, no LLM calls")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if arguments.zone_angles and arguments.live:
        raise SystemExit("--zone-angles works with a recorded hour, not with --live")

    source = default_dataset_source()
    if arguments.live:
        request = current_hour_request(DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG)
        interval_start = request.interval_start
        LOGGER.info("Live weather for %s at %.4f, %.4f; models trained on %s; current angle %g deg", interval_start, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG, source.path.name, arguments.angle)
    else:
        hour = pick_hour(hourly_weather(load_dataset_split(source).test), arguments.timestamp)
        weather = {**hour, "panel_angle_deg": arguments.angle}
        interval_start = weather["timestamp"]
        LOGGER.info("Dataset %s (%s, labels %s); hour %s; current angle %g deg", source.path.name, source.dataset_kind, source.label_source, interval_start, arguments.angle)

    skip_reason = "not used in a live run: no look-back weather history" if arguments.live else "skipped for this run (--skip-lstm)" if arguments.skip_lstm else None
    skipped = [ModelCandidate(lstm.MODEL_NAME, lstm.IMPLEMENTATION, unavailable_reason=skip_reason)] if skip_reason else []
    metadata = build_metadata(source, interval_start=interval_start, control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)
    LOGGER.info("Training and scoring models (this is the slow part)...")
    modeling_tools = build_modeling_tools(source, metadata=metadata, extra_candidates=skipped)

    reasoner = None if arguments.no_llm else load_reasoner()
    LOGGER.info("LLM explanations: %s", "off" if reasoner is None else f"on ({reasoner.model})")
    run_id = f"run-{utc_now_iso()}"
    if arguments.zone_angles:
        write_zone_runs(arguments, source, hour, modeling_tools, reasoner, run_id)
        return
    if arguments.live:
        payload = recommend_live(source, request, modeling_tools, DEFAULT_CONFIG, current_angle_deg=arguments.angle, control_target_id=CONTROL_TARGET_ID, run_id=run_id, reasoner=reasoner)
    else:
        payload = recommend_for_recorded_hour(source, weather, modeling_tools, DEFAULT_CONFIG, control_target_id=CONTROL_TARGET_ID, run_id=run_id, reasoner=reasoner)
    path = save_recommendation(payload, arguments.output)

    decision, optimization, data = payload["decision"], payload["optimization"], payload["data_agent"]
    LOGGER.info("Data: %s from %s; issues: %s", data["status"], data["source"], "; ".join(data["issues"]) or "none")
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


def write_zone_runs(arguments: argparse.Namespace, source, hour: WeatherFeatures, modeling_tools, reasoner, run_id: str) -> None:
    """One file per zone: the first at --output, the rest beside it with the zone id in the name."""
    angles = [float(value) for value in arguments.zone_angles.split(",")]
    payloads = recommend_for_zones(source, hour, modeling_tools, DEFAULT_CONFIG, zone_angles=angles, run_id=run_id, reasoner=reasoner)
    paths = []
    for index, payload in enumerate(payloads):
        zone_id = payload["farm_status"]["zones"][index]["zone_id"]
        path = arguments.output if index == 0 else arguments.output.with_name(f"{arguments.output.stem}.{zone_id}{arguments.output.suffix}")
        paths.append(save_recommendation(payload, path))
        decision, optimization = payload["decision"], payload["optimization"]
        net = "unavailable" if optimization is None else f"{optimization['net_benefit_kwh_equivalent']:+.4f} kWh-eq"
        LOGGER.info("%s at %g deg (control row %s): %s to %g deg; net benefit %s", zone_id, angles[index], payload["metadata"]["control_target_id"], decision["action"], decision["target_angle_deg"], net)
    LOGGER.info("Wrote %s", ", ".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
