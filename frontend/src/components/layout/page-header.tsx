import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
export function PageHeader({ icon: Icon, title, description, actions }: { icon: LucideIcon; title: string; description: string; actions?: ReactNode }) {
  return <header className="page-header"><div className="flex min-w-0 items-start gap-3"><span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary"><Icon size={22} aria-hidden="true" /></span><div className="min-w-0"><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-muted-foreground">{description}</p></div></div>{actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}</header>;
}
