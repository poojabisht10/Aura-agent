import axios from 'axios';
import type {
  ProjectCreateRequest,
  ProjectResponse,
  ProjectStatusResponse,
  ProjectsListResponse,
  ComponentsListResponse,
  Stats,
  DeploymentStatus,
  VerificationReport,
} from '@/types';

const API_BASE_URL = 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Projects API
export const projectsApi = {
  list: async (skip = 0, limit = 100): Promise<ProjectsListResponse> => {
    const response = await apiClient.get<ProjectsListResponse>('/api/projects', {
      params: { skip, limit },
    });
    return response.data;
  },

  create: async (data: ProjectCreateRequest): Promise<ProjectResponse> => {
    const response = await apiClient.post<ProjectResponse>('/api/projects/create', data);
    return response.data;
  },

  addWebsite: async (data: ProjectCreateRequest): Promise<ProjectResponse> => {
    const response = await apiClient.post<ProjectResponse>('/api/projects/add-website', data);
    return response.data;
  },

  getStatus: async (projectId: number): Promise<ProjectStatusResponse> => {
    const response = await apiClient.get<ProjectStatusResponse>(
      `/api/projects/${projectId}/status`
    );
    return response.data;
  },

  delete: async (projectId: number): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/api/projects/${projectId}`);
    return response.data;
  },

  getPreviewUrl: async (projectId: number): Promise<{ preview_url: string | null; type: string; needs_build?: boolean; message?: string }> => {
    const response = await apiClient.get(`/api/projects/${projectId}/preview-url`);
    return response.data;
  },

  build: async (projectId: number): Promise<{ message: string; project_id: number; project_name: string }> => {
    const response = await apiClient.post(`/api/projects/${projectId}/build`);
    return response.data;
  },

  // Deployment APIs
  getDeploymentStatus: async (projectId: number): Promise<DeploymentStatus> => {
    const response = await apiClient.get<DeploymentStatus>(
      `/api/projects/${projectId}/deployment-status`
    );
    return response.data;
  },

  pushToGitHub: async (projectId: number): Promise<{ message: string; project_id: number }> => {
    const response = await apiClient.post(`/api/projects/${projectId}/push-to-github`);
    return response.data;
  },

  deployToVercel: async (projectId: number): Promise<{ message: string; project_id: number }> => {
    const response = await apiClient.post(`/api/projects/${projectId}/deploy-to-vercel`);
    return response.data;
  },

  getFigmaJson: async (projectId: number): Promise<any> => {
    const response = await apiClient.get(`/api/projects/${projectId}/figma-json`);
    return response.data;
  },

  getFigmaJsonRaw: async (projectId: number): Promise<any> => {
    const response = await apiClient.get(`/api/projects/${projectId}/figma-json/raw`);
    return response.data;
  },

  getTrace: async (projectId: number): Promise<any> => {
    const response = await apiClient.get(`/api/projects/${projectId}/trace`);
    return response.data;
  },

  getVerificationReport: async (projectId: number): Promise<VerificationReport> => {
    const response = await apiClient.get<VerificationReport>(
      `/api/projects/${projectId}/verification-report`
    );
    return response.data;
  },

  getScreenshotUrl: (projectId: number, filename: string): string => {
    return `${API_BASE_URL}/api/projects/${projectId}/screenshots/${filename}`;
  },
};

// Components API
export const componentsApi = {
  list: async (category?: string, limit = 100): Promise<ComponentsListResponse> => {
    const response = await apiClient.get<ComponentsListResponse>('/api/components', {
      params: { category, limit },
    });
    return response.data;
  },
};

// Stats API
export const statsApi = {
  get: async (): Promise<Stats> => {
    const response = await apiClient.get<Stats>('/api/stats');
    return response.data;
  },
};

export default apiClient;
