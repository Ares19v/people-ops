import React from 'react';
import { User, UserRole, LeaveBalanceSummary } from '../types';
import {
  Calendar, Clock, Shield, Sparkles, UserPlus, CheckCircle2,
  TrendingUp, ArrowUpRight, Award, AlertCircle, Cpu, Bot
} from 'lucide-react';
import { AgentFlowCircuit } from '../components/AgentFlowCircuit';

interface DashboardProps {
  currentUser: User | null;
  currentRole: UserRole;
  balances: LeaveBalanceSummary | null;
  onNavigate: (tab: string, options?: { openApplyModal?: boolean; openLogModal?: boolean }) => void;
  openChat: (prompt?: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  currentUser,
  currentRole,
  balances,
  onNavigate,
  openChat,
}) => {
  const el = balances?.balances.find((b) => b.leave_type === 'EL')?.available_balance ?? 18;
  const cl = balances?.balances.find((b) => b.leave_type === 'CL')?.available_balance ?? 7;
  const sl = balances?.balances.find((b) => b.leave_type === 'SL')?.available_balance ?? 10;

  return (
    <div className="space-y-8">
      {/* Olixer Hero Presentation Section */}
      <div className="hero-wrapper">
        <div className="pill-announcement">
          <Sparkles className="w-3.5 h-3.5 text-blue-600" />
          <span>Google ADK Multi-Agent Orchestration &bull; NVIDIA NeMo Guardrails</span>
        </div>
        <h1 className="hero-main-title">
          Intelligent People Operations, <br className="hidden sm:inline" />
          <strong>orchestrated by autonomous agents.</strong>
        </h1>
        <p className="hero-subtext">
          Welcome back, <span className="font-semibold text-slate-900">{currentUser?.full_name || 'Team Member'}</span> ({currentRole}).
          Enforcing Maharashtra Shops & Establishments Act 2017 rules, automated leave ledgers, and DPDP-compliant PII redaction.
        </p>

        {/* Hero Quick Action Pills */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button onClick={() => openChat()} className="btn-pill-dark">
            <Bot size={15} />
            <span>Ask HR Assistant</span>
          </button>
          <button onClick={() => onNavigate('leaves', { openApplyModal: true })} className="btn-pill-outline">
            <Calendar size={14} />
            <span>Apply Leave</span>
          </button>
          <button onClick={() => onNavigate('timesheets', { openLogModal: true })} className="btn-pill-outline">
            <Clock size={14} />
            <span>Log Timesheet</span>
          </button>
          <button onClick={() => onNavigate('policy')} className="btn-pill-outline">
            <Shield size={14} />
            <span>Search Policy RAG</span>
          </button>
        </div>
      </div>

      {/* Interactive Multi-Agent Flow Circuit */}
      <AgentFlowCircuit onSelectQuery={(query) => openChat(query)} />

      {/* KPI Metrics Row in Olixer Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Earned Leave */}
        <div
          onClick={() => onNavigate('leaves')}
          className="card-olixer p-5 cursor-pointer hover:border-blue-400 hover:shadow-md transition-all group"
          title="View Leave Ledger"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600 group-hover:text-blue-600 transition-colors">Earned Leave (EL)</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <Calendar className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">{el}</span>
            <span className="text-xs font-medium text-slate-500">days balance</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              Max 45-day carry-over (Sec 18)
            </span>
          </div>
        </div>

        {/* Casual Leave */}
        <div
          onClick={() => onNavigate('leaves')}
          className="card-olixer p-5 cursor-pointer hover:border-emerald-400 hover:shadow-md transition-all group"
          title="View Leave Ledger"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600 group-hover:text-emerald-600 transition-colors">Casual Leave (CL)</span>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
              <Calendar className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">{cl}</span>
            <span className="text-xs font-medium text-slate-500">days balance</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              8 days statutory quota
            </span>
          </div>
        </div>

        {/* Logged Hours */}
        <div
          onClick={() => onNavigate('timesheets')}
          className="card-olixer p-5 cursor-pointer hover:border-amber-400 hover:shadow-md transition-all group"
          title="View Timesheets"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600 group-hover:text-amber-600 transition-colors">Logged Hours (Week)</span>
            <span className="p-2 rounded-xl bg-amber-50 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">40.0</span>
            <span className="text-xs font-medium text-slate-500">hrs logged</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-amber">
              <Clock className="w-3 h-3" />
              48h Weekly Cap (MH Act)
            </span>
          </div>
        </div>

        {/* NeMo Guardrails */}
        <div
          onClick={() => openChat('What NVIDIA NeMo Guardrails are active in this workspace?')}
          className="card-olixer p-5 cursor-pointer hover:border-purple-400 hover:shadow-md transition-all group"
          title="Ask HR AI about Guardrails"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600 group-hover:text-purple-600 transition-colors">NeMo Safety Rails</span>
            <span className="p-2 rounded-xl bg-purple-50 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Shield className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-purple-600">Active</span>
            <span className="text-xs font-medium text-slate-500">Dual-Boundary</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              Colang 2.0 &bull; DPDP Scrubbing
            </span>
          </div>
        </div>
      </div>

      {/* Role Workflows & Architecture Capabilities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Architecture Status Dossier */}
        <div className="card-olixer p-6">
          <h3 className="font-display font-bold text-base text-slate-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-600" />
            Active Sub-Agent Fleet (Google ADK)
          </h3>
          <div className="space-y-3">
            <div className="p-3.5 bg-slate-50/70 border border-slate-100 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-display font-bold text-xs shrink-0">
                ADK
              </div>
              <div>
                <h4 className="font-display font-bold text-xs text-slate-900">Root Orchestrator</h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  Directs conversational queries to Leave, Policy RAG, and Timesheet autonomous agents.
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-slate-50/70 border border-slate-100 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-display font-bold text-xs shrink-0">
                RAG
              </div>
              <div>
                <h4 className="font-display font-bold text-xs text-slate-900">HR Policy Graph RAG</h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  Indexes Maharashtra Shops & Establishments Act 2017 & company bylaws with exact legal citations.
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-slate-50/70 border border-slate-100 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-display font-bold text-xs shrink-0">
                SAFE
              </div>
              <div>
                <h4 className="font-display font-bold text-xs text-slate-900">NVIDIA NeMo Guardrails</h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  Filters jailbreak attempts, stops system prompt exfiltration, and masks Indian PII (Aadhaar, PAN).
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Representative User Journeys */}
        <div className="card-olixer p-6 flex flex-col justify-between">
          <div>
            <h3 className="font-display font-bold text-base text-slate-900 mb-2 flex items-center gap-2">
              <Award className="w-5 h-5 text-amber-500" />
              Quick Guided Actions
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Select one of the pre-configured flows to test role capabilities:
            </p>
            <div className="space-y-2.5">
              <button
                onClick={() => onNavigate('leaves')}
                className="w-full text-left p-3.5 rounded-2xl border border-slate-200/80 hover:border-blue-400 hover:bg-blue-50/30 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-600">
                    1. Submit & Approve Leave
                  </div>
                  <div className="text-[11px] text-slate-500">Apply as employee &bull; Approve as HR Manager</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </button>

              <button
                onClick={() => onNavigate('policy')}
                className="w-full text-left p-3.5 rounded-2xl border border-slate-200/80 hover:border-blue-400 hover:bg-blue-50/30 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-600">
                    2. Query Maharashtra Labour Law
                  </div>
                  <div className="text-[11px] text-slate-500">Explore Section 18 statutory citations and overtime rules</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </button>

              <button
                onClick={() => onNavigate('reports')}
                className="w-full text-left p-3.5 rounded-2xl border border-slate-200/80 hover:border-blue-400 hover:bg-blue-50/30 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-600">
                    3. Generate Timesheet Reports & CSV
                  </div>
                  <div className="text-[11px] text-slate-500">Filter project hours & download audit-ready CSV</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
