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
  UserChatSession,
  ActiveMemoryWindowResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

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
  login: async (email: string, password: string) => {
    const res = await apiClient.post<{ access_token: string; role: UserRole; full_name: string; permissions: string[] }>('/auth/login', { email, password });
    localStorage.setItem('token', res.data.access_token);
    localStorage.setItem('user_role', res.data.role);
    return res.data;
  },
  mockLogin: async (role: UserRole, email?: string) => {
    const res = await apiClient.post<{ access_token: string; role: UserRole; full_name: string; permissions: string[] }>('/auth/mock-login', { role, email });
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
  getPrompts: async () => {
    const res = await apiClient.get('/agents/prompts');
    return res.data;
  },
  getSinglePrompt: async (promptKey: string) => {
    const res = await apiClient.get(`/agents/prompts/${promptKey}`);
    return res.data;
  },
  syncPromptsToCloud: async () => {
    const res = await apiClient.post('/agents/prompts/sync-cloud');
    return res.data;
  },
  syncSinglePromptToCloud: async (promptKey: string) => {
    const res = await apiClient.post(`/agents/prompts/${promptKey}/sync-cloud`);
    return res.data;
  },
  updatePrompt: async (promptKey: string, template: string, label = 'live') => {
    const res = await apiClient.put(`/agents/prompts/${promptKey}`, { template, label });
    return res.data;
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
  decideTimesheets: async (entryIds: string[], decision: 'APPROVE' | 'REJECT', rejectionReason?: string) => {
    const res = await apiClient.post<TimesheetEntry[]>('/timesheets/decide', {
      entry_ids: entryIds,
      decision,
      rejection_reason: rejectionReason,
    });
    return res.data;
  },
  getTimesheetCSVUrl: (filters?: Record<string, any>) => {
    const params = new URLSearchParams(filters).toString();
    return `${API_BASE_URL}/reports/timesheets/csv?${params}`;
  },
  downloadTimesheetCSV: async (filters?: Record<string, any>) => {
    const res = await apiClient.get('/reports/timesheets/csv', {
      params: filters,
      responseType: 'blob',
    });
    const blob = new Blob([res.data], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timesheets_export_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },

  // Policy RAG
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
  getChatMemory: async (sessionId: string) => {
    const res = await apiClient.get<{
      session_id: string;
      turns_count: number;
      history: Array<{ role: string; content: string }>;
      entities: Record<string, any>;
    }>(`/agents/memory/${sessionId}`);
    return res.data;
  },
  clearChatMemory: async (sessionId: string) => {
    const res = await apiClient.delete(`/agents/memory/${sessionId}`);
    return res.data;
  },
  getUserSessions: async () => {
    const res = await apiClient.get<{ user_id: string; sessions_count: number; sessions: UserChatSession[] }>('/agents/sessions');
    return res.data;
  },
  getSessionTurns: async (sessionId: string) => {
    const res = await apiClient.get<{
      session_id: string;
      title: string;
      user_id: string;
      created_at: string;
      turns_count: number;
      messages: Array<{
        id: string;
        role: string;
        content: string;
        metadata: Record<string, any>;
        created_at: string;
      }>;
    }>(`/agents/sessions/${sessionId}`);
    return res.data;
  },
  deleteSession: async (sessionId: string) => {
    const res = await apiClient.delete<{ status: string; session_id: string }>(`/agents/sessions/${sessionId}`);
    return res.data;
  },
  purgeUserChatHistory: async () => {
    const res = await apiClient.delete<{ status: string; purged_sessions_count: number }>('/agents/sessions/purge-history');
    return res.data;
  },
  getActiveMemoryWindow: async (sessionId?: string) => {
    const res = await apiClient.get<ActiveMemoryWindowResponse>('/agents/memory/window/active', {
      params: sessionId ? { session_id: sessionId } : {},
    });
    return res.data;
  },
  summarizeSession: async (sessionId: string) => {
    const res = await apiClient.post<{ status: string; summary: any }>(`/agents/sessions/${sessionId}/summarize`);
    return res.data;
  },

  // Zoho People HRMS Integration
  getZohoStatus: async () => {
    const res = await apiClient.get('/agents/zoho/status');
    return res.data;
  },
  syncZohoAttendance: async (date: string, hours: number) => {
    const res = await apiClient.post('/agents/zoho/sync-attendance', { date, hours });
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

  // Database Inspector & SQL Views
  getDatabaseViews: async () => {
    const res = await apiClient.get<Array<{
      key: string;
      title: string;
      description: string;
      icon: string;
      category: string;
      rowCount: number;
    }>>('/reports/db-inspector/views');
    return res.data;
  },
  getDatabaseViewData: async (viewName: string, search?: string, limit?: number) => {
    const res = await apiClient.get<{
      view_name: string;
      meta: { title: string; description: string; category: string; icon: string };
      columns: string[];
      rows: Array<Record<string, any>>;
      total_returned: number;
    }>(`/reports/db-inspector/view/${viewName}`, {
      params: { search, limit: limit || 100 }
    });
    return res.data;
  },
};
