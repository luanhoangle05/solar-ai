import { CheckCircle2, CirclePause, MoveHorizontal, TriangleAlert } from "lucide-react";
import type { FarmRow } from "@/types/solar";

export const rowStatePresentation = {
  READY: { icon: CheckCircle2, color: "var(--success)", variant: "success" },
  MOVING: { icon: MoveHorizontal, color: "#48c9f4", variant: "default" },
  STOWED: { icon: CirclePause, color: "var(--warning)", variant: "warning" },
  FAULT: { icon: TriangleAlert, color: "var(--danger)", variant: "danger" },
} as const satisfies Record<FarmRow["current_state"], { icon: typeof CheckCircle2; color: string; variant: string }>;
