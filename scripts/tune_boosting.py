"""Owner: Duy. Grid search over the boosting model's hyperparameters.

Each candidate is fitted on the train window (with early stopping on its own
tail) and compared on validation RMSE, the same rule as model selection. The
test window is never read here. Decision quality on the validation window is
recorded for information only; it does not pick the winner.

Run from the repo root: `python -m scripts.tune_boosting`. The winning values
are then copied by hand into `BoostingConfig`, so training stays deterministic.
"""

import argparse
import dataclasses
import itertools
import json
import logging
from pathlib import Path

from src.common.config import DEFAULT_CONFIG
from src.common.tool_contracts import ToolError
from src.models.advanced.boosting import DEFAULT_BOOSTING_CONFIG, BoostingConfig, train_boosting
from src.models.advanced.features import split_for_early_stopping
from src.models.data_loader import ROOT, DatasetSource, default_dataset_source, hourly_weather, load_dataset_split
from src.models.evaluation import evaluate_decision_quality, evaluate_predictor
from src.service.recommendation_service import build_metadata


LOGGER = logging.getLogger(__name__)
OUTPUT = ROOT / "data" / "evaluation" / "boosting_tuning.json"
CONTROL_TARGET_ID = "row-001"
MAX_ROUNDS = 3000
GRID = {"max_depth": (6, 8, 10), "learning_rate": (0.05, 0.1)}
SELECTION_RULE = "lowest validation RMSE; ties keep the earlier candidate, and the current default is listed first"


def candidate_configs() -> list[BoostingConfig]:
    """The current default first, then every grid combination with a higher round limit."""
    names = tuple(GRID)
    grid = [
        dataclasses.replace(DEFAULT_BOOSTING_CONFIG, num_boost_round=MAX_ROUNDS, **dict(zip(names, values)))
        for values in itertools.product(*GRID.values())
    ]
    return [DEFAULT_BOOSTING_CONFIG, *grid]


def tune(source: DatasetSource) -> dict:
    split = load_dataset_split(source)
    metadata = build_metadata(source, interval_start=split.validation[0]["timestamp"], control_target_id=CONTROL_TARGET_ID, config=DEFAULT_CONFIG)
    fit_rows, stop_rows = split_for_early_stopping(split.train)
    labels = {(row["timestamp"], row["panel_angle_deg"]): row["actual_kwh"] for row in split.validation}
    validation_hours = hourly_weather(split.validation)
    results = []
    for config in candidate_configs():
        predictor = train_boosting(fit_rows, stop_rows, config)
        metrics = evaluate_predictor(predictor, split.validation, metadata=metadata)
        quality = evaluate_decision_quality(
            predictor, validation_hours, lambda weather, angle: labels[(weather["timestamp"], float(angle))],
            DEFAULT_CONFIG.candidate_angles_deg, metadata=metadata,
        )
        results.append({
            "config": dataclasses.asdict(config),
            "validation": dataclasses.asdict(metrics),
            "validation_decision_quality": dataclasses.asdict(quality),
        })
        LOGGER.info(
            "depth %d, learning rate %.2f, max rounds %d: validation RMSE %.5f, MAE %.5f, best angle matched %.1f%%, regret %.2f kWh",
            config.max_depth, config.learning_rate, config.num_boost_round, metrics.rmse, metrics.mae,
            100 * quality.best_angle_match_rate, quality.total_regret_kwh,
        )
    best = min(results, key=lambda result: result["validation"]["rmse"])
    return {
        "dataset": {"dataset_kind": source.dataset_kind, "label_source": source.label_source},
        "windows": {"fit_rows": len(fit_rows), "early_stopping_rows": len(stop_rows), "validation_rows": len(split.validation)},
        "selection_rule": SELECTION_RULE,
        "note": "The test window is not read during tuning. Decision quality is informational and does not pick the winner.",
        "selected": best["config"],
        "candidates": results,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        report = tune(default_dataset_source())
    except (ToolError, ValueError) as exc:
        raise SystemExit(f"Boosting tuning failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    LOGGER.info("Selected %s", report["selected"])
    LOGGER.info("Wrote %s", args.output)


if __name__ == "__main__":
    main()
