import { Badge } from "@/components/ui/badge";

type Status = "ready" | "pending" | "warning" | "error";

interface StatusBadgeProps {
  status: Status;
  children: React.ReactNode;
}

const variants = {
  ready: "success",
  pending: "secondary",
  warning: "warning",
  error: "danger",
} as const;

export function StatusBadge({ status, children }: StatusBadgeProps) {
  return <Badge variant={variants[status]}>{children}</Badge>;
}
