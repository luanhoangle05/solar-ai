import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function OptimizationPanel({ title, icon: Icon, className = "", meta, children }: {
  title: string; icon: LucideIcon; className?: string; meta?: ReactNode; children: ReactNode;
}) {
  return <Card className={`opt-panel ${className}`}>
    <CardHeader className="opt-panel-header">
      <CardTitle><Icon size={18} aria-hidden="true" />{title}</CardTitle>{meta}
    </CardHeader>
    <CardContent className="opt-panel-content">{children}</CardContent>
  </Card>;
}
