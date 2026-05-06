export const API_BASE_URL = "http://localhost:8000"

export const PROJECT_STATUSES = {
  pending: "Pending",
  generating: "Generating",
  success: "Success",
  completed_with_errors: "Completed with Errors",
  failed: "Failed",
} as const

export const UI_LIBRARIES = [
  { value: "tailwind", label: "Tailwind CSS" },
  { value: "mui", label: "Material-UI" },
  { value: "chakra", label: "Chakra UI" },
] as const
