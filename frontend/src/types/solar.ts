import type { z } from "zod";

import {
  actionSchema,
  agentNameSchema,
  candidatePredictionSchema,
  currentWeatherSchema,
  dataAgentReportSchema,
  dataStatusSchema,
  decisionSchema,
  farmRowSchema,
  farmStatusSchema,
  farmZoneSchema,
  frontendDataSchema,
  historicalDecisionSchema,
  metadataSchema,
  modelMetricsSchema,
  modelNameSchema,
  optimizationResultSchema,
  runErrorSchema,
  safetyCheckSchema,
  safetyResultSchema,
} from "@/schemas/frontend-data";

export type Action = z.infer<typeof actionSchema>;
export type AgentName = z.infer<typeof agentNameSchema>;
export type CandidatePrediction = z.infer<typeof candidatePredictionSchema>;
export type CurrentWeather = z.infer<typeof currentWeatherSchema>;
export type DataAgentReport = z.infer<typeof dataAgentReportSchema>;
export type DataStatus = z.infer<typeof dataStatusSchema>;
export type Decision = z.infer<typeof decisionSchema>;
export type FarmRow = z.infer<typeof farmRowSchema>;
export type FarmStatus = z.infer<typeof farmStatusSchema>;
export type FarmZone = z.infer<typeof farmZoneSchema>;
export type FrontendData = z.infer<typeof frontendDataSchema>;
export type HistoricalDecision = z.infer<typeof historicalDecisionSchema>;
export type Metadata = z.infer<typeof metadataSchema>;
export type ModelMetrics = z.infer<typeof modelMetricsSchema>;
export type ModelName = z.infer<typeof modelNameSchema>;
export type OptimizationResult = z.infer<typeof optimizationResultSchema>;
export type RunError = z.infer<typeof runErrorSchema>;
export type SafetyCheck = z.infer<typeof safetyCheckSchema>;
export type SafetyResult = z.infer<typeof safetyResultSchema>;
