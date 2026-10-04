import { ChartNoAxesCombined, CloudSun, LayoutDashboard, Settings, SlidersHorizontal, Target } from "lucide-react";
export const navigation = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard, primary: true },
  { label: "Simulation", href: "/simulation", icon: SlidersHorizontal, primary: true },
  { label: "Optimization", href: "/optimization", icon: Target, primary: true },
  { label: "Weather", href: "/weather", icon: CloudSun, primary: false },
  { label: "Analytics", href: "/analytics", icon: ChartNoAxesCombined, primary: true },
  { label: "Settings", href: "/settings", icon: Settings, primary: false },
] as const;
export function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
}
