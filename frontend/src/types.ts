export type UserRole = 'EMPLOYEE' | 'HR_ASSOCIATE' | 'HR_MANAGER' | 'ADMIN';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department: string;
  designation: string;
  manager_id?: string;
  is_active: boolean;
}

export interface LeaveBalanceItem {
  leave_type: 'EL' | 'CL' | 'SL' | 'LWP';
  total_allocated: number;
  used_days: number;
  pending_days: number;
  carry_forwarded: number;
  available_balance: number;
}

export interface LeaveBalanceSummary {
  user_id: string;
  year: number;
  balances: LeaveBalanceItem[];
}

export interface LeaveApplication {
  id: string;
  user_id: string;
  employee_name?: string;
  leave_type: 'EL' | 'CL' | 'SL' | 'LWP';
  start_date: string;
  end_date: string;
  total_days: number;
  reason: string;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  approver_id?: string;
  approver_name?: string;
  approver_comments?: string;
  applied_at: string;
  decided_at?: string;
}

export interface Project {
  id: string;
  name: string;
  code: string;
  client_name: string;
  is_active: boolean;
}

export interface TimesheetEntry {
  id: string;
  user_id: string;
  employee_name?: string;
  project_id: string;
  project_name?: string;
  task_name: string;
  entry_date: string;
  hours: number;
  is_billable: boolean;
  notes?: string;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED';
  approver_id?: string;
  rejection_reason?: string;
  created_at: string;
}

export interface TimesheetReportSummary {
  total_hours: number;
  billable_hours: number;
  non_billable_hours: number;
  entry_count: number;
  entries: TimesheetEntry[];
}

export interface CitationItem {
  source_title: string;
  section: string;
  document_type: string;
  citation_text: string;
  confidence_score: number;
}

export interface StructuredAction {
  action_type: string;
  action_payload: Record<string, any>;
  requires_confirmation: boolean;
  executed: boolean;
  result_message?: string;
}

export interface AgentChatResponse {
  response: string;
  agent_routed: string;
  guardrail_status: string;
  guardrail_tripped?: string;
  citations: CitationItem[];
  structured_action?: StructuredAction;
  session_id: string;
  latency_ms: number;
  token_usage: Record<string, number>;
}
