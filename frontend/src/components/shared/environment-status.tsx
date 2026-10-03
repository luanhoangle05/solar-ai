import { Badge } from "@/components/ui/badge";
import { dataStatusVariants } from "@/config/status";
import type { FrontendData } from "@/types/solar";
export function EnvironmentStatus({ data }: { data?: FrontendData }) {
  if (!data) return <Badge variant="danger">DATA UNAVAILABLE</Badge>;
  return <div className="environment-status" aria-label="Data environment"><Badge variant={data.metadata.dataset_kind === "MOCK" ? "warning" : "secondary"}>{data.metadata.dataset_kind} DATA</Badge><Badge variant={dataStatusVariants[data.data_agent.status]}>{data.data_agent.status}</Badge><span className="schema-version">v{data.metadata.schema_version}</span></div>;
}
