import Link from "next/link";
import { Settings, Sun } from "lucide-react";
import type { FrontendData } from "@/types/solar";
import { EnvironmentStatus } from "@/components/shared/environment-status";
import { buttonVariants } from "@/components/ui/button";
import { PrimaryNav } from "./primary-nav";
import { MobileNav } from "./mobile-nav";
export function TopHeader({ data }: { data?: FrontendData }) {
  return <header className="top-header"><MobileNav /><Link href="/" className="brand" aria-label="SolarAI home"><Sun className="brand-icon" aria-hidden="true" /><span><strong>SolarAI</strong><small>Optimize Today, Generate Tomorrow</small></span></Link><PrimaryNav /><div className="header-context"><EnvironmentStatus data={data} /><Link href="/settings" aria-label="Settings" className={buttonVariants({variant:"secondary",size:"icon"})}><Settings size={17} aria-hidden="true" /></Link></div></header>;
}
