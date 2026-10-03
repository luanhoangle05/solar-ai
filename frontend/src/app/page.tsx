import {
  CheckCircle2,
  Database,
  Layers3,
  SunMedium,
} from "lucide-react";

import { StatusBadge } from "@/components/shared/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const foundationItems = [
  {
    icon: Layers3,
    title: "Architecture",
    value: "Next.js + React + TypeScript",
    description: "Strict, component-driven frontend foundation.",
  },
  {
    icon: Database,
    title: "Data Integration",
    value: "Phase 1",
    description: "Shared mock contract integration comes next.",
  },
  {
    icon: CheckCircle2,
    title: "Frontend Status",
    value: "Ready",
    description: "Foundation initialized and ready for feature work.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground sm:px-10 lg:px-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10">
        <header className="flex flex-col gap-6 border-b border-border pb-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex size-12 items-center justify-center rounded-xl border border-primary/30 bg-primary/10">
              <SunMedium className="size-7 text-warning" aria-hidden="true" />
            </div>

            <div>
              <h1 className="text-3xl font-semibold tracking-tight">SolarAI</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                AI-Powered Solar Farm Optimization
              </p>
            </div>
          </div>

          <StatusBadge status="ready">Frontend Ready</StatusBadge>
        </header>

        <section className="grid gap-5 md:grid-cols-3">
          {foundationItems.map((item) => {
            const Icon = item.icon;

            return (
              <Card key={item.title}>
                <CardHeader>
                  <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/10">
                    <Icon className="size-5 text-primary" aria-hidden="true" />
                  </div>
                  <CardDescription>{item.title}</CardDescription>
                  <CardTitle className="text-xl">{item.value}</CardTitle>
                </CardHeader>

                <CardContent>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {item.description}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </section>

        <Card className="border-primary/20">
          <CardHeader>
            <CardDescription>Phase 0</CardDescription>
            <CardTitle>Frontend foundation initialized successfully.</CardTitle>
          </CardHeader>

          <CardContent>
            <p className="max-w-3xl text-sm leading-7 text-muted-foreground">
              This phase establishes the SolarAI frontend architecture, design
              tokens, reusable UI primitives, and development tooling. Real
              SolarAI mock-contract integration begins in Phase 1.
            </p>
          </CardContent>
        </Card>

        <footer className="border-t border-border pt-6 text-xs text-muted-foreground">
          No mock business values, backend calls, or optimization calculations
          are implemented in Phase 0.
        </footer>
      </div>
    </main>
  );
}
