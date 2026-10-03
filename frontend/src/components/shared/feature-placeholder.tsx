import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowLeft, Construction } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
export function FeaturePlaceholder({ icon, title, description, planned, children }: { icon: LucideIcon; title: string; description: string; planned: string; children?: React.ReactNode }) {
  return <div className="space-y-4"><PageHeader icon={icon} title={title} description={description} /><Card><CardHeader className="flex-row items-center justify-between gap-3 border-b border-border"><CardTitle className="flex items-center gap-2"><Construction size={18} className="text-primary" aria-hidden="true" />{title} workspace</CardTitle><Badge variant="secondary">Planned</Badge></CardHeader><CardContent className="space-y-3 pt-4"><p className="text-sm font-medium">This functionality is not implemented yet.</p><p className="text-sm text-muted-foreground">{planned}</p><Link href="/" className={buttonVariants({variant:"secondary"})}><ArrowLeft size={16} aria-hidden="true" />View contract snapshot</Link></CardContent></Card>{children}</div>;
}
