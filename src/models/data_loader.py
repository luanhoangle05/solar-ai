"""Owner: Duy. The single entry point for labeled weather rows.

Every trainer and evaluator reads through `load_weather_rows`, so switching
from the synthetic example dataset to Luan's real pipeline output is a
path/config change (see the environment variables below), not a code change.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import get_args, get_type_hints

from src.common.schema import ContractError, Metadata, WEATHER_COLUMNS, WeatherRow, validate_weather_row


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DATASET_PATH = ROOT / "data" / "example" / "example_weather.csv"

DATASET_PATH_ENV = "SOLAR_DATASET_PATH"
DATASET_KIND_ENV = "SOLAR_DATASET_KIND"
LABEL_SOURCE_ENV = "SOLAR_LABEL_SOURCE"

_METADATA_HINTS = get_type_hints(Metadata)
_DATASET_KINDS = get_args(_METADATA_HINTS["dataset_kind"])
_LABEL_SOURCES = get_args(_METADATA_HINTS["label_source"])
_HEADER_LINE = 1


class DatasetError(ValueError):
    """The dataset file is missing, malformed, or breaks the weather contract."""


@dataclass(frozen=True)
class DatasetSource:
    """Where labeled rows come from and how outputs built on them are labeled."""

    path: Path
    dataset_kind: str
    label_source: str


def default_dataset_source() -> DatasetSource:
    """Example dataset (MOCK/mock) unless the environment points elsewhere."""
    path = Path(os.environ.get(DATASET_PATH_ENV) or EXAMPLE_DATASET_PATH)
    dataset_kind = os.environ.get(DATASET_KIND_ENV) or "MOCK"
    label_source = os.environ.get(LABEL_SOURCE_ENV) or "mock"
    if dataset_kind not in _DATASET_KINDS:
        raise DatasetError(f"{DATASET_KIND_ENV} must be one of {_DATASET_KINDS}, got {dataset_kind!r}")
    if label_source not in _LABEL_SOURCES:
        raise DatasetError(f"{LABEL_SOURCE_ENV} must be one of {_LABEL_SOURCES}, got {label_source!r}")
    if (dataset_kind == "MOCK") != (label_source == "mock"):
        raise DatasetError(f"Inconsistent label: dataset_kind {dataset_kind!r} cannot use label_source {label_source!r}")
    return DatasetSource(path=path, dataset_kind=dataset_kind, label_source=label_source)


def load_weather_rows(path: Path) -> list[WeatherRow]:
    """Read a 13-column weather CSV into validated, chronological rows."""
    if not path.is_file():
        raise DatasetError(f"Dataset not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != WEATHER_COLUMNS:
            raise DatasetError(f"{path}: header must be exactly {WEATHER_COLUMNS}, got {header}")
        rows = [_parse_row(values, line, path) for line, values in enumerate(reader, start=_HEADER_LINE + 1)]
    if not rows:
        raise DatasetError(f"{path}: no data rows")
    _require_chronological(rows, path)
    return rows


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


def _require_chronological(rows: list[WeatherRow], path: Path) -> None:
    """Time-aware splits rely on strictly increasing timestamps."""
    instants = [datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")) for row in rows]
    for index, (earlier, later) in enumerate(zip(instants, instants[1:]), start=_HEADER_LINE + 2):
        if later <= earlier:
            raise DatasetError(f"{path} line {index}: rows are not in strictly chronological order")
