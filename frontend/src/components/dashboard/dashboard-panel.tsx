import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface DashboardPanelProps {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function DashboardPanel({ title, icon: Icon, children, action, className }: DashboardPanelProps) {
  return (
    <Card className={cn("dashboard-panel", className)}>
      <CardHeader className="dashboard-panel-header">
        <CardTitle className="flex min-w-0 items-center gap-2 text-sm">
          <Icon size={17} className="shrink-0 text-primary" aria-hidden="true" />
          {title}
        </CardTitle>
        {action}
      </CardHeader>
      <CardContent className="dashboard-panel-content">{children}</CardContent>
    </Card>
  );
}
