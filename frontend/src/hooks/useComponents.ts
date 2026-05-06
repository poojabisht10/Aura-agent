import { useQuery } from "@tanstack/react-query"
import { componentsApi } from "@/api/client"

export function useComponents(category?: string, limit = 100) {
  return useQuery({
    queryKey: ["components", category, limit],
    queryFn: () => componentsApi.list(category, limit),
  })
}
