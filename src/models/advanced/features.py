"""Owner: Duy. Feature layout shared by the advanced models.

Models see only FEATURE_COLUMNS (weather, sun position, panel angle). The
label `actual_kwh` is never part of an inference vector.
"""

from typing import Sequence

import numpy as np

from src.common.schema import FEATURE_COLUMNS, WeatherFeatures, WeatherRow
from src.common.tool_contracts import ToolError


PANEL_ANGLE_COLUMN = "panel_angle_deg"
LABEL_COLUMN = "actual_kwh"


def feature_matrix(rows: Sequence[WeatherFeatures]) -> np.ndarray:
    """One row per sample, columns in FEATURE_COLUMNS order."""
    try:
        matrix = np.array([[row[name] for name in FEATURE_COLUMNS] for row in rows], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolError(f"Weather features are missing or non-numeric: {exc!r}") from exc
    if not np.isfinite(matrix).all():
        raise ToolError("Weather features must be finite")
    return matrix.reshape(len(rows), len(FEATURE_COLUMNS))


def label_vector(rows: Sequence[WeatherRow]) -> np.ndarray:
    return np.array([row[LABEL_COLUMN] for row in rows], dtype=np.float64)


def at_candidate_angles(weather: WeatherFeatures, candidate_angles_deg: Sequence[float]) -> list[WeatherFeatures]:
    """Copies of the weather with each candidate angle substituted for the current one."""
    return [{**weather, PANEL_ANGLE_COLUMN: angle} for angle in candidate_angles_deg]
