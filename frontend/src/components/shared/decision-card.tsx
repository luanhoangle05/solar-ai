import {
  ArrowRight,
  CirclePause,
  RotateCw,
  ShieldAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatAngle } from "@/lib/formatters";
import type { Decision } from "@/types/solar";

interface DecisionCardProps {
  decision: Decision;
  safetyPassed: boolean;
}

const actionPresentation = {
  ROTATE: {
    label: "ROTATE",
    variant: "success" as const,
    icon: RotateCw,
  },
  HOLD: {
    label: "HOLD",
    variant: "warning" as const,
    icon: CirclePause,
  },
  STOW: {
    label: "STOW",
    variant: "danger" as const,
    icon: ShieldAlert,
  },
};

export function DecisionCard({
  decision,
  safetyPassed,
}: DecisionCardProps) {
  const presentation = actionPresentation[decision.action];
  const Icon = presentation.icon;

  return (
    <Card className="h-full border-primary/25">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardDescription>Final Manager Decision</CardDescription>
            <CardTitle className="mt-2 flex items-center gap-3 text-3xl">
              <Icon className="size-7 text-primary" aria-hidden="true" />
              {presentation.label}
            </CardTitle>
          </div>

          <Badge variant={safetyPassed ? "success" : "danger"}>
            Safety {safetyPassed ? "Passed" : "Blocked"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">Target</span>
          <ArrowRight className="size-4 text-primary" aria-hidden="true" />
          <span className="font-semibold text-foreground">
            {formatAngle(decision.target_angle_deg)}
          </span>
        </div>

        <p className="text-sm leading-6 text-muted-foreground">
          {decision.reason}
        </p>
      </CardContent>
    </Card>
  );
}
