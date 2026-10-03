import type { DataStatus } from "@/types/solar";
export const dataStatusVariants = {
  VALID: "success", DEGRADED: "warning", STALE: "warning", INVALID: "danger",
} as const satisfies Record<DataStatus, "success" | "warning" | "danger">;
