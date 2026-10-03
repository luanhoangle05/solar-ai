import { describe, expect, it } from "vitest";

import {
  loadFrontendData,
  parseFrontendData,
} from "../lib/frontend-data.server";
import {
  getControlTargetRow,
  getFrontendSummary,
  getSelectedModel,
} from "../lib/selectors";
import { frontendDataSchema } from "./frontend-data";

describe("SolarAI FrontendData contract", () => {
  it("accepts the repository's shared frontend fixture", async () => {
    const data = await loadFrontendData();

    expect(data.metadata.schema_version).toBe("0.1.0");
    expect(data.metadata.dataset_kind).toBe("MOCK");
    expect(data.metadata.label_source).toBe("mock");
    expect(data.metadata.energy_scope).toBe("row");

    expect(data.farm_status.total_panels).toBe(1000);
    expect(data.farm_status.rows).toHaveLength(50);
    expect(data.farm_status.zones).toHaveLength(4);

    expect(data.farm_status.zones.map((zone) => zone.panel_count)).toEqual([
      260,
      240,
      260,
      240,
    ]);
  });

  it("selects the current mock recommendation without recalculating it", async () => {
    const data = await loadFrontendData();
    const summary = getFrontendSummary(data);

    expect(summary.currentAngleDeg).toBe(35);
    expect(summary.recommendedAngleDeg).toBe(45);
    expect(summary.predictedKwh).toBe(6.09);
    expect(summary.energyGainKwh).toBeCloseTo(0.29, 12);
    expect(summary.movementCostKwhEquivalent).toBe(0.03);
    expect(summary.netBenefitKwhEquivalent).toBe(0.26);
    expect(summary.decisionAction).toBe("ROTATE");
    expect(summary.decisionTargetAngleDeg).toBe(45);
  });

  it("resolves the contract control target and selected model", async () => {
    const data = await loadFrontendData();

    expect(getControlTargetRow(data)?.row_id).toBe("row-001");
    expect(getControlTargetRow(data)?.action).toBe("ROTATE");

    const model = getSelectedModel(data);
    expect(model?.model).toBe("boosting");
    expect(model?.implementation).toBe("xgboost");
    expect(model?.status).toBe("MOCK");
  });

  it("rejects unknown top-level fields", async () => {
    const data = await loadFrontendData();
    const invalid: Record<string, unknown> = {
      ...structuredClone(data),
      unsupported_field: true,
    };

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects an invalid decision action", async () => {
    const data = await loadFrontendData();
    const invalid = structuredClone(data) as unknown as {
      decision: { action: string };
    };

    invalid.decision.action = "MOVE";

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects contradictory safety summary", async () => {
    const data = await loadFrontendData();
    const invalid = structuredClone(data);

    invalid.safety.passed = false;

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects ROTATE when net benefit is not positive", async () => {
    const data = await loadFrontendData();
    const invalid = structuredClone(data);

    if (!invalid.optimization) {
      throw new Error("Expected fixture optimization.");
    }

    invalid.optimization.predicted_kwh = invalid.optimization.baseline_kwh;
    invalid.optimization.energy_gain_kwh = 0;
    invalid.optimization.movement_cost_kwh_equivalent = 0;
    invalid.optimization.net_benefit_kwh_equivalent = 0;

    const candidate = invalid.candidate_predictions.find(
      (item) =>
        item.angle_deg === invalid.optimization!.recommended_angle_deg,
    );

    if (!candidate) {
      throw new Error("Expected recommended candidate.");
    }

    candidate.predicted_kwh = invalid.optimization.baseline_kwh;

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects duplicate candidate angles", async () => {
    const data = await loadFrontendData();
    const invalid = structuredClone(data);

    invalid.candidate_predictions[1].angle_deg =
      invalid.candidate_predictions[0].angle_deg;

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects broken farm membership", async () => {
    const data = await loadFrontendData();
    const invalid = structuredClone(data);

    invalid.farm_status.zones[0].row_ids[0] = "row-050";

    expect(frontendDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("returns a readable validation error for invalid input", async () => {
    await expect(parseFrontendData({})).rejects.toMatchObject({
      name: "FrontendDataLoadError",
    });
  });
});
