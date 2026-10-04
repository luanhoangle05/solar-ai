"""Owner: Duy. The single entry point for labeled weather rows.

Every trainer and evaluator reads through this module, so switching datasets is
a path/config change (see the environment variables below), not a code change.

Two layouts are supported:
- a single CSV, split chronologically here (the synthetic example dataset);
- a directory holding `train_sample.csv`, `validation_sample.csv` and
  `test_sample.csv`, used exactly as delivered (Luan's pipeline output).

A dataset may hold several rows per hour, one per panel angle, so timestamps
must not go backwards but may repeat; a repeated (timestamp, angle) pair is an error.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Sequence, get_args, get_type_hints

from src.common.schema import ContractError, Metadata, WEATHER_COLUMNS, WeatherFeatures, WeatherRow, validate_weather_row
from src.models.evaluation import ChronologicalSplit, chronological_split


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DATASET_PATH = ROOT / "data" / "example" / "example_weather.csv"
PIPELINE_DATASET_PATH = ROOT / "data" / "generated" / "gem_seasonal_sample"
SPLIT_FILE_NAMES = {"train": "train_sample.csv", "validation": "validation_sample.csv", "test": "test_sample.csv"}
LABEL_COLUMN = "actual_kwh"
_WEATHER_ONLY_COLUMNS = tuple(name for name in WEATHER_COLUMNS if name not in ("timestamp", "panel_angle_deg", LABEL_COLUMN))

DATASET_PATH_ENV = "SOLAR_DATASET_PATH"
DATASET_KIND_ENV = "SOLAR_DATASET_KIND"
LABEL_SOURCE_ENV = "SOLAR_LABEL_SOURCE"

_METADATA_HINTS = get_type_hints(Metadata)
_DATASET_KINDS = get_args(_METADATA_HINTS["dataset_kind"])
_LABEL_SOURCES = get_args(_METADATA_HINTS["label_source"])


class DatasetError(ValueError):
    """The dataset file is missing, malformed, or breaks the weather contract."""


@dataclass(frozen=True)
class DatasetSource:
    """Where labeled rows come from and how outputs built on them are labeled."""

    path: Path
    dataset_kind: str
    label_source: str


EXAMPLE_DATASET_SOURCE = DatasetSource(path=EXAMPLE_DATASET_PATH, dataset_kind="MOCK", label_source="mock")
# Archived forecast-model weather with pvlib-simulated energy labels: real inputs, physics-derived targets.
PIPELINE_DATASET_SOURCE = DatasetSource(path=PIPELINE_DATASET_PATH, dataset_kind="LIVE", label_source="physics-derived")


def default_dataset_source() -> DatasetSource:
    """Luan's pipeline dataset unless the environment points elsewhere.

    The two known datasets carry their own labels. Any other path must state its
    dataset kind and label source in the environment; provenance is never guessed.
    """
    path = Path(os.environ.get(DATASET_PATH_ENV) or PIPELINE_DATASET_PATH)
    known = next((source for source in (EXAMPLE_DATASET_SOURCE, PIPELINE_DATASET_SOURCE) if path.resolve() == source.path.resolve()), None)
    dataset_kind = os.environ.get(DATASET_KIND_ENV) or (known.dataset_kind if known else None)
    label_source = os.environ.get(LABEL_SOURCE_ENV) or (known.label_source if known else None)
    if dataset_kind is None or label_source is None:
        raise DatasetError(f"{path} is not a known dataset: set {DATASET_KIND_ENV} and {LABEL_SOURCE_ENV} to declare its provenance")
    if dataset_kind not in _DATASET_KINDS:
        raise DatasetError(f"{DATASET_KIND_ENV} must be one of {_DATASET_KINDS}, got {dataset_kind!r}")
    if label_source not in _LABEL_SOURCES:
        raise DatasetError(f"{LABEL_SOURCE_ENV} must be one of {_LABEL_SOURCES}, got {label_source!r}")
    if (dataset_kind == "MOCK") != (label_source == "mock"):
        raise DatasetError(f"Inconsistent label: dataset_kind {dataset_kind!r} cannot use label_source {label_source!r}")
    return DatasetSource(path=path, dataset_kind=dataset_kind, label_source=label_source)


def load_dataset_split(source: DatasetSource) -> ChronologicalSplit:
    """Train/validation/test windows: delivered files for a directory, a chronological split for one CSV."""
    if not source.path.is_dir():
        try:
            return chronological_split(load_weather_rows(source.path))
        except ValueError as exc:
            raise DatasetError(f"{source.path}: {exc}") from exc
    windows = {name: tuple(load_weather_rows(source.path / file_name)) for name, file_name in SPLIT_FILE_NAMES.items()}
    split = ChronologicalSplit(**windows)
    if not split.train[-1]["timestamp"] < split.validation[0]["timestamp"] or not split.validation[-1]["timestamp"] < split.test[0]["timestamp"]:
        raise DatasetError(f"{source.path}: train, validation and test windows must not overlap in time")
    return split


def hourly_weather(rows: Sequence[WeatherFeatures]) -> list[WeatherFeatures]:
    """One feature row per distinct hour, in order; the label is dropped.

    Rows that share a timestamp differ only in panel angle, so the first is kept.
    """
    by_hour: dict[str, WeatherFeatures] = {}
    for row in rows:
        by_hour.setdefault(row["timestamp"], {name: value for name, value in row.items() if name != LABEL_COLUMN})
    return list(by_hour.values())


def load_weather_rows(path: Path) -> list[WeatherRow]:
    """Read a 13-column weather CSV into validated rows in non-decreasing time order."""
    if not path.is_file():
        raise DatasetError(f"Dataset not found: {path}")
    # utf-8-sig tolerates the byte-order mark that Excel and PowerShell 5 write.
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != WEATHER_COLUMNS:
            raise DatasetError(f"{path}: header must be exactly {WEATHER_COLUMNS}, got {header}")
        numbered = [(reader.line_num, _parse_row(values, reader.line_num, path)) for values in reader if values]
    if not numbered:
        raise DatasetError(f"{path}: no data rows")
    _require_chronological(numbered, path)
    return [row for _, row in numbered]


def _parse_row(values: list[str], line: int, path: Path) -> WeatherRow:
    if len(values) != len(WEATHER_COLUMNS):
        raise DatasetError(f"{path} line {line}: expected {len(WEATHER_COLUMNS)} values, got {len(values)}")
    try:
        row = {
            name: value if name == "timestamp" else float(value)
            for name, value in zip(WEATHER_COLUMNS, values)
        }
        validate_weather_row(row)
    except (ValueError, ContractError) as exc:
        raise DatasetError(f"{path} line {line}: {exc}") from exc
    return row


def _require_chronological(numbered: list[tuple[int, WeatherRow]], path: Path) -> None:
    """Time-aware splits rely on timestamps that never go backwards. Gaps are allowed
    here; sequence models must check spacing themselves."""
    instants = [datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")) for _, row in numbered]
    for (line, _), earlier, later in zip(numbered[1:], instants, instants[1:]):
        if later < earlier:
            raise DatasetError(f"{path} line {line}: rows are not in chronological order")
    weather_by_hour: dict[datetime, tuple] = {}
    seen: set[tuple[datetime, float]] = set()
    for (line, row), instant in zip(numbered, instants):
        key = (instant, row["panel_angle_deg"])
        if key in seen:
            raise DatasetError(f"{path} line {line}: duplicate row for {row['timestamp']} at {row['panel_angle_deg']:g} deg")
        seen.add(key)
        # Rows sharing an hour may differ only in panel angle and label; anything else would be silently dropped later.
        weather = tuple(row[name] for name in _WEATHER_ONLY_COLUMNS)
        if weather_by_hour.setdefault(instant, weather) != weather:
            raise DatasetError(f"{path} line {line}: weather for {row['timestamp']} differs between panel-angle rows")
