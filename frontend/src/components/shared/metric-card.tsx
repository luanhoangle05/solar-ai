import type { LucideIcon } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  icon: LucideIcon;
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: MetricCardProps) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <CardDescription>{label}</CardDescription>

          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10">
            <Icon className="size-4 text-primary" aria-hidden="true" />
          </div>
        </div>
        <CardTitle className="mt-1 text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>

      {detail ? (
        <CardContent>
          <p className="text-xs leading-5 text-muted-foreground">
            {detail}
          </p>
        </CardContent>
      ) : null}
    </Card>
  );
}
