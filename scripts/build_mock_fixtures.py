"""Reproduce contract fixtures only. No training, API, or agent execution.

All energy, weather, logs, history, and model outputs are synthetic examples.
Metrics are calculated from synthetic fixture vectors, not measured results.
"""

import csv
import json
import math
from pathlib import Path
from typing import get_type_hints

from src.common.config import (
    DEFAULT_CONFIG, PANELS_PER_ROW, PREDICTION_HORIZON_MINUTES,
    SCHEMA_VERSION, TOTAL_PANELS, ZONE_ROW_COUNTS,
)
from src.common.schema import (
    CurrentWeather, MODEL_NAMES, WEATHER_COLUMNS, validate_agent_state, validate_frontend_data,
    validate_model_output, validate_weather_row,
)


ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "data" / "mock"


def build() -> None:
    """Replace only the four documented, reproducible MOCK fixtures."""
    MOCK.mkdir(parents=True, exist_ok=True)
    timestamp = "2026-06-21T19:00:00Z"
    metadata = {
        "schema_version": SCHEMA_VERSION, "dataset_kind": "MOCK",
        "label_source": "mock", "energy_scope": "row",
        "prediction_horizon_minutes": PREDICTION_HORIZON_MINUTES, "interval_start": timestamp,
        "control_target_id": "row-001", "config_id": DEFAULT_CONFIG.config_id,
        "assumptions": [
            "MOCK DEVELOPMENT DATA: hand-authored weather and energy values; not measurements or physics output.",
            "kWh is for one 20-panel row over the hour starting at interval_start.",
            "PROTOTYPE SIMULATION ASSUMPTIONS: movement and safety coefficients are not hardware-calibrated.",
            "Metrics are calculated from synthetic vectors, not trained-model evaluation.",
            "Four whole-row zones contain 260/240/260/240 panels.",
        ],
    }
    # Hourly examples; values match WEATHER_COLUMNS exactly.
    raw_rows = [
        ["2026-06-21T14:00:00Z", 13, 35, 0, 10, 16, 250, 420, 115, 19, 77, 35, 1.7],
        ["2026-06-21T15:00:00Z", 15, 30, 0, 11, 18, 420, 530, 132, 29, 89, 35, 2.8],
        ["2026-06-21T16:00:00Z", 17, 25, 0, 12, 19, 580, 620, 155, 38, 102, 35, 4.1],
        ["2026-06-21T17:00:00Z", 19, 20, 0, 13, 21, 710, 695, 178, 47, 118, 35, 5.0],
        ["2026-06-21T18:00:00Z", 21, 18, 0, 14, 22, 805, 735, 180, 55, 140, 35, 5.6],
        [timestamp, 22, 15, 0, 14, 24, 850, 750, 201, 60, 168, 35, 5.8],
    ]
    weather_rows = [dict(zip(WEATHER_COLUMNS, row)) for row in raw_rows]
    for row in weather_rows:
        validate_weather_row(row)
    with (MOCK / "sample_weather.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WEATHER_COLUMNS)
        writer.writeheader()
        writer.writerows(weather_rows)

    fixture = {
        "actual_kwh": [2.0, 3.0, 4.0, 5.0],
        "linear_regression": [2.4, 2.6, 4.3, 4.5],
        "random_forest": [2.2, 2.8, 4.1, 4.8],
        "boosting": [2.1, 2.9, 4.05, 4.9],
        "lstm": [2.3, 2.7, 4.2, 4.7],
    }
    actual = fixture["actual_kwh"]
    mean = sum(actual) / len(actual)
    total = sum((a - mean) ** 2 for a in actual)
    comparison = []
    for model in MODEL_NAMES:
        residuals = [p - a for p, a in zip(fixture[model], actual)]
        squared = sum(e * e for e in residuals)
        comparison.append({
            "model": model, "implementation": "xgboost" if model == "boosting" else model,
            "status": "MOCK", "mae": sum(abs(e) for e in residuals) / len(actual),
            "rmse": math.sqrt(squared / len(actual)), "r2": 1 - squared / total,
        })
    # Explicit fixture choice, not a trained-model selection implementation.
    selected = next(e for e in comparison if e["model"] == "boosting")
    predictions = [
        {"angle_deg": angle, "predicted_kwh": energy}
        for angle, energy in zip(DEFAULT_CONFIG.candidate_angles_deg, (5.65, 5.8, 5.99, 6.09, 6.10, 6.105, 6.11))
    ]
    modeling = {"selected_model": selected["model"], "mae": selected["mae"], "rmse": selected["rmse"], "r2": selected["r2"], "model_comparison": comparison, "candidate_predictions": predictions}
    model_output = {"timestamp": timestamp, "metadata": metadata, "modeling": modeling, "evaluation_fixture": fixture}

    current_angle, proposed_angle = 35.0, 45.0
    by_angle = {p["angle_deg"]: p["predicted_kwh"] for p in predictions}
    baseline, predicted = by_angle[current_angle], by_angle[proposed_angle]
    movement = abs(proposed_angle - current_angle) * (DEFAULT_CONFIG.motor_kwh_per_degree + DEFAULT_CONFIG.wear_kwh_equivalent_per_degree)
    gain = predicted - baseline
    optimization = {
        "current_angle_deg": current_angle, "recommended_angle_deg": proposed_angle,
        "baseline_kwh": baseline, "predicted_kwh": predicted,
        "energy_gain_kwh": gain, "movement_cost_kwh_equivalent": movement,
        "net_benefit_kwh_equivalent": gain - movement,
    }
    safety = {
        "passed": True,
        "checks": [{"name": name, "passed": True, "severity": severity, "reason": "MOCK illustrative check; controller not executed."}
                   for name, severity in (("wind_safety", "SEVERE"), ("angle_limits", "SEVERE"), ("data_freshness", "BLOCK_ROTATE"), ("panel_status", "BLOCK_ROTATE"), ("model_confidence", "BLOCK_ROTATE"))],
        "reason": "MOCK safety report for frontend development; no hardware authorization.",
    }
    decision = {"action": "ROTATE", "target_angle_deg": proposed_angle, "reason": "MOCK: 45 degrees yields greater net benefit than the raw-energy maximum at 60 degrees."}
    zones, rows = [], []
    number = 1
    for zone_number, row_count in enumerate(ZONE_ROW_COUNTS, start=1):
        zone_id = f"zone-{zone_number:02d}"
        row_ids = []
        for _ in range(row_count):
            row_id = f"row-{number:03d}"
            row_ids.append(row_id)
            stowed = number in (49, 50)
            rows.append({"row_id": row_id, "zone_id": zone_id, "panel_count": PANELS_PER_ROW,
                         "angle_deg": 0.0 if stowed else current_angle,
                         "current_state": "STOWED" if stowed else "READY",
                         "action": "STOW" if stowed else ("ROTATE" if number == 1 else "HOLD")})
            number += 1
        zones.append({"zone_id": zone_id, "row_ids": row_ids, "panel_count": row_count * PANELS_PER_ROW})
    data = {"status": "VALID", "source": "mock_csv", "forecast_age_minutes": 5.0, "used_cache": False, "issues": []}
    logs = [{"timestamp": f"2026-06-21T18:59:{index:02d}Z", "agent": agent, "action": action, "result": result}
            for index, (agent, action, result) in enumerate((
                ("data", "weather_received", "MOCK weather fixture received"),
                ("data", "validation", "MOCK example: required fields present"),
                ("modeling", "comparison", "MOCK metrics derived from synthetic vectors"),
                ("modeling", "selection", "MOCK selected boosting adapter"),
                ("optimization", "candidate_comparison", "MOCK seven candidate predictions"),
                ("optimization", "recommendation", "MOCK 45-degree net benefit recommendation"),
                ("manager", "safety", "MOCK checks passed; no controller executed"),
            ), start=1)]
    frontend = {
        "timestamp": timestamp, "metadata": metadata,
        "current_weather": {key: weather_rows[-1][key] for key in get_type_hints(CurrentWeather)},
        "data_agent": data, "model_comparison": comparison, "selected_model": selected["model"],
        "candidate_predictions": predictions, "optimization": optimization,
        "safety": safety, "decision": decision,
        "farm_status": {"total_panels": TOTAL_PANELS, "zones": zones, "rows": rows},
        "agent_log": logs,
        "history": [
            {"timestamp": "2026-06-21T17:00:00Z", "control_target_id": "row-001", "decision": {"action": "HOLD", "target_angle_deg": 35.0, "reason": "MOCK previous below-threshold result"}, "net_benefit_kwh_equivalent": 0.01},
            {"timestamp": "2026-06-21T18:00:00Z", "control_target_id": "row-049", "decision": {"action": "STOW", "target_angle_deg": 0.0, "reason": "MOCK previous safety override"}, "net_benefit_kwh_equivalent": 0.0},
        ],
        "errors": [],
    }
    features = {key: val for key, val in weather_rows[-1].items() if key != "actual_kwh"}
    state = {
        "run_id": "mock-run-001", "timestamp": timestamp, "metadata": metadata, "stage": "COMPLETE",
        "weather": features, "data": data, "modeling": modeling, "optimization": optimization,
        "safety": safety, "decision": decision, "agent_log": logs,
        "tool_calls": [{"timestamp": timestamp, "agent": "data", "tool": "validate_weather", "status": "OK", "detail": "MOCK trace entry; tool not executed"}],
        "errors": [],
    }
    for name, payload, validator in (
        ("sample_model_output.json", model_output, validate_model_output),
        ("sample_full_frontend_data.json", frontend, validate_frontend_data),
        ("agent_state.json", state, validate_agent_state),
    ):
        validator(payload)
        (MOCK / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
