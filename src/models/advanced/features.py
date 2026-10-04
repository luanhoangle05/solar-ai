"""Owner: Duy. Feature layout shared by the advanced models.

Models see FEATURE_COLUMNS (weather, sun position, panel angle) plus geometry
features derived only from those columns. The label `actual_kwh` is never part
of an inference vector.

The geometry features are the standard terms for irradiance on a tilted
surface. With el = sun elevation, az = sun azimuth, t = panel tilt:

    beam on panel = DNI * (sin(el)cos(t) + cos(el)sin(t)cos(az - panel_azimuth))

Expanding cos(az - panel_azimuth) gives three terms that do not depend on which
way the panel faces, so no panel azimuth is assumed here; a model learns the
facing direction as weights on the east-west and north-south terms.

Each model chooses whether to use them; both advanced models do by default.
Measured with the validation RMSE and the decision-quality metric in evaluation.py:
- pipeline dataset (real weather, physics-derived labels): they lower validation
  error and angle-curve error for both the LSTM and boosted trees;
- synthetic example data (noisy labels): they help the LSTM, while for boosted
  trees they lower RMSE but make the predicted angle curve bumpier.
"""

from typing import Sequence

import numpy as np

from src.common.schema import FEATURE_COLUMNS, WeatherFeatures, WeatherRow
from src.common.tool_contracts import ToolError


PANEL_ANGLE_COLUMN = "panel_angle_deg"
LABEL_COLUMN = "actual_kwh"
EARLY_STOPPING_FRACTION = 0.15
GEOMETRY_FEATURES = (
    "beam_horizontal_wm2",    # DNI * sin(el) * cos(t)
    "beam_north_south_wm2",   # DNI * cos(el) * sin(t) * cos(az)
    "beam_east_west_wm2",     # DNI * cos(el) * sin(t) * sin(az)
    "sky_diffuse_tilted_wm2",  # DHI * (1 + cos(t)) / 2
    "ground_view_ghi_wm2",    # GHI * (1 - cos(t)) / 2
)
MODEL_FEATURE_NAMES = (*FEATURE_COLUMNS, *GEOMETRY_FEATURES)


def feature_names(*, geometry: bool) -> tuple[str, ...]:
    return MODEL_FEATURE_NAMES if geometry else FEATURE_COLUMNS


def feature_matrix(rows: Sequence[WeatherFeatures], *, geometry: bool = True) -> np.ndarray:
    """One row per sample, columns in `feature_names(geometry=...)` order."""
    try:
        raw = np.array([[row[name] for name in FEATURE_COLUMNS] for row in rows], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolError(f"Weather features are missing or non-numeric: {exc!r}") from exc
    if not np.isfinite(raw).all():
        raise ToolError("Weather features must be finite")
    raw = raw.reshape(len(rows), len(FEATURE_COLUMNS))
    return np.hstack([raw, _geometry_features(raw)]) if geometry else raw


def _geometry_features(raw: np.ndarray) -> np.ndarray:
    """Tilted-surface irradiance terms, in GEOMETRY_FEATURES order; zero when the sun is down."""
    column = {name: raw[:, index] for index, name in enumerate(FEATURE_COLUMNS)}
    elevation = np.radians(column["sun_elevation_deg"])
    azimuth = np.radians(column["sun_azimuth_deg"])
    tilt = np.radians(column[PANEL_ANGLE_COLUMN])
    # Below the horizon there is no beam; clamping keeps night rows from producing negative "irradiance".
    sun_up = np.clip(np.sin(elevation), 0.0, None)
    beam_slant = np.where(sun_up > 0, column["dni_wm2"] * np.cos(elevation) * np.sin(tilt), 0.0)
    return np.column_stack([
        column["dni_wm2"] * sun_up * np.cos(tilt),
        beam_slant * np.cos(azimuth),
        beam_slant * np.sin(azimuth),
        column["dhi_wm2"] * (1 + np.cos(tilt)) / 2,
        column["ghi_wm2"] * (1 - np.cos(tilt)) / 2,
    ])


def label_vector(rows: Sequence[WeatherRow]) -> np.ndarray:
    return np.array([row[LABEL_COLUMN] for row in rows], dtype=np.float64)


def at_candidate_angles(weather: WeatherFeatures, candidate_angles_deg: Sequence[float]) -> list[WeatherFeatures]:
    """Copies of the weather with each candidate angle substituted for the current one."""
    return [{**weather, PANEL_ANGLE_COLUMN: angle} for angle in candidate_angles_deg]


def split_for_early_stopping(train_rows: Sequence[WeatherRow], fraction: float = EARLY_STOPPING_FRACTION) -> tuple[Sequence[WeatherRow], Sequence[WeatherRow]]:
    """(fit rows, early-stopping rows): the latest `fraction` of the train window is held for stopping.

    Both advanced models stop on this slice, so the validation window stays
    unseen until model selection.
    """
    cut = len(train_rows) - int(len(train_rows) * fraction)
    return train_rows[:cut], train_rows[cut:]
