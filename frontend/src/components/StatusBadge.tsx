import { Badge } from "@/components/ui/badge"
import type { Project } from "@/types"

interface StatusBadgeProps {
  status: Project["status"]
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const variants: Record<Project["status"], "default" | "secondary" | "success" | "destructive" | "warning"> = {
    pending: "secondary",
    generating: "default",
    success: "success",
    completed_with_errors: "warning",
    completed_with_warnings: "warning",
    failed: "destructive",
  }

  const labels: Record<Project["status"], string> = {
    pending: "Pending",
    generating: "Generating",
    success: "Success",
    completed_with_errors: "Completed with Errors",
    completed_with_warnings: "Completed with Warnings",
    failed: "Failed",
  }

  return (
    <Badge variant={variants[status]}>
      {labels[status]}
    </Badge>
  )
}
