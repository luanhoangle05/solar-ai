"""Owner: Duy. LSTM adapter (PyTorch) behind the stable model ID `lstm`.

Each prediction reads a short window of hourly feature rows that ENDS at the
hour being predicted: the previous `sequence_length - 1` hours of recorded
features, then the current hour with the candidate panel angle. No row after
the prediction hour is ever read, and the label `actual_kwh` is never an input.

Limitation: the adapter needs the preceding hours in its history store. Asked
about an hour whose history it does not hold, it raises ToolError rather than
guessing, and the Modeling Agent reports the failure.
"""

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import nn

from src.common.schema import FEATURE_COLUMNS, CandidatePrediction, Metadata, WeatherFeatures, WeatherRow
from src.common.tool_contracts import ToolError
from src.models.advanced.features import at_candidate_angles, feature_matrix, label_vector


MODEL_NAME = "lstm"
IMPLEMENTATION = "pytorch"
STEP = timedelta(hours=1)
MIN_FEATURE_STD = 1e-6


@dataclass(frozen=True)
class LstmConfig:
    """Training hyperparameters; early stopping watches the tail of the train window."""

    sequence_length: int = 6
    hidden_size: int = 48
    max_epochs: int = 80
    patience: int = 10
    batch_size: int = 64
    learning_rate: float = 3e-3
    seed: int = 20261004


DEFAULT_LSTM_CONFIG = LstmConfig()


@dataclass(frozen=True)
class FeatureScaler:
    """Standardization fitted on the fit rows only; later rows never influence it."""

    mean: np.ndarray
    std: np.ndarray
    target_scale: float

    def scale(self, features: np.ndarray) -> np.ndarray:
        return (features - self.mean) / self.std


@dataclass(frozen=True)
class SequenceSet:
    """`inputs[k]` is the window ending at `rows[target_indices[k]]`."""

    inputs: np.ndarray
    target_indices: tuple[int, ...]


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_sequences(rows: Sequence[WeatherFeatures], sequence_length: int, *, first_target: int = 0) -> SequenceSet:
    """Windows of consecutive hourly rows, each ending at its own target row.

    A target is skipped when it lacks `sequence_length - 1` directly preceding
    hourly rows (start of data or a gap). `first_target` limits which rows may be
    targets while still letting their windows reach back into earlier rows.
    """
    if sequence_length < 1:
        raise ValueError("sequence_length must be at least 1")
    features = feature_matrix(rows)
    instants = [parse_timestamp(row["timestamp"]) for row in rows]
    targets = tuple(
        index for index in range(max(first_target, sequence_length - 1), len(rows))
        if all(instants[position] - instants[position - 1] == STEP for position in range(index - sequence_length + 2, index + 1))
    )
    windows = [features[index - sequence_length + 1:index + 1] for index in targets]
    inputs = np.stack(windows) if windows else np.empty((0, sequence_length, len(FEATURE_COLUMNS)))
    return SequenceSet(inputs=inputs, target_indices=targets)


class _Network(nn.Module):
    def __init__(self, feature_count: int, hidden_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(feature_count, hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(windows)
        return self.head(output[:, -1, :]).squeeze(-1)


class LstmPredictor:
    """`EnergyPredictor` over a trained network; predictions are clipped at 0 kWh."""

    implementation = IMPLEMENTATION

    def __init__(self, network: _Network, scaler: FeatureScaler, history: Mapping[datetime, np.ndarray], sequence_length: int) -> None:
        self._network, self._scaler, self._history, self._sequence_length = network, scaler, history, sequence_length

    def predict_kwh(self, weather: WeatherFeatures, candidate_angles_deg: tuple[float, ...], *, metadata: Metadata) -> list[CandidatePrediction]:
        past = self._history_before(weather["timestamp"])
        current = feature_matrix(at_candidate_angles(weather, candidate_angles_deg))
        windows = np.stack([np.vstack([past, row]) for row in current]) if len(current) else np.empty((0, self._sequence_length, len(FEATURE_COLUMNS)))
        predicted = _predict(self._network, self._scaler, windows)
        return [{"angle_deg": angle, "predicted_kwh": max(0.0, float(value))} for angle, value in zip(candidate_angles_deg, predicted)]

    def _history_before(self, timestamp: str) -> np.ndarray:
        """Feature rows for the hours strictly before `timestamp`, oldest first."""
        try:
            now = parse_timestamp(timestamp)
        except (ValueError, AttributeError) as exc:
            raise ToolError(f"LSTM cannot parse the prediction timestamp {timestamp!r}") from exc
        hours_back = range(self._sequence_length - 1, 0, -1)
        missing = [now - STEP * back for back in hours_back if now - STEP * back not in self._history]
        if missing:
            raise ToolError(f"LSTM history is missing {len(missing)} of the {self._sequence_length - 1} hours before {timestamp}")
        rows = [self._history[now - STEP * back] for back in hours_back]
        return np.array(rows).reshape(self._sequence_length - 1, len(FEATURE_COLUMNS))


def train_lstm(
    train_rows: Sequence[WeatherRow],
    early_stopping_rows: Sequence[WeatherRow],
    history_rows: Sequence[WeatherFeatures],
    config: LstmConfig = DEFAULT_LSTM_CONFIG,
) -> LstmPredictor:
    """Fit on `train_rows`, stop early on `early_stopping_rows` (which must directly follow them).

    `history_rows` supplies recorded features (never labels) that the adapter may
    look back on at prediction time; only hours before the predicted hour are read.
    """
    if not train_rows or not early_stopping_rows:
        raise ToolError("LSTM needs non-empty fit and early-stopping windows")
    torch.manual_seed(config.seed)
    scaler = _fit_scaler(train_rows)
    fit = build_sequences(train_rows, config.sequence_length)
    combined = [*train_rows, *early_stopping_rows]
    stop = build_sequences(combined, config.sequence_length, first_target=len(train_rows))
    if not fit.target_indices or not stop.target_indices:
        raise ToolError(f"Too few consecutive hourly rows to build LSTM sequences of length {config.sequence_length}")
    fit_inputs = _to_tensor(scaler.scale(fit.inputs))
    fit_targets = _to_tensor(label_vector(train_rows)[list(fit.target_indices)] / scaler.target_scale)
    stop_inputs = _to_tensor(scaler.scale(stop.inputs))
    stop_targets = _to_tensor(label_vector(combined)[list(stop.target_indices)] / scaler.target_scale)
    network = _fit_network(fit_inputs, fit_targets, stop_inputs, stop_targets, config)
    history = {parse_timestamp(row["timestamp"]): vector for row, vector in zip(history_rows, feature_matrix(history_rows))}
    return LstmPredictor(network, scaler, history, config.sequence_length)


def _fit_scaler(train_rows: Sequence[WeatherRow]) -> FeatureScaler:
    features, labels = feature_matrix(train_rows), label_vector(train_rows)
    std = features.std(axis=0)
    return FeatureScaler(mean=features.mean(axis=0), std=np.where(std < MIN_FEATURE_STD, 1.0, std), target_scale=max(float(labels.max()), MIN_FEATURE_STD))


def _fit_network(fit_inputs: torch.Tensor, fit_targets: torch.Tensor, stop_inputs: torch.Tensor, stop_targets: torch.Tensor, config: LstmConfig) -> _Network:
    network = _Network(fit_inputs.shape[-1], config.hidden_size)
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    loss_function = nn.MSELoss()
    shuffle = torch.Generator().manual_seed(config.seed)
    best_loss, best_state, epochs_without_improvement = float("inf"), copy.deepcopy(network.state_dict()), 0
    for _ in range(config.max_epochs):
        network.train()
        for batch in torch.randperm(len(fit_inputs), generator=shuffle).split(config.batch_size):
            optimizer.zero_grad()
            loss_function(network(fit_inputs[batch]), fit_targets[batch]).backward()
            optimizer.step()
        network.eval()
        with torch.no_grad():
            stop_loss = loss_function(network(stop_inputs), stop_targets).item()
        if stop_loss < best_loss:
            best_loss, best_state, epochs_without_improvement = stop_loss, copy.deepcopy(network.state_dict()), 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= config.patience:
                break
    network.load_state_dict(best_state)
    network.eval()
    return network


def _predict(network: _Network, scaler: FeatureScaler, windows: np.ndarray) -> np.ndarray:
    if not len(windows):
        return np.empty(0)
    with torch.no_grad():
        return network(_to_tensor(scaler.scale(windows))).numpy() * scaler.target_scale


def _to_tensor(values: np.ndarray) -> torch.Tensor:
    return torch.tensor(values, dtype=torch.float32)
