import { AlertTriangle } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatDisplayName } from "@/lib/formatters";
import type { RunError } from "@/types/solar";

export function SystemIssues({ errors }: { errors: RunError[] }) {
  if (!errors.length) return null;
  return <div role="alert" className="dashboard-issues"><DashboardPanel title={"System Issues · " + errors.length} icon={AlertTriangle}>
    <ul className="space-y-2 text-sm">{errors.map((error, index) => <li key={error.code + index}><strong>{formatDisplayName(error.agent)} · {error.code}</strong><p className="text-muted-foreground">{error.message}</p></li>)}</ul>
  </DashboardPanel></div>;
}
