import { useQuery } from "@tanstack/react-query"
import { projectsApi } from "@/api/client"
import type { ProjectStatusResponse } from "@/types"

export function useProjectStatus(projectId: number | null, enabled = true) {
  return useQuery({
    queryKey: ["project-status", projectId],
    queryFn: () => projectsApi.getStatus(projectId!),
    enabled: enabled && projectId !== null,
    refetchInterval: (query) => {
      // Stop polling on error to avoid hammering a dead server
      if (query.state.status === "error") return false
      const data = query.state.data as ProjectStatusResponse | undefined
      // Poll every 5 seconds if project is pending or generating
      if (data?.status === "pending" || data?.status === "generating") {
        return 5000
      }
      // Stop polling for other statuses
      return false
    },
  })
}
