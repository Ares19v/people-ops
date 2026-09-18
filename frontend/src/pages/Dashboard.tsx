import React from 'react';
import { User, UserRole, LeaveBalanceSummary } from '../types';
import {
  Calendar, Clock, Shield, Sparkles, UserPlus, CheckCircle2,
  TrendingUp, ArrowUpRight, Award, AlertCircle
} from 'lucide-react';

interface DashboardProps {
  currentUser: User | null;
  currentRole: UserRole;
  balances: LeaveBalanceSummary | null;
  onNavigate: (tab: string) => void;
  openChat: () => void;
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
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 rounded-2xl p-6 sm:p-8 text-white shadow-lg relative overflow-hidden">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold mb-3 border border-emerald-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            Google ADK Multi-Agent Orchestration &bull; NeMo Guardrails
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Welcome back, {currentUser?.full_name || 'Team Member'}
          </h1>
          <p className="mt-2 text-slate-300 text-sm sm:text-base leading-relaxed">
            Role: <span className="font-semibold text-emerald-400">{currentRole}</span> &bull; {currentUser?.department || 'Operations'} &bull; All interactions secured by dual-boundary guardrails and DPDP-compliant redaction.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              onClick={() => onNavigate('leaves')}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center gap-2"
            >
              <Calendar className="w-4 h-4" />
              Manage Leaves
            </button>
            <button
              onClick={() => onNavigate('timesheets')}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-sm font-semibold backdrop-blur-sm border border-white/10 transition-all flex items-center gap-2"
            >
              <Clock className="w-4 h-4" />
              Log Timesheet
            </button>
            <button
              onClick={openChat}
              className="px-4 py-2 bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-600 hover:to-emerald-700 text-white rounded-xl text-sm font-semibold shadow-md transition-all flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              Ask AI Agent
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:border-emerald-200 transition-all">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Earned Leave (EL)</span>
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <Calendar className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{el}</span>
            <span className="text-xs text-slate-500">days available</span>
          </div>
          <div className="mt-2 text-xs text-slate-600 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Max 45 days carry-over (MH Act)
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:border-blue-200 transition-all">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Casual Leave (CL)</span>
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
              <Calendar className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{cl}</span>
            <span className="text-xs text-slate-500">days available</span>
          </div>
          <div className="mt-2 text-xs text-slate-600 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
            8 days statutory quota
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:border-amber-200 transition-all">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Logged Hours (Week)</span>
            <span className="p-1.5 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">40.0</span>
            <span className="text-xs text-slate-500">hrs logged</span>
          </div>
          <div className="mt-2 text-xs text-emerald-600 flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Target achieved
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:border-purple-200 transition-all">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Safety Guardrails</span>
            <span className="p-1.5 rounded-lg bg-purple-50 text-purple-600">
              <Shield className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-purple-700">Active</span>
            <span className="text-xs text-slate-500">NeMo 0.24</span>
          </div>
          <div className="mt-2 text-xs text-purple-600 flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Dual-boundary enabled
          </div>
        </div>
      </div>

      {/* Role-Specific Capabilities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-600" />
            Multi-Agent Architecture Status
          </h3>
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 rounded-lg flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs shrink-0">
                ADK
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Root Orchestrator (Google ADK)</h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  Routes conversational intents directly to Leave, Policy, and Timesheet specialized agents.
                </p>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs shrink-0">
                RAG
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">HR Policy Graph RAG</h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  Synthesizes knowledge graph nodes from the Maharashtra Shops & Establishments Act, 2017 with exact citations.
                </p>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs shrink-0">
                SAFE
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">NVIDIA NeMo Guardrails</h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  Enforces Colang 2.0 rails against jailbreaks, prompt injection, and redacts sensitive Indian PII (Aadhaar, PAN).
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
              <Award className="w-5 h-5 text-amber-500" />
              Quick Representative Journeys
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              Select one of the pre-configured flows to test role capabilities:
            </p>
            <div className="space-y-2.5">
              <button
                onClick={() => onNavigate('leaves')}
                className="w-full text-left p-3 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/50 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-900 group-hover:text-emerald-700">
                    1. Submit & Approve Leave
                  </div>
                  <div className="text-[11px] text-slate-500">Apply as employee &bull; Approve as HR Manager</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600" />
              </button>

              <button
                onClick={() => onNavigate('policy')}
                className="w-full text-left p-3 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-900 group-hover:text-blue-700">
                    2. Query Maharashtra Labour Law
                  </div>
                  <div className="text-[11px] text-slate-500">Explore Section 18 statutory citations and rules</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600" />
              </button>

              <button
                onClick={() => onNavigate('reports')}
                className="w-full text-left p-3 rounded-xl border border-slate-200 hover:border-purple-300 hover:bg-purple-50/50 transition-all flex items-center justify-between group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-900 group-hover:text-purple-700">
                    3. Generate Timesheet Reports & CSV
                  </div>
                  <div className="text-[11px] text-slate-500">Filter project hours & download official CSV</div>
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-purple-600" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
