import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { projectsApi } from "@/api/client"
import { useToast } from "@/components/ui/toast"
import type { ProjectCreateRequest } from "@/types"

export function useProjects(skip = 0, limit = 100) {
  return useQuery({
    queryKey: ["projects", skip, limit],
    queryFn: () => projectsApi.list(skip, limit),
    refetchInterval: 10000, // Refetch every 10 seconds
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  return useMutation({
    mutationFn: ({ data, isNewProject }: { data: ProjectCreateRequest; isNewProject: boolean }) =>
      isNewProject ? projectsApi.create(data) : projectsApi.addWebsite(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["stats"] })
      addToast({
        title: "Project created",
        description: response.message,
        variant: "success",
      })
    },
    onError: (error: any) => {
      addToast({
        title: "Failed to create project",
        description: error.response?.data?.detail || "An error occurred",
        variant: "destructive",
      })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  return useMutation({
    mutationFn: (projectId: number) => projectsApi.delete(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["stats"] })
      addToast({
        title: "Project deleted",
        description: "The project has been successfully deleted",
        variant: "success",
      })
    },
    onError: (error: any) => {
      addToast({
        title: "Failed to delete project",
        description: error.response?.data?.detail || "An error occurred",
        variant: "destructive",
      })
    },
  })
}
