import Link from "next/link";
import { Sun } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return <main id="main-content" className="grid min-h-dvh place-items-center p-5">
    <section className="w-full max-w-md space-y-4 rounded-xl border border-border bg-card p-6">
      <p className="flex items-center gap-2 font-semibold"><Sun className="text-warning" aria-hidden="true"/>SolarAI · 404</p>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">This address does not match a SolarAI workspace.</p>
      <Link href="/" className={buttonVariants({ variant: "secondary" })}>Return to Dashboard</Link>
    </section>
  </main>;
}
