import { z } from "zod";

const SCHEMA_VERSION = "0.1.0";
const PREDICTION_HORIZON_MINUTES = 60;
const TOTAL_PANELS = 1000;
const ROW_COUNT = 50;
const ZONE_COUNT = 4;
const PANELS_PER_ROW = 20;
const DEFAULT_CONFIG_ID = "prototype-row-hour-v1";
const DEFAULT_MIN_NET_BENEFIT_KWH_EQUIVALENT = 0.02;
const DEFAULT_MAX_FORECAST_AGE_MINUTES = 30;
const DEFAULT_STOW_ANGLE_DEG = 0;

const finiteNumber = z.number().finite();
const nonNegativeNumber = finiteNumber.min(0);
const angleDeg = finiteNumber.min(0).max(90);

function isTimezoneAwareTimestamp(value: string): boolean {
  if (!/(Z|[+-]\d{2}:\d{2})$/i.test(value)) {
    return false;
  }

  return Number.isFinite(Date.parse(value));
}

const timestampSchema = z
  .string()
  .refine(isTimezoneAwareTimestamp, "Timestamp must be valid and timezone-aware");

export const actionSchema = z.enum(["ROTATE", "HOLD", "STOW"]);
export const modelNameSchema = z.enum([
  "linear_regression",
  "random_forest",
  "boosting",
  "lstm",
]);
export const agentNameSchema = z.enum([
  "data",
  "modeling",
  "optimization",
  "manager",
]);
export const dataStatusSchema = z.enum([
  "VALID",
  "DEGRADED",
  "STALE",
  "INVALID",
]);

export const metadataSchema = z
  .object({
    schema_version: z.literal(SCHEMA_VERSION),
    dataset_kind: z.enum(["MOCK", "LIVE"]),
    label_source: z.enum([
      "mock",
      "measured",
      "physics-derived",
      "unavailable",
    ]),
    energy_scope: z.literal("row"),
    prediction_horizon_minutes: z.literal(PREDICTION_HORIZON_MINUTES),
    interval_start: timestampSchema,
    control_target_id: z.string().min(1),
    config_id: z.string().min(1),
    assumptions: z.array(z.string()),
  })
  .strict()
  .superRefine((metadata, ctx) => {
    if (
      metadata.dataset_kind === "MOCK" &&
      metadata.label_source !== "mock"
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["label_source"],
        message: "MOCK payloads must use label_source='mock'.",
      });
    }

    if (
      metadata.dataset_kind === "LIVE" &&
      metadata.label_source === "mock"
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["label_source"],
        message: "LIVE payloads cannot use mock labels.",
      });
    }
  });

export const currentWeatherSchema = z
  .object({
    temperature_c: finiteNumber,
    cloud_cover_pct: finiteNumber.min(0).max(100),
    precipitation_mm: nonNegativeNumber,
    wind_speed_kmh: nonNegativeNumber,
    wind_gust_kmh: nonNegativeNumber,
    ghi_wm2: nonNegativeNumber,
    dni_wm2: nonNegativeNumber,
    dhi_wm2: nonNegativeNumber,
  })
  .strict()
  .superRefine((weather, ctx) => {
    if (weather.wind_gust_kmh < weather.wind_speed_kmh) {
      ctx.addIssue({
        code: "custom",
        path: ["wind_gust_kmh"],
        message: "Wind gust cannot be below sustained wind speed.",
      });
    }
  });

export const dataAgentReportSchema = z
  .object({
    status: dataStatusSchema,
    source: z.string().min(1),
    forecast_age_minutes: nonNegativeNumber.nullable(),
    used_cache: z.boolean(),
    issues: z.array(z.string()),
  })
  .strict()
  .superRefine((report, ctx) => {
    if (
      report.forecast_age_minutes === null &&
      !["STALE", "INVALID"].includes(report.status)
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["forecast_age_minutes"],
        message: "Unknown forecast age cannot be considered reliable.",
      });
    }

    if (report.status !== "VALID" && report.issues.length === 0) {
      ctx.addIssue({
        code: "custom",
        path: ["issues"],
        message: "Non-VALID data requires at least one issue explanation.",
      });
    }
  });

export const modelMetricsSchema = z
  .object({
    model: modelNameSchema,
    implementation: z.string(),
    status: z.enum(["MOCK", "VALIDATED", "UNAVAILABLE"]),
    mae: finiteNumber.nullable(),
    rmse: finiteNumber.nullable(),
    r2: finiteNumber.nullable(),
  })
  .strict()
  .superRefine((entry, ctx) => {
    const metrics = [entry.mae, entry.rmse, entry.r2];

    if (entry.status === "UNAVAILABLE") {
      if (!metrics.every((metric) => metric === null)) {
        ctx.addIssue({
          code: "custom",
          message: "UNAVAILABLE model metrics must all be null.",
        });
      }
      return;
    }

    if (metrics.some((metric) => metric === null)) {
      ctx.addIssue({
        code: "custom",
        message: "Available model must provide MAE, RMSE, and R2.",
      });
      return;
    }

    if (entry.mae! < 0 || entry.rmse! < entry.mae! - 1e-9) {
      ctx.addIssue({
        code: "custom",
        message: "Expected RMSE >= MAE >= 0.",
      });
    }

    if (entry.r2! > 1) {
      ctx.addIssue({
        code: "custom",
        path: ["r2"],
        message: "R2 cannot exceed 1.",
      });
    }
  });

export const candidatePredictionSchema = z
  .object({
    angle_deg: angleDeg,
    predicted_kwh: nonNegativeNumber,
  })
  .strict();

export const optimizationResultSchema = z
  .object({
    current_angle_deg: angleDeg,
    recommended_angle_deg: angleDeg,
    baseline_kwh: nonNegativeNumber,
    predicted_kwh: nonNegativeNumber,
    energy_gain_kwh: finiteNumber,
    movement_cost_kwh_equivalent: nonNegativeNumber,
    net_benefit_kwh_equivalent: finiteNumber,
  })
  .strict()
  .superRefine((optimization, ctx) => {
    const expectedGain =
      optimization.predicted_kwh - optimization.baseline_kwh;
    const expectedNet =
      optimization.energy_gain_kwh -
      optimization.movement_cost_kwh_equivalent;

    if (Math.abs(optimization.energy_gain_kwh - expectedGain) > 1e-9) {
      ctx.addIssue({
        code: "custom",
        path: ["energy_gain_kwh"],
        message: "Energy gain does not equal predicted - baseline.",
      });
    }

    if (
      Math.abs(
        optimization.net_benefit_kwh_equivalent - expectedNet,
      ) > 1e-9
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["net_benefit_kwh_equivalent"],
        message: "Net benefit does not equal gain - movement cost.",
      });
    }
  });

export const safetyCheckSchema = z
  .object({
    name: z.string(),
    passed: z.boolean(),
    severity: z.enum(["INFO", "BLOCK_ROTATE", "SEVERE"]),
    reason: z.string(),
  })
  .strict();

export const safetyResultSchema = z
  .object({
    passed: z.boolean(),
    checks: z.array(safetyCheckSchema).min(1),
    reason: z.string(),
  })
  .strict()
  .superRefine((safety, ctx) => {
    const expectedPassed = safety.checks.every((check) => check.passed);

    if (safety.passed !== expectedPassed) {
      ctx.addIssue({
        code: "custom",
        path: ["passed"],
        message: "Safety summary contradicts individual checks.",
      });
    }
  });

export const decisionSchema = z
  .object({
    action: actionSchema,
    target_angle_deg: angleDeg,
    reason: z.string(),
  })
  .strict();

export const farmZoneSchema = z
  .object({
    zone_id: z.string(),
    row_ids: z.array(z.string()).min(1),
    panel_count: z.number().int().nonnegative(),
  })
  .strict();

export const farmRowSchema = z
  .object({
    row_id: z.string(),
    zone_id: z.string(),
    panel_count: z.number().int().nonnegative(),
    angle_deg: angleDeg,
    current_state: z.enum(["READY", "MOVING", "STOWED", "FAULT"]),
    action: actionSchema,
  })
  .strict();

export const farmStatusSchema = z
  .object({
    total_panels: z.number().int().nonnegative(),
    zones: z.array(farmZoneSchema),
    rows: z.array(farmRowSchema),
  })
  .strict();

export const agentLogEntrySchema = z
  .object({
    timestamp: timestampSchema,
    agent: agentNameSchema,
    action: z.string(),
    result: z.string(),
  })
  .strict();

export const runErrorSchema = z
  .object({
    agent: agentNameSchema,
    code: z.string(),
    message: z.string(),
  })
  .strict();

export const historicalDecisionSchema = z
  .object({
    timestamp: timestampSchema,
    control_target_id: z.string(),
    decision: decisionSchema,
    net_benefit_kwh_equivalent: finiteNumber,
  })
  .strict();

const frontendDataShape = z
  .object({
    timestamp: timestampSchema,
    metadata: metadataSchema,
    current_weather: currentWeatherSchema.nullable(),
    data_agent: dataAgentReportSchema,
    model_comparison: z.array(modelMetricsSchema),
    selected_model: modelNameSchema.nullable(),
    candidate_predictions: z.array(candidatePredictionSchema),
    optimization: optimizationResultSchema.nullable(),
    safety: safetyResultSchema,
    decision: decisionSchema,
    farm_status: farmStatusSchema,
    agent_log: z.array(agentLogEntrySchema),
    history: z.array(historicalDecisionSchema),
    errors: z.array(runErrorSchema),
  })
  .strict();

export const frontendDataSchema = frontendDataShape.superRefine((data, ctx) => {
  // Model contract -----------------------------------------------------
  const expectedModelNames = new Set([
    "linear_regression",
    "random_forest",
    "boosting",
    "lstm",
  ]);

  const actualModelNames = new Set(
    data.model_comparison.map((entry) => entry.model),
  );

  if (
    data.model_comparison.length !== 4 ||
    actualModelNames.size !== 4 ||
    [...expectedModelNames].some((name) => !actualModelNames.has(name as never))
  ) {
    ctx.addIssue({
      code: "custom",
      path: ["model_comparison"],
      message: "Expected exactly four distinct canonical models.",
    });
  }

  if (data.metadata.dataset_kind === "LIVE") {
    data.model_comparison.forEach((entry, index) => {
      if (entry.status === "MOCK") {
        ctx.addIssue({
          code: "custom",
          path: ["model_comparison", index, "status"],
          message: "LIVE payload cannot contain MOCK model metrics.",
        });
      }
    });
  }

  if (data.selected_model === null) {
    const allUnavailable = data.model_comparison.every(
      (entry) =>
        entry.status === "UNAVAILABLE" &&
        entry.mae === null &&
        entry.rmse === null &&
        entry.r2 === null,
    );

    if (!allUnavailable) {
      ctx.addIssue({
        code: "custom",
        path: ["model_comparison"],
        message:
          "No selected model means all model metrics must be UNAVAILABLE/null.",
      });
    }

    if (data.candidate_predictions.length > 0 || data.optimization !== null) {
      ctx.addIssue({
        code: "custom",
        message:
          "No selected model cannot claim predictions or optimization.",
      });
    }
  } else {
    const selected = data.model_comparison.find(
      (entry) => entry.model === data.selected_model,
    );

    if (!selected || selected.status === "UNAVAILABLE") {
      ctx.addIssue({
        code: "custom",
        path: ["selected_model"],
        message: "Selected model must exist and be available.",
      });
    }

    if (data.candidate_predictions.length === 0) {
      ctx.addIssue({
        code: "custom",
        path: ["candidate_predictions"],
        message: "Selected model requires candidate predictions.",
      });
    }
  }

  const candidateAngles = new Set<number>();
  data.candidate_predictions.forEach((candidate, index) => {
    if (candidateAngles.has(candidate.angle_deg)) {
      ctx.addIssue({
        code: "custom",
        path: ["candidate_predictions", index, "angle_deg"],
        message: "Duplicate candidate angle.",
      });
    }
    candidateAngles.add(candidate.angle_deg);
  });

  // Decision / safety contract ----------------------------------------
  const severeFailure = data.safety.checks.some(
    (check) => !check.passed && check.severity === "SEVERE",
  );

  if (severeFailure && data.decision.action !== "STOW") {
    ctx.addIssue({
      code: "custom",
      path: ["decision", "action"],
      message: "A severe safety failure requires STOW.",
    });
  }

  if (data.decision.action === "ROTATE") {
    if (!data.safety.passed) {
      ctx.addIssue({
        code: "custom",
        path: ["decision"],
        message: "ROTATE cannot bypass a failed safety result.",
      });
    }

    if (!data.optimization) {
      ctx.addIssue({
        code: "custom",
        path: ["optimization"],
        message: "ROTATE requires an optimization result.",
      });
    } else {
      if (
        data.decision.target_angle_deg !==
        data.optimization.recommended_angle_deg
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["decision", "target_angle_deg"],
          message: "ROTATE target must equal the recommended angle.",
        });
      }

      if (data.optimization.net_benefit_kwh_equivalent <= 0) {
        ctx.addIssue({
          code: "custom",
          path: ["optimization", "net_benefit_kwh_equivalent"],
          message: "ROTATE requires positive net benefit.",
        });
      }
    }

    if (!["VALID", "DEGRADED"].includes(data.data_agent.status)) {
      ctx.addIssue({
        code: "custom",
        path: ["data_agent", "status"],
        message: "Unreliable data cannot authorize ROTATE.",
      });
    }

    if (data.current_weather === null) {
      ctx.addIssue({
        code: "custom",
        path: ["current_weather"],
        message: "ROTATE requires current weather.",
      });
    }
  }

  if (
    data.decision.action === "HOLD" &&
    data.optimization &&
    data.decision.target_angle_deg !== data.optimization.current_angle_deg
  ) {
    ctx.addIssue({
      code: "custom",
      path: ["decision", "target_angle_deg"],
      message: "HOLD must preserve the current optimization angle.",
    });
  }

  // Candidate / optimization consistency ------------------------------
  if (data.optimization) {
    const baselinePrediction = data.candidate_predictions.find(
      (candidate) =>
        candidate.angle_deg === data.optimization!.current_angle_deg,
    );

    const recommendedPrediction = data.candidate_predictions.find(
      (candidate) =>
        candidate.angle_deg === data.optimization!.recommended_angle_deg,
    );

    if (
      !baselinePrediction ||
      baselinePrediction.predicted_kwh !== data.optimization.baseline_kwh
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["optimization", "baseline_kwh"],
        message: "Missing or mismatched stay-baseline prediction.",
      });
    }

    if (
      !recommendedPrediction ||
      recommendedPrediction.predicted_kwh !==
        data.optimization.predicted_kwh
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["optimization", "predicted_kwh"],
        message: "Missing or mismatched recommended prediction.",
      });
    }
  }

  // Farm consistency --------------------------------------------------
  if (data.farm_status.total_panels !== TOTAL_PANELS) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "total_panels"],
      message: "Expected exactly 1000 panels.",
    });
  }

  if (data.farm_status.rows.length !== ROW_COUNT) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "rows"],
      message: "Expected exactly 50 farm rows.",
    });
  }

  if (data.farm_status.zones.length !== ZONE_COUNT) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "zones"],
      message: "Expected exactly four zones.",
    });
  }

  const rowMap = new Map(
    data.farm_status.rows.map((row) => [row.row_id, row]),
  );

  if (rowMap.size !== data.farm_status.rows.length) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "rows"],
      message: "Duplicate row ID.",
    });
  }

  if (!rowMap.has(data.metadata.control_target_id)) {
    ctx.addIssue({
      code: "custom",
      path: ["metadata", "control_target_id"],
      message: "Control target does not exist in farm rows.",
    });
  }

  const zoneIds = new Set(data.farm_status.zones.map((zone) => zone.zone_id));
  if (zoneIds.size !== data.farm_status.zones.length) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "zones"],
      message: "Duplicate zone ID.",
    });
  }

  const memberships: string[] = [];

  data.farm_status.zones.forEach((zone, zoneIndex) => {
    memberships.push(...zone.row_ids);

    zone.row_ids.forEach((rowId) => {
      const row = rowMap.get(rowId);

      if (!row || row.zone_id !== zone.zone_id) {
        ctx.addIssue({
          code: "custom",
          path: ["farm_status", "zones", zoneIndex, "row_ids"],
          message: `Invalid zone membership for ${rowId}.`,
        });
      }
    });

    if (zone.panel_count !== zone.row_ids.length * PANELS_PER_ROW) {
      ctx.addIssue({
        code: "custom",
        path: ["farm_status", "zones", zoneIndex, "panel_count"],
        message: "Zone panel count must equal row count Ã— 20.",
      });
    }
  });

  if (
    memberships.length !== ROW_COUNT ||
    new Set(memberships).size !== ROW_COUNT ||
    [...rowMap.keys()].some((rowId) => !memberships.includes(rowId))
  ) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status"],
      message: "Every row must belong to exactly one zone.",
    });
  }

  data.farm_status.rows.forEach((row, index) => {
    if (row.panel_count !== PANELS_PER_ROW) {
      ctx.addIssue({
        code: "custom",
        path: ["farm_status", "rows", index, "panel_count"],
        message: "Each row must contain exactly 20 panels.",
      });
    }
  });

  const zonePanelTotal = data.farm_status.zones.reduce(
    (total, zone) => total + zone.panel_count,
    0,
  );

  if (zonePanelTotal !== TOTAL_PANELS) {
    ctx.addIssue({
      code: "custom",
      path: ["farm_status", "zones"],
      message: "Zone panel counts must total 1000.",
    });
  }

  const targetRow = rowMap.get(data.metadata.control_target_id);

  if (targetRow) {
    if (
      data.decision.action === "HOLD" &&
      data.decision.target_angle_deg !== targetRow.angle_deg
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["decision", "target_angle_deg"],
        message: "HOLD target must equal the control row angle.",
      });
    }

    if (targetRow.action !== data.decision.action) {
      ctx.addIssue({
        code: "custom",
        path: ["farm_status", "rows"],
        message: "Control-row action must match the final decision.",
      });
    }
  }

  // Current prototype configuration invariants ------------------------
  if (data.metadata.config_id === DEFAULT_CONFIG_ID) {
    if (data.decision.action === "ROTATE" && data.optimization) {
      if (
        data.optimization.net_benefit_kwh_equivalent <=
        DEFAULT_MIN_NET_BENEFIT_KWH_EQUIVALENT
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["optimization", "net_benefit_kwh_equivalent"],
          message: "ROTATE net benefit is below the prototype threshold.",
        });
      }

      const age = data.data_agent.forecast_age_minutes;
      if (age === null || age > DEFAULT_MAX_FORECAST_AGE_MINUTES) {
        ctx.addIssue({
          code: "custom",
          path: ["data_agent", "forecast_age_minutes"],
          message: "ROTATE cannot use a stale prototype forecast.",
        });
      }
    }

    if (
      data.decision.action === "STOW" &&
      data.decision.target_angle_deg !== DEFAULT_STOW_ANGLE_DEG
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["decision", "target_angle_deg"],
        message: "STOW angle differs from the prototype configuration.",
      });
    }
  }
});

export type FrontendDataInput = z.input<typeof frontendDataSchema>;
