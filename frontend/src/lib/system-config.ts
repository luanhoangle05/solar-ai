import type { FrontendData } from "../types/solar";
import { getFarmSummary } from "./farm";
import { getSelectedModel } from "./selectors";

export function getSystemConfigView(data: FrontendData) {
  return { readOnly: true as const, metadata: data.metadata, farm: getFarmSummary(data),
    timestamp: data.timestamp, source: data.data_agent, selectedModel: getSelectedModel(data) };
}
