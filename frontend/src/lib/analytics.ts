import type { FrontendData } from "../types/solar";
import { getOptimizationSummary } from "./optimization";
import { getAgentsSummary } from "./agents";
import { getRowCounts } from "./farm";

export function getAnalyticsView(data: FrontendData) {
  return { optimization: getOptimizationSummary(data), agents: getAgentsSummary(data),
    farm: getRowCounts(data.farm_status.rows), rowCount: data.farm_status.rows.length,
    // History is kept separate from the current run; no interpolated or appended events.
    history: [...data.history].sort((a,b) => Date.parse(b.timestamp)-Date.parse(a.timestamp)),
    current: { timestamp: data.timestamp, decision: data.decision, target: data.metadata.control_target_id,
      netBenefit: data.optimization?.net_benefit_kwh_equivalent ?? null },
  };
}
