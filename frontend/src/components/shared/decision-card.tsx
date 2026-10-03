import type { CSSProperties } from "react";
import { ArrowRight, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { actionPresentation } from "@/config/actions";
import { formatAngle } from "@/lib/formatters";
import type { Decision } from "@/types/solar";

interface DecisionCardProps {
  decision: Decision;
  safetyPassed: boolean;
  currentAngle?: number | null;
}

export function DecisionCard({ decision, safetyPassed, currentAngle = null }: DecisionCardProps) {
  const presentation = actionPresentation[decision.action];
  const Icon = presentation.icon;
  return (
    <Card className="dashboard-decision dashboard-panel" style={{ "--action-color": presentation.color } as CSSProperties}>
      <CardHeader className="dashboard-panel-header">
        <CardTitle className="flex items-center gap-2 text-sm"><Bot size={17} aria-hidden="true" />Manager Decision</CardTitle>
        <Badge variant={safetyPassed ? "success" : "danger"}>Safety {safetyPassed ? "PASSED" : "BLOCKED"}</Badge>
      </CardHeader>
      <CardContent className="dashboard-panel-content">
        <div className="decision-result">
          <strong><Icon size={25} aria-hidden="true" />{decision.action}</strong>
          <span aria-label="Observed angle to decision target">{formatAngle(currentAngle)} <ArrowRight size={16} aria-hidden="true" /> {formatAngle(decision.target_angle_deg)}</span>
        </div>
        <p className="decision-reason">{decision.reason}</p>
        <p className="dashboard-note">Proposed action · execution is not confirmed.</p>
      </CardContent>
    </Card>
  );
}
