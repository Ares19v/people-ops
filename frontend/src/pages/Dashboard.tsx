import React, { useState, useEffect } from 'react';
import { User, UserRole, LeaveBalanceSummary } from '../types';
import { api } from '../api';
import {
  Calendar, Clock, Shield, Sparkles, UserPlus, CheckCircle2,
  TrendingUp, ArrowUpRight, Award, AlertCircle, Cpu, Bot, Workflow
} from 'lucide-react';
import { AgentFlowCircuit } from '../components/AgentFlowCircuit';
import { FeatureExplainerIcon } from '../components/FeatureExplainerIcon';

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

  const [weeklyLoggedHours, setWeeklyLoggedHours] = useState<number | null>(null);

  useEffect(() => {
    const fetchWeeklyHours = async () => {
      try {
        const now = new Date();
        const day = now.getDay();
        const diff = now.getDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(now.setDate(diff)).toISOString().slice(0, 10);
        const rep = await api.getTimesheetReport({ start_date: monday });
        setWeeklyLoggedHours(rep.total_hours ?? 0);
      } catch {
        setWeeklyLoggedHours(0);
      }
    };
    fetchWeeklyHours();
  }, [currentUser, currentRole]);

  return (
    <div className="space-y-12 pb-8">
      {/* Olixer Hero Presentation Section */}
      <div className="hero-wrapper">
        <h1 className="hero-main-title inline-flex flex-wrap items-center justify-center gap-1.5">
          <span>Intelligent People Operations, <br className="hidden sm:inline" />
          <strong>orchestrated by autonomous agents.</strong></span>
          <FeatureExplainerIcon featureKey="hero_banner" />
        </h1>
        <p className="hero-subtext">
          Enforcing Maharashtra Shops & Establishments Act 2017 rules, automated leave ledgers, and DPDP-compliant PII redaction.
        </p>

        {/* Hero Quick Action Pills */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3.5">
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
          <FeatureExplainerIcon featureKey="quick_actions" />
        </div>
      </div>

      {/* Interactive Multi-Agent Flow Circuit */}
      <div className="relative">
        <AgentFlowCircuit onSelectQuery={(query) => openChat(query)} />
      </div>

      {/* KPI Metrics Row in Olixer Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Earned Leave */}
        <div
          onClick={() => onNavigate('leaves')}
          className="card-olixer p-5 cursor-pointer hover:border-blue-300 hover:shadow-md transition-all group bg-gradient-to-b from-white via-slate-50/70 to-blue-50/30 border border-slate-200/90"
          title="View Leave Ledger"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-700 group-hover:text-blue-950 transition-colors">Earned Leave (EL)</span>
              <FeatureExplainerIcon featureKey="kpi_earned_leave" />
            </div>
            <span className="p-1.5 rounded-lg bg-blue-50/80 text-blue-700 border border-blue-200/60 transition-colors group-hover:bg-blue-100 group-hover:text-blue-900">
              <Calendar className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">{el}</span>
            <span className="text-xs font-medium text-slate-500">days balance</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-blue-900 bg-blue-50/70 border border-blue-200/60 rounded-md px-2 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-blue-600" />
              Max 45-day carry-over — Sec 18
            </span>
          </div>
        </div>

        {/* Casual Leave */}
        <div
          onClick={() => onNavigate('leaves')}
          className="card-olixer p-5 cursor-pointer hover:border-blue-300 hover:shadow-md transition-all group bg-gradient-to-b from-white via-slate-50/70 to-blue-50/30 border border-slate-200/90"
          title="View Leave Ledger"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-700 group-hover:text-blue-950 transition-colors">Casual Leave (CL)</span>
              <FeatureExplainerIcon featureKey="kpi_casual_leave" />
            </div>
            <span className="p-1.5 rounded-lg bg-blue-50/80 text-blue-700 border border-blue-200/60 transition-colors group-hover:bg-blue-100 group-hover:text-blue-900">
              <Calendar className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">{cl}</span>
            <span className="text-xs font-medium text-slate-500">days balance</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-700 bg-slate-100/80 border border-slate-200/80 rounded-md px-2 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-slate-500" />
              8 days statutory quota
            </span>
          </div>
        </div>

        {/* Logged Hours */}
        <div
          onClick={() => onNavigate('timesheets')}
          className="card-olixer p-5 cursor-pointer hover:border-blue-300 hover:shadow-md transition-all group bg-gradient-to-b from-white via-slate-50/70 to-blue-50/30 border border-slate-200/90"
          title="View Timesheets"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-700 group-hover:text-blue-950 transition-colors">Logged Hours (Week)</span>
              <FeatureExplainerIcon featureKey="dashboard_timesheet_overtime" />
            </div>
            <span className="p-1.5 rounded-lg bg-blue-50/80 text-blue-700 border border-blue-200/60 transition-colors group-hover:bg-blue-100 group-hover:text-blue-900">
              <Clock className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">
              {weeklyLoggedHours !== null ? weeklyLoggedHours.toFixed(1) : '—'}
            </span>
            <span className="text-xs font-medium text-slate-500">hrs logged</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-blue-900 bg-blue-50/70 border border-blue-200/60 rounded-md px-2 py-0.5">
              <Clock className="w-3 h-3 text-blue-600" />
              48h Weekly Cap — MH Act
            </span>
          </div>
        </div>

        {/* NeMo Guardrails */}
        <div
          onClick={() => openChat('What NVIDIA NeMo Guardrails are active in this workspace?')}
          className="card-olixer p-5 cursor-pointer hover:border-blue-300 hover:shadow-md transition-all group bg-gradient-to-b from-white via-slate-50/70 to-blue-50/30 border border-slate-200/90"
          title="Ask HR AI about Guardrails"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-700 group-hover:text-blue-950 transition-colors">NeMo Safety Rails</span>
              <FeatureExplainerIcon featureKey="kpi_compliance_health" />
            </div>
            <span className="p-1.5 rounded-lg bg-blue-50/80 text-blue-700 border border-blue-200/60 transition-colors group-hover:bg-blue-100 group-hover:text-blue-900">
              <Shield className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">Active</span>
            <span className="text-xs font-medium text-slate-500">Dual-Boundary</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-900 bg-emerald-50/70 border border-emerald-200/60 rounded-md px-2 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              Colang 2.0 — DPDP Scrubbing
            </span>
          </div>
        </div>
      </div>

      {/* Role Workflows & Architecture Capabilities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Architecture Status Dossier */}
        <div className="card-olixer p-6 bg-gradient-to-b from-white to-slate-50/50 border border-slate-200/90">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <h3 className="font-display font-bold text-base text-slate-900 flex items-center gap-2">
                <Shield className="w-4.5 h-4.5 text-blue-800" />
                Active Sub-Agent Fleet (Google ADK)
              </h3>
              <FeatureExplainerIcon featureKey="dashboard_agent_telemetry" />
            </div>
            <span className="text-[10px] font-mono font-medium text-blue-900 bg-blue-50/90 px-2.5 py-0.5 rounded border border-blue-200/70">
              5 Subagents + Root LLM
            </span>
          </div>
          <div className="space-y-2">
            {/* Root LLM Orchestrator */}
            <div className="p-3 bg-gradient-to-r from-slate-50/80 to-blue-50/30 border border-slate-200/80 rounded-xl flex items-start gap-3 hover:border-blue-200 transition-colors">
              <div className="w-7 h-7 rounded-lg bg-slate-900 text-white flex items-center justify-center font-mono font-bold text-[10px] shrink-0 border border-slate-800 shadow-xs">
                LLM
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h4 className="font-display font-bold text-xs text-slate-900">Root LLM Orchestrator</h4>
                  <FeatureExplainerIcon featureKey="agent_root_orchestrator" />
                  <span className="text-[9px] font-mono font-medium text-blue-800 bg-blue-100/70 px-1.5 py-0.2 rounded border border-blue-200/70">CORE</span>
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                  Decoupled Langfuse prompt registry, multi-turn memory recall, and NeMo zero-PII boundary routing across 5 subagents.
                </p>
              </div>
            </div>

            {/* Occupational Health Subagent */}
            <div className="p-3 bg-gradient-to-r from-slate-50/80 to-blue-50/20 border border-slate-200/80 rounded-xl flex items-start gap-3 hover:border-blue-200 transition-colors">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-900 flex items-center justify-center font-mono font-bold text-[10px] shrink-0 border border-blue-200/80">
                MED
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center">
                  <h4 className="font-display font-bold text-xs text-slate-900">Occupational Health Subagent</h4>
                  <FeatureExplainerIcon featureKey="kpi_sick_leave" />
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                  Clinical decision support, sick leave quotas, HIPAA/DPDP privacy, and doctor certificate validation for &gt;2 days absence.
                </p>
              </div>
            </div>

            {/* Zoho People Subagent */}
            <div className="p-3 bg-gradient-to-r from-slate-50/80 to-blue-50/20 border border-slate-200/80 rounded-xl flex items-start gap-3 hover:border-blue-200 transition-colors">
              <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center font-mono font-bold text-[10px] shrink-0 border border-slate-200">
                SYNC
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center">
                  <h4 className="font-display font-bold text-xs text-slate-900">Zoho People Subagent</h4>
                  <FeatureExplainerIcon featureKey="zoho_sync_integration" />
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                  Live bi-directional REST v2 integration synchronizing employee attendance logs and leave records with zero raw PII exposure.
                </p>
              </div>
            </div>

            {/* HR Policy Graph RAG */}
            <div className="p-3 bg-gradient-to-r from-slate-50/80 to-blue-50/20 border border-slate-200/80 rounded-xl flex items-start gap-3 hover:border-blue-200 transition-colors">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-900 flex items-center justify-center font-mono font-bold text-[10px] shrink-0 border border-blue-200/80">
                RAG
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center">
                  <h4 className="font-display font-bold text-xs text-slate-900">Policy & Statutory Graph RAG</h4>
                  <FeatureExplainerIcon featureKey="policy_rag_search" />
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                  Indexes Maharashtra Shops & Establishments Act 2017 & company bylaws with exact section citations.
                </p>
              </div>
            </div>

            {/* Leave & Timesheet Subagents */}
            <div className="p-3 bg-gradient-to-r from-slate-50/80 to-blue-50/20 border border-slate-200/80 rounded-xl flex items-start gap-3 hover:border-blue-200 transition-colors">
              <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center font-mono font-bold text-[10px] shrink-0 border border-slate-200">
                OPS
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center">
                  <h4 className="font-display font-bold text-xs text-slate-900">Leave & Timesheet Subagents</h4>
                  <FeatureExplainerIcon featureKey="dashboard_leave_ledger" />
                </div>
                <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                  Authoritative leave ledgers (Sec 18, 45-day carry-over) and daily overtime auditing under Section 13 & 14.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Representative User Journeys */}
        <div className="card-olixer p-6 flex flex-col justify-between bg-gradient-to-b from-white to-slate-50/50 border border-slate-200/90">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <h3 className="font-display font-bold text-base text-slate-900 flex items-center gap-2">
                  <Workflow className="w-4.5 h-4.5 text-blue-800" />
                  Quick Guided Actions
                </h3>
                <FeatureExplainerIcon featureKey="dashboard_recent_requests" />
              </div>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Select a pre-configured workflow to execute role and agent capabilities:
            </p>
            <div className="space-y-2">
              <button
                onClick={() => onNavigate('leaves')}
                className="w-full text-left p-3 rounded-xl border border-slate-200/90 hover:border-blue-300 hover:from-blue-50/40 hover:to-white transition-all flex items-center justify-between gap-3 min-w-0 group bg-gradient-to-r from-white to-slate-50/80 shadow-2xs overflow-hidden"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-950 truncate">
                    1. Submit & Approve Leave
                  </div>
                  <div className="text-[11px] text-slate-500 group-hover:text-slate-600 truncate">Apply as employee — Approve as HR Manager</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-700 transition-colors shrink-0" />
              </button>

              <button
                onClick={() => onNavigate('policy')}
                className="w-full text-left p-3 rounded-xl border border-slate-200/90 hover:border-blue-300 hover:from-blue-50/40 hover:to-white transition-all flex items-center justify-between gap-3 min-w-0 group bg-gradient-to-r from-white to-slate-50/80 shadow-2xs overflow-hidden"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-950 truncate">
                    2. Query Maharashtra Labour Law
                  </div>
                  <div className="text-[11px] text-slate-500 group-hover:text-slate-600 truncate">Explore Section 18 statutory citations and overtime rules</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-700 transition-colors shrink-0" />
              </button>

              <button
                onClick={() => openChat('Employee requesting 4 days of sick leave with fever, do I need a medical certificate?')}
                className="w-full text-left p-3 rounded-xl border border-slate-200/90 hover:border-blue-300 hover:from-blue-50/40 hover:to-white transition-all flex items-center justify-between gap-3 min-w-0 group bg-gradient-to-r from-white to-slate-50/80 shadow-2xs overflow-hidden"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-950 truncate">
                    3. Occupational Health Advisory
                  </div>
                  <div className="text-[11px] text-slate-500 group-hover:text-slate-600 truncate">Test fever/sick leave triage & doctor certificate rule (&gt;2 days)</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-700 transition-colors shrink-0" />
              </button>

              <button
                onClick={() => openChat('Sync my attendance and leave records with Zoho People API.')}
                className="w-full text-left p-3 rounded-xl border border-slate-200/90 hover:border-blue-300 hover:from-blue-50/40 hover:to-white transition-all flex items-center justify-between gap-3 min-w-0 group bg-gradient-to-r from-white to-slate-50/80 shadow-2xs overflow-hidden"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-950 truncate">
                    4. Zoho People System Sync
                  </div>
                  <div className="text-[11px] text-slate-500 group-hover:text-slate-600 truncate">Test live external HRMS attendance & leave record sync</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-700 transition-colors shrink-0" />
              </button>

              <button
                onClick={() => onNavigate('reports')}
                className="w-full text-left p-3 rounded-xl border border-slate-200/90 hover:border-blue-300 hover:from-blue-50/40 hover:to-white transition-all flex items-center justify-between gap-3 min-w-0 group bg-gradient-to-r from-white to-slate-50/80 shadow-2xs overflow-hidden"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-xs font-bold text-slate-900 group-hover:text-blue-950 truncate">
                    5. Timesheet Reports & CSV Export
                  </div>
                  <div className="text-[11px] text-slate-500 group-hover:text-slate-600 truncate">Filter project hours & download audit-ready CSV</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-700 transition-colors shrink-0" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
