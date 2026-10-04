import type { ComponentProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
export const buttonVariants = cva("inline-flex shrink-0 items-center justify-center gap-2 rounded-md border text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50", { variants: {
  variant: { primary: "border-primary bg-primary text-primary-foreground hover:bg-primary/85", secondary: "border-border bg-secondary text-foreground hover:bg-accent", danger: "border-danger bg-danger text-primary-foreground hover:bg-danger/85" },
  size: { default: "h-9 px-3", icon: "size-9" },
}, defaultVariants: { variant: "primary", size: "default" } });
export function Button({ className, variant, size, type = "button", ...props }: ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return <button type={type} className={cn(buttonVariants({variant,size}),className)} {...props} />;
}
