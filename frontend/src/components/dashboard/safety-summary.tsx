import { CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { formatDisplayName } from "@/lib/formatters";
import type { SafetyResult } from "@/types/solar";

export function SafetySummary({ safety }: { safety: SafetyResult }) {
  return (
    <DashboardPanel title="Safety Validation" icon={ShieldCheck} className="dashboard-safety" action={<Badge variant={safety.passed ? "success" : "danger"}>{safety.passed ? "PASSED" : "BLOCKED"}</Badge>}>
      <p className="safety-count">{safety.checks.length} checks · {safety.checks.filter(check => !check.passed).length} failed</p>
      <ul className="safety-checks">
        {safety.checks.map((check, index) => {
          const Icon = check.passed ? CheckCircle2 : XCircle;
          const color = check.passed ? "text-success" : check.severity === "SEVERE" ? "text-danger" : "text-warning";
          return <li key={check.name + index}>
            <div><Icon size={15} className={color} aria-hidden="true" /><span>{formatDisplayName(check.name)}</span><strong className={color}>{check.passed ? "Passed" : "Failed"}</strong></div>
            {!check.passed && <p className={color}>{formatDisplayName(check.severity)} · {check.reason}</p>}
          </li>;
        })}
      </ul>
      <p className="dashboard-note mt-3">{safety.reason}</p>
    </DashboardPanel>
  );
}
