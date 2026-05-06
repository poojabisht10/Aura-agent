export interface Project {
  id: number;
  name: string;
  figma_url: string;
  status: 'pending' | 'generating' | 'success' | 'completed_with_errors' | 'completed_with_warnings' | 'failed';
  project_path: string | null;
  components_generated: number;
  components_reused: number;
  conversion_time_seconds: number | null;
  created_at: string;
  updated_at?: string;
  error_message: string | null;
  // Multi-page support
  parent_project_id?: number | null;
  is_page?: boolean;
  route_path?: string | null;
  // GitHub integration
  github_repo_url?: string | null;
  github_pushed?: boolean;
  github_branch?: string | null;
  github_pr_url?: string | null;
  // Vercel deployment
  deployment_status?: 'not_deployed' | 'deploying' | 'deployed' | 'failed';
  deployment_url?: string | null;
  deployment_error?: string | null;
  last_deployed_at?: string | null;
  // Visual verification
  visual_match?: boolean;
  verification_confidence?: number;
  verification_iterations?: number;
}

// ---------------------------------------------------------------------------
// Verification Report types
// ---------------------------------------------------------------------------

export interface VerificationScores {
  dimension?: number;
  color?: number;
  spacing?: number;
  typography?: number;
  effects?: number;
  pixel?: number;
  structural?: number;
  element_dimensions?: number;
  [key: string]: number | undefined;
}

export interface PerElementResult {
  figma_id: string;
  name: string;
  accuracy: number;
  dom_screenshot?: string;
  width_match?: boolean;
  height_match?: boolean;
  pixel_comparison?: {
    pixel_match_ratio: number;
    dimension_match: boolean;
    method: string;
  };
}

export interface VerificationIteration {
  iteration: number;
  confidence: number;
  method: string;
  accuracy_scores: Record<string, number>;
  discrepancies: any[];
  fixes_applied?: number;
}

export interface VerificationReport {
  timestamp: string;
  project_name: string;
  overall_confidence: number;
  status: 'success' | 'completed_with_warnings' | 'needs_review' | 'failed';
  method: string;
  iterations: number;
  scores: VerificationScores;
  element_comparison: {
    element_count: number;
    overall_dimension_accuracy: number;
    overall_pixel_accuracy?: number | null;
  };
  per_element_results: PerElementResult[];
  discrepancies: any[];
  iteration_history: VerificationIteration[];
}

export interface DeploymentStatus {
  project_id: number;
  project_name: string;
  // GitHub
  github_pushed: boolean;
  github_repo_url: string | null;
  github_branch: string | null;
  github_pr_url: string | null;
  // Vercel
  deployment_status: 'not_deployed' | 'deploying' | 'deployed' | 'failed';
  deployment_url: string | null;
  deployment_error: string | null;
  last_deployed_at: string | null;
  vercel_project_id: string | null;
}

export interface ProjectListItem {
  id: number;
  name: string;
  status: string;
  components_generated: number;
  components_reused: number;
  created_at: string;
  // Multi-page support
  parent_project_id?: number | null;
  is_page?: boolean;
  route_path?: string | null;
  // GitHub integration
  github_pushed?: boolean;
  github_repo_url?: string | null;
  // Vercel deployment
  deployment_status?: 'not_deployed' | 'deploying' | 'deployed' | 'failed';
  deployment_url?: string | null;
}

export interface ProjectStatusResponse extends Project {}

export interface ProjectCreateRequest {
  figma_url: string;
  project_name: string;
  ui_library?: 'tailwind' | 'mui' | 'chakra' | 'css-modules';
  add_as?: 'new_project' | 'new_page';
  parent_project_id?: number | null;
}

export interface ProjectResponse {
  project_id: string;
  status: string;
  message: string;
}

export interface Component {
  id: string;
  name: string;
  category: string;
  code: string;
  description: string;
  created_at?: string;
  usage_count?: number;
  metadata?: Record<string, any>;
}

export interface Stats {
  total_projects: number;
  completed_projects: number;
  total_components: number;
  total_component_reuses: number;
}

export interface ProjectsListResponse {
  projects: ProjectListItem[];
  total: number;
}

export interface ComponentsListResponse {
  components: Component[];
  total: number;
}
