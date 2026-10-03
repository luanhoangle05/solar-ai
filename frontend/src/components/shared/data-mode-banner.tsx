import { FlaskConical } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Metadata } from "@/types/solar";

interface DataModeBannerProps {
  metadata: Metadata;
}

export function DataModeBanner({ metadata }: DataModeBannerProps) {
  const isMock = metadata.dataset_kind === "MOCK";

  return (
    <div
      className="flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      role="status"
    >
      <div className="flex items-start gap-3">
        <FlaskConical
          className="mt-0.5 size-5 shrink-0 text-warning"
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-semibold text-foreground">
            {isMock ? "MOCK DEVELOPMENT DATA" : "LIVE DATA"}
          </p>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
            {isMock
              ? "Synthetic fixture for frontend development. Values are not measurements, trained-model performance, or hardware authorization."
              : "Payload is labeled LIVE by the shared contract."}
          </p>
        </div>
      </div>

      <Badge variant={isMock ? "warning" : "success"}>
        {metadata.dataset_kind}
      </Badge>
    </div>
  );
}
