"""Owner: Duy. Train, compare models and replay the decision pipeline on the test window.

Writes a JSON report of computed results. On the synthetic example dataset the
report is labeled MOCK: it shows how the system behaves on simulated data and is
not evidence of real-world accuracy or savings.

Run from the repository root:  python -m scripts.evaluate_system
"""

import argparse
import dataclasses
import json
import logging
from pathlib import Path

from scripts.generate_example_data import DEFAULT_EXAMPLE_CONFIG, expected_row_kwh
from src.common.config import DEFAULT_CONFIG
from src.common.schema import Metadata, ModelMetrics
from src.common.tool_contracts import ToolError
from src.models.data_loader import EXAMPLE_DATASET_PATH, DatasetSource, default_dataset_source, load_weather_rows
from src.models.evaluation import (
    EvaluatedModelingTools, build_model_metrics, chronological_split, evaluate_predictor, selection_reason,
)
from src.service.recommendation_service import build_metadata, build_modeling_tools, replay_test_window


LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT = EXAMPLE_DATASET_PATH.parent / "system_evaluation.json"
CONTROL_TARGET_ID = "row-001"
INITIAL_ANGLE_DEG = 35.0
EXAMPLE_FORMULA_SOURCE = "example-data formula, noise-free (data/example/README.md)"
REPLAY_NOTES = [
    "A 'model-predicted' replay grades the selected model's choices with that model's own predictions, so its gain is optimistic.",
    "The baseline row never stows; hours stowed for safety lower optimized energy by design.",
    "Each hour is decided on its own one-hour horizon; a move is not credited for energy gained in later hours.",
    "error_hours above zero means some decisions were fallbacks after a failed stage.",
]


def build_report(source: DatasetSource) -> dict:
    split = chronological_split(load_weather_rows(source.path))
    metadata = build_metadata(source, interval_start=split.test[0]["timestamp"], control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)
    tools = build_modeling_tools(source, metadata=metadata)
    validation = tools.evaluate_models()
    selected = tools.select_best_model(validation)
    replays = []
    if source.path.resolve() == EXAMPLE_DATASET_PATH.resolve():
        # Only the synthetic dataset has a known generating formula to score decisions against; it leads the report.
        replays.append(replay_test_window(
            source, tools, DEFAULT_CONFIG, initial_angle_deg=INITIAL_ANGLE_DEG, control_target_id=CONTROL_TARGET_ID,
            energy_at=lambda weather, angle: expected_row_kwh({**weather, "panel_angle_deg": angle}, DEFAULT_EXAMPLE_CONFIG),
            energy_source=EXAMPLE_FORMULA_SOURCE,
        ))
    replays.append(replay_test_window(source, tools, DEFAULT_CONFIG, initial_angle_deg=INITIAL_ANGLE_DEG, control_target_id=CONTROL_TARGET_ID))
    return {
        "metadata": metadata,
        "windows": {name: {"rows": len(rows), "first": rows[0]["timestamp"], "last": rows[-1]["timestamp"]} for name, rows in dataclasses.asdict(split).items()},
        "validation_metrics": validation,
        "unavailable_reasons": tools.unavailable_reasons(),
        "selected_model": selected,
        "selection_reason": selection_reason(validation, selected),
        "test_metrics": _test_metrics(tools, validation, split.test, metadata),
        "replay_baseline": f"row fixed at {INITIAL_ANGLE_DEG:g} deg for every test hour",
        "replay_notes": REPLAY_NOTES,
        "system_evaluation": [dataclasses.asdict(replay) for replay in replays],
    }


def _test_metrics(tools: EvaluatedModelingTools, validation: list[ModelMetrics], test_rows: tuple, metadata: Metadata) -> list[ModelMetrics]:
    """Held-out test metrics for every model that was available on validation; same rows for all."""
    scored = []
    for entry in validation:
        if entry["status"] == "UNAVAILABLE":
            scored.append(entry)
            continue
        metrics = evaluate_predictor(tools.get_predictor(entry["model"]), test_rows, metadata=metadata)
        scored.append(build_model_metrics(entry["model"], entry["implementation"], metrics, dataset_kind=metadata["dataset_kind"]))
    return scored


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = build_report(default_dataset_source())
    except (ToolError, ValueError) as exc:
        raise SystemExit(f"System evaluation failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    LOGGER.info("%s", report["selection_reason"])
    for replay in report["system_evaluation"]:
        LOGGER.info(
            "[%s] %d h: baseline %.1f kWh, optimized %.1f kWh, gain %+.1f, movement cost %.2f, net %+.1f kWh-eq; "
            "ROTATE %d / HOLD %d / STOW %d; moves avoided %d; severe events %d; unsafe rotations %d; error hours %d",
            replay["energy_source"], replay["hours"], replay["baseline_kwh"], replay["optimized_kwh"], replay["energy_gain_kwh"],
            replay["movement_cost_kwh_equivalent"], replay["net_benefit_kwh_equivalent"], replay["rotate_count"], replay["hold_count"],
            replay["stow_count"], replay["unnecessary_moves_avoided"], replay["severe_safety_events"], replay["unsafe_rotations"], replay["error_hours"],
        )
    LOGGER.info("Wrote %s", args.output)


if __name__ == "__main__":
    main()
