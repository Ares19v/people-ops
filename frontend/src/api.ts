import axios from 'axios';
import {
  User,
  UserRole,
  LeaveBalanceSummary,
  LeaveApplication,
  Project,
  TimesheetEntry,
  TimesheetReportSummary,
  AgentChatResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // Auth
  mockLogin: async (role: UserRole) => {
    const res = await apiClient.post<{ access_token: string; role: UserRole; full_name: string }>('/auth/mock-login', { role });
    localStorage.setItem('token', res.data.access_token);
    localStorage.setItem('user_role', res.data.role);
    return res.data;
  },
  getCurrentUser: async () => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_role');
  },

  // Leaves
  getLeaveBalances: async (userId?: string) => {
    const res = await apiClient.get<LeaveBalanceSummary>('/leaves/balances', {
      params: userId ? { user_id: userId } : {},
    });
    return res.data;
  },
  applyLeave: async (payload: { leave_type: string; start_date: string; end_date: string; reason: string }) => {
    const res = await apiClient.post<LeaveApplication>('/leaves/apply', payload);
    return res.data;
  },
  getLeaveApplications: async (statusFilter?: string, allEmployees = false) => {
    const res = await apiClient.get<LeaveApplication[]>('/leaves/applications', {
      params: {
        ...(statusFilter ? { status_filter: statusFilter } : {}),
        all_employees: allEmployees,
      },
    });
    return res.data;
  },
  decideLeave: async (applicationId: string, decision: 'APPROVE' | 'REJECT', comments?: string) => {
    const res = await apiClient.post<LeaveApplication>(`/leaves/${applicationId}/decide`, {
      decision,
      comments,
    });
    return res.data;
  },

  // Timesheets
  getProjects: async () => {
    const res = await apiClient.get<Project[]>('/timesheets/projects');
    return res.data;
  },
  logTimesheet: async (payload: { project_id: string; task_name: string; entry_date: string; hours: number; is_billable: boolean; notes?: string }) => {
    const res = await apiClient.post<TimesheetEntry>('/timesheets/entry', payload);
    return res.data;
  },
  getTimesheetReport: async (filters?: Record<string, any>) => {
    const res = await apiClient.get<TimesheetReportSummary>('/reports/timesheets', { params: filters });
    return res.data;
  },
  getTimesheetCSVUrl: (filters?: Record<string, any>) => {
    const params = new URLSearchParams(filters).toString();
    return `${API_BASE_URL}/reports/timesheets/csv?${params}`;
  },

  // Policy Graph RAG
  searchPolicies: async (query: string) => {
    const res = await apiClient.get('/policy/search', { params: { q: query } });
    return res.data;
  },

  // Multi-Agent Chat
  chatWithAgent: async (message: string, sessionId?: string, targetAgent?: string) => {
    const res = await apiClient.post<AgentChatResponse>('/agents/chat', {
      message,
      session_id: sessionId,
      target_agent: targetAgent,
    });
    return res.data;
  },

  // Onboarding
  initiateOnboarding: async (payload: any) => {
    const res = await apiClient.post('/onboarding/initiate', payload);
    return res.data;
  },
  uploadDocument: async (userId: string, docType: string, file: File) => {
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('doc_type', docType);
    formData.append('file', file);
    const res = await apiClient.post('/onboarding/upload-document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  extractResume: async (documentId: string) => {
    const res = await apiClient.post(`/onboarding/extract-resume/${documentId}`);
    return res.data;
  },
  confirmOnboarding: async (payload: any) => {
    const res = await apiClient.post('/onboarding/confirm', payload);
    return res.data;
  },
};
