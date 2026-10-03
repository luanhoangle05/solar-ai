import type { ModelName } from "@/types/solar";

export function formatAngle(value: number | null): string {
  return value === null ? "Unavailable" : `${value.toFixed(0)}°`;
}

export function formatKwh(value: number | null): string {
  return value === null ? "Unavailable" : `${value.toFixed(2)} kWh`;
}

export function formatSignedKwh(value: number | null): string {
  if (value === null) {
    return "Unavailable";
  }

  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)} kWh`;
}

export function formatKwhEquivalent(value: number | null): string {
  if (value === null) {
    return "Unavailable";
  }

  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)} kWh eq.`;
}

export function formatModelName(model: ModelName | null): string {
  if (model === null) {
    return "Unavailable";
  }

  const labels: Record<ModelName, string> = {
    linear_regression: "Linear Regression",
    random_forest: "Random Forest",
    boosting: "Boosting",
    lstm: "LSTM",
  };

  return labels[model];
}
