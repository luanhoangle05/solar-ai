import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function FarmPanel({ title, icon: Icon, className = "", meta, children }: {
  title: string; icon: LucideIcon; className?: string; meta?: ReactNode; children: ReactNode;
}) {
  return <Card className={`fx-panel ${className}`}><CardHeader className="fx-panel-heading"><CardTitle><Icon size={18} aria-hidden="true"/>{title}</CardTitle>{meta}</CardHeader><CardContent className="fx-panel-body">{children}</CardContent></Card>;
}
