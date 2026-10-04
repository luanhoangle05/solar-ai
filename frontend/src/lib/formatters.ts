import type { ModelName } from "@/types/solar";

export function formatAngle(value: number | null): string {
  return value === null ? "Unavailable" : `${value}°`;
}

export function formatKwh(value: number | null, decimals = 2): string {
  return value === null ? "Unavailable" : `${value.toFixed(decimals)} kWh`;
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

export function formatDisplayName(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function formatMetric(value: number | null): string {
  return value === null ? "Unavailable" : value.toFixed(4);
}

export function formatRecordedTime(value: string, date = true): string {
  return new Intl.DateTimeFormat("en-GB", {
    ...(date ? { day: "2-digit", month: "short", year: "numeric" } as const : {}),
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: "UTC",
  }).format(new Date(value)) + " UTC";
}

export function formatMovementCost(value: number): string {
  return value.toFixed(2) + " kWh eq.";
}

/** Candidate inspection keeps close predictions distinct without floating-point noise. */
export function formatCandidateEnergy(value: number | null): string {
  return formatKwh(value, 3);
}
