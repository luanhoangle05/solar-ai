import { CirclePause, RotateCw, ShieldAlert } from "lucide-react";

export const actionPresentation = {
  ROTATE: { icon: RotateCw, variant: "success", color: "var(--success)" },
  HOLD: { icon: CirclePause, variant: "warning", color: "var(--warning)" },
  STOW: { icon: ShieldAlert, variant: "danger", color: "var(--danger)" },
} as const;
