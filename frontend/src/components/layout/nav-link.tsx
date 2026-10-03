"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentProps } from "react";
import { isActiveRoute } from "@/config/navigation";
import { cn } from "@/lib/utils";
export function NavLink({ href, className, ...props }: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const active = isActiveRoute(usePathname(), href);
  return <Link href={href} aria-current={active ? "page" : undefined} className={cn("nav-link", className)} {...props} />;
}
