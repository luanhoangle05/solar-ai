import type {
  FrontendData,
  ModelMetrics,
} from "@/types/solar";

export interface FrontendSummary {
  currentAngleDeg: number;
  recommendedAngleDeg: number | null;
  predictedKwh: number | null;
  energyGainKwh: number | null;
  movementCostKwhEquivalent: number | null;
  netBenefitKwhEquivalent: number | null;
  decisionAction: FrontendData["decision"]["action"];
  decisionTargetAngleDeg: number;
}

export function getControlTargetRow(data: FrontendData) {
  return (
    data.farm_status.rows.find(
      (row) => row.row_id === data.metadata.control_target_id,
    ) ?? null
  );
}

export function getSelectedModel(
  data: FrontendData,
): ModelMetrics | null {
  if (data.selected_model === null) {
    return null;
  }

  return (
    data.model_comparison.find(
      (model) => model.model === data.selected_model,
    ) ?? null
  );
}

export function getFrontendSummary(
  data: FrontendData,
): FrontendSummary {
  const targetRow = getControlTargetRow(data);
  const optimization = data.optimization;

  return {
    currentAngleDeg:
      optimization?.current_angle_deg ??
      targetRow?.angle_deg ??
      data.decision.target_angle_deg,
    recommendedAngleDeg: optimization?.recommended_angle_deg ?? null,
    predictedKwh: optimization?.predicted_kwh ?? null,
    energyGainKwh: optimization?.energy_gain_kwh ?? null,
    movementCostKwhEquivalent:
      optimization?.movement_cost_kwh_equivalent ?? null,
    netBenefitKwhEquivalent:
      optimization?.net_benefit_kwh_equivalent ?? null,
    decisionAction: data.decision.action,
    decisionTargetAngleDeg: data.decision.target_angle_deg,
  };
}
