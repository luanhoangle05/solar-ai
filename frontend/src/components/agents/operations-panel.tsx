import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function OperationsPanel({ title, icon: Icon, className = "", meta, children }: {
  title: string; icon: LucideIcon; className?: string; meta?: ReactNode; children: ReactNode;
}) {
  return <Card className={`ops-panel ${className}`}><CardHeader className="ops-panel-heading"><CardTitle><Icon size={18} aria-hidden="true"/>{title}</CardTitle>{meta}</CardHeader><CardContent className="ops-panel-body">{children}</CardContent></Card>;
}
