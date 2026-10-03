import { BrainCircuit } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { formatMetric, formatModelName } from "@/lib/formatters";
import type { ModelMetrics } from "@/types/solar";

export function SelectedModelSummary({ model }: { model: ModelMetrics | null }) {
  return (
    <DashboardPanel title="Selected Prediction Model" icon={BrainCircuit} className="dashboard-model" action={model && <Badge variant={model.status === "MOCK" ? "warning" : model.status === "VALIDATED" ? "success" : "secondary"}>{model.status}</Badge>}>
      {model ? <>
        <p className="text-xl font-semibold">{formatModelName(model.model)}</p>
        <p className="mt-1 text-xs text-muted-foreground">Implementation: {model.implementation || "Unavailable"}</p>
        <dl className="model-metrics">
          <div><dt><abbr title="Mean absolute error">MAE</abbr></dt><dd>{formatMetric(model.mae)}</dd></div>
          <div><dt><abbr title="Root mean square error">RMSE</abbr></dt><dd>{formatMetric(model.rmse)}</dd></div>
          <div><dt><abbr title="Coefficient of determination">R²</abbr></dt><dd>{formatMetric(model.r2)}</dd></div>
        </dl>
        <p className="dashboard-note">{model.status === "MOCK" ? "Synthetic fixture metrics · not real-world model accuracy." : "Model status and metrics are supplied by the backend contract."}</p>
      </> : <p className="dashboard-empty">Model unavailable. No model selected.</p>}
    </DashboardPanel>
  );
}
