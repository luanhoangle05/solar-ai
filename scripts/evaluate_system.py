"""Owner: Duy. Train, compare models and replay the decision pipeline on the test window.

Writes a JSON report of computed results, labeled from the dataset it ran on.
By default it uses Luan's pipeline dataset (real archived forecast weather with
physics-simulated energy labels); `--example` runs the synthetic example dataset.
Neither is measured production, so the report is not evidence of real-world savings.

Run from the repository root:  python -m scripts.evaluate_system
"""

import argparse
import dataclasses
import json
import logging
from pathlib import Path
from typing import Callable, Sequence

from scripts.generate_example_data import DEFAULT_EXAMPLE_CONFIG, expected_row_kwh
from src.common.config import DEFAULT_CONFIG
from src.common.schema import Metadata, ModelMetrics, WeatherFeatures, WeatherRow
from src.common.tool_contracts import ToolError
from src.models.data_loader import (
    EXAMPLE_DATASET_PATH, EXAMPLE_DATASET_SOURCE, ROOT, DatasetSource, default_dataset_source, hourly_weather, load_dataset_split,
)
from src.models.evaluation import (
    EvaluatedModelingTools, build_model_metrics, evaluate_decision_quality, evaluate_predictor, selection_reason,
)
from src.service.recommendation_service import build_metadata, build_modeling_tools, replay_test_window


LOGGER = logging.getLogger(__name__)
EXAMPLE_OUTPUT = EXAMPLE_DATASET_PATH.parent / "system_evaluation.json"
PIPELINE_OUTPUT = ROOT / "data" / "evaluation" / "system_evaluation.json"
CONTROL_TARGET_ID = "row-001"
INITIAL_ANGLE_DEG = 35.0
EXAMPLE_FORMULA_SOURCE = "example-data formula, noise-free (data/example/README.md)"
DATASET_LABEL_SOURCE = "dataset energy labels for the same hour and angle"
DECISION_QUALITY_NOTE = (
    "Each model's best candidate angle is compared with the true best angle according to the stated energy source, "
    "on test-window hours where the true energy depends on the angle. Regret is true kWh lost per hour."
)
REPLAY_NOTES = [
    "A 'model-predicted' replay grades the selected model's choices with that model's own predictions, so its gain is optimistic.",
    "The baseline row never stows; hours stowed for safety lower optimized energy by design.",
    "Each hour is decided on its own one-hour horizon; a move is not credited for energy gained in later hours.",
    "error_hours above zero means some decisions were fallbacks after a failed stage.",
]

EnergyOracle = Callable[[WeatherFeatures, float], float]


def build_report(source: DatasetSource) -> dict:
    split = load_dataset_split(source)
    metadata = build_metadata(source, interval_start=split.test[0]["timestamp"], control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)
    tools = build_modeling_tools(source, metadata=metadata)
    validation = tools.evaluate_models()
    selected = tools.select_best_model(validation)
    oracle, oracle_source = _true_energy_oracle(source, split.test)
    replays, skipped = [], []
    if oracle is not None:
        # A replay scored against known energy leads the report; the self-graded one follows.
        try:
            replays.append(_replay(source, tools, energy_at=oracle, energy_source=oracle_source))
        except ToolError as exc:
            skipped.append(f"Replay against {oracle_source} skipped: {exc}")
    replays.append(_replay(source, tools))
    return {
        "metadata": metadata,
        "windows": {name: _describe_window(rows) for name, rows in (("train", split.train), ("validation", split.validation), ("test", split.test))},
        "validation_metrics": validation,
        "unavailable_reasons": tools.unavailable_reasons(),
        "selected_model": selected,
        "selection_reason": selection_reason(validation, selected),
        "test_metrics": _test_metrics(tools, validation, split.test, metadata),
        "decision_quality_source": oracle_source,
        "decision_quality": None if oracle is None else _decision_quality(tools, validation, split.test, oracle, metadata),
        "decision_quality_note": None if oracle is None else DECISION_QUALITY_NOTE,
        "replay_baseline": f"row fixed at {INITIAL_ANGLE_DEG:g} deg for every test hour",
        "replay_notes": [*REPLAY_NOTES, *skipped],
        "system_evaluation": [dataclasses.asdict(replay) for replay in replays],
    }


def _replay(source: DatasetSource, tools: EvaluatedModelingTools, **energy):
    return replay_test_window(source, tools, DEFAULT_CONFIG, initial_angle_deg=INITIAL_ANGLE_DEG, control_target_id=CONTROL_TARGET_ID, **energy)


def _describe_window(rows: Sequence[WeatherRow]) -> dict:
    return {"rows": len(rows), "hours": len(hourly_weather(rows)), "first": rows[0]["timestamp"], "last": rows[-1]["timestamp"]}


def _true_energy_oracle(source: DatasetSource, test_rows: Sequence[WeatherRow]) -> tuple[EnergyOracle | None, str | None]:
    """A known energy for any candidate angle, if the dataset offers one; otherwise (None, None)."""
    if source.path.resolve() == EXAMPLE_DATASET_PATH.resolve():
        return _example_formula_kwh, EXAMPLE_FORMULA_SOURCE
    labels = {(row["timestamp"], row["panel_angle_deg"]): row["actual_kwh"] for row in test_rows}
    candidates = {float(angle) for angle in DEFAULT_CONFIG.candidate_angles_deg}
    covered = all((row["timestamp"], angle) in labels for row in test_rows for angle in candidates)
    if not covered:
        return None, None

    def labeled_kwh(weather: WeatherFeatures, angle_deg: float) -> float:
        try:
            return labels[(weather["timestamp"], float(angle_deg))]
        except KeyError:
            raise ToolError(f"The dataset has no energy label for {weather['timestamp']} at {angle_deg:g} deg") from None

    return labeled_kwh, f"{DATASET_LABEL_SOURCE} ({source.label_source})"


def _example_formula_kwh(weather: WeatherFeatures, angle_deg: float) -> float:
    return expected_row_kwh({**weather, "panel_angle_deg": angle_deg}, DEFAULT_EXAMPLE_CONFIG)


def _decision_quality(tools: EvaluatedModelingTools, validation: list[ModelMetrics], test_rows: Sequence[WeatherRow], oracle: EnergyOracle, metadata: Metadata) -> dict:
    """Per available model: how well it ranks the configured candidate angles on each test hour."""
    hours = hourly_weather(test_rows)
    return {
        entry["model"]: dataclasses.asdict(evaluate_decision_quality(
            tools.get_predictor(entry["model"]), hours, oracle, DEFAULT_CONFIG.candidate_angles_deg, metadata=metadata,
        ))
        for entry in validation if entry["status"] != "UNAVAILABLE"
    }


def _test_metrics(tools: EvaluatedModelingTools, validation: list[ModelMetrics], test_rows: Sequence[WeatherRow], metadata: Metadata) -> list[ModelMetrics]:
    """Held-out test metrics for every model that was available on validation; same rows for all."""
    scored = []
    for entry in validation:
        if entry["status"] == "UNAVAILABLE":
            scored.append(entry)
            continue
        metrics = evaluate_predictor(tools.get_predictor(entry["model"]), test_rows, metadata=metadata)
        scored.append(build_model_metrics(entry["model"], entry["implementation"], metrics, dataset_kind=metadata["dataset_kind"]))
    return scored


def _log_summary(report: dict) -> None:
    for name, window in report["windows"].items():
        LOGGER.info("[%s] %d rows over %d hours, %s to %s", name, window["rows"], window["hours"], window["first"], window["last"])
    for name in ("validation_metrics", "test_metrics"):
        for entry in report[name]:
            if entry["status"] != "UNAVAILABLE":
                LOGGER.info("[%s] %s: RMSE %.4f, MAE %.4f, R2 %.4f", name, entry["model"], entry["rmse"], entry["mae"], entry["r2"])
    LOGGER.info("%s", report["selection_reason"])
    for replay in report["system_evaluation"]:
        LOGGER.info(
            "[%s] %d h: baseline %.2f kWh, optimized %.2f kWh, gain %+.2f, movement cost %.3f, net %+.2f kWh-eq; "
            "ROTATE %d / HOLD %d / STOW %d; moves avoided %d; severe events %d; unsafe rotations %d; error hours %d",
            replay["energy_source"], replay["hours"], replay["baseline_kwh"], replay["optimized_kwh"], replay["energy_gain_kwh"],
            replay["movement_cost_kwh_equivalent"], replay["net_benefit_kwh_equivalent"], replay["rotate_count"], replay["hold_count"],
            replay["stow_count"], replay["unnecessary_moves_avoided"], replay["severe_safety_events"], replay["unsafe_rotations"], replay["error_hours"],
        )
    for model, quality in (report["decision_quality"] or {}).items():
        LOGGER.info(
            "[decision quality] %s: best angle matched in %.1f%% of %d h; regret mean %.4f / max %.3f / total %.2f kWh; curve error %.4f kWh",
            model, 100 * quality["best_angle_match_rate"], quality["hours"], quality["mean_regret_kwh"], quality["max_regret_kwh"],
            quality["total_regret_kwh"], quality["mean_curve_error_kwh"],
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--example", action="store_true", help="run on the synthetic example dataset instead of the pipeline dataset")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        source = EXAMPLE_DATASET_SOURCE if args.example else default_dataset_source()
        report = build_report(source)
    except (ToolError, ValueError) as exc:
        raise SystemExit(f"System evaluation failed: {exc}") from exc
    output = args.output or (EXAMPLE_OUTPUT if source == EXAMPLE_DATASET_SOURCE else PIPELINE_OUTPUT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _log_summary(report)
    LOGGER.info("Wrote %s", output)


if __name__ == "__main__":
    main()
