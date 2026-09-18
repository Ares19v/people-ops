import React, { useState } from 'react';
import {
  Bot, ShieldCheck, ShieldAlert, Cpu, ArrowRight, Zap,
  FileText, Calendar, Clock, Sparkles, CheckCircle2, ChevronRight
} from 'lucide-react';

interface AgentFlowCircuitProps {
  onSelectQuery?: (query: string) => void;
}

export const AgentFlowCircuit: React.FC<AgentFlowCircuitProps> = ({ onSelectQuery }) => {
  const [activePreset, setActivePreset] = useState<'leave' | 'policy' | 'timesheet'>('policy');

  const presets = [
    {
      id: 'leave' as const,
      label: 'Leave Application',
      sub: 'EL / CL / SL Statutory Request',
      query: 'I want to apply for 3 days Casual Leave from next Monday',
      targetAgent: 'Leave Agent',
      targetId: 'leave',
      railStatus: 'Input Rail: 0 Policy Conflicts',
      icon: Calendar,
    },
    {
      id: 'policy' as const,
      label: 'Maharashtra Law Graph RAG',
      sub: 'Statutory Overtime & Hours',
      query: 'What is the maximum daily working hours and overtime pay under Maharashtra Act 2017?',
      targetAgent: 'HR Policy Agent',
      targetId: 'policy',
      railStatus: 'Output Rail: Legal Citations Extracted',
      icon: FileText,
    },
    {
      id: 'timesheet' as const,
      label: 'Timesheet Entry',
      sub: 'Hours Logging & Overtime Audit',
      query: 'Log 9.5 hours for Project Apollo with 0.5h overtime',
      targetAgent: 'Timesheet Agent',
      targetId: 'timesheet',
      railStatus: 'Dual Rail: 9h Limit & DPDP Scrubbed',
      icon: Clock,
    },
  ];

  const current = presets.find((p) => p.id === activePreset) || presets[1];

  const fleetAgents = [
    {
      id: 'leave',
      name: 'Leave Agent',
      icon: Calendar,
      role: 'Balance Ledger & Carry-Forward Validation',
      stat: 'Sec 18 Compliant',
    },
    {
      id: 'policy',
      name: 'HR Policy Agent',
      icon: FileText,
      role: 'Graph RAG & Statutory Law Indexer',
      stat: 'Maharashtra Act 2017',
    },
    {
      id: 'timesheet',
      name: 'Timesheet Agent',
      icon: Clock,
      role: '9h Daily / 48h Weekly Cap Auditing',
      stat: 'Sec 13 Overtime Rail',
    },
  ];

  const handleSelectPreset = (id: 'leave' | 'policy' | 'timesheet', query: string) => {
    setActivePreset(id);
    if (onSelectQuery) {
      onSelectQuery(query);
    }
  };

  return (
    <div className="card-olixer overflow-hidden p-6 sm:p-7 relative border border-slate-200/90 shadow-sm">
      {/* Header bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 mb-6 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-600"></span>
            </span>
            <h3 className="font-display font-bold text-base text-slate-900 tracking-tight">
              Google ADK Multi-Agent Flow Circuit &bull; NeMo Safety Boundary
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Autonomous multi-agent intent pipeline with real-time Colang 2.0 guardrails and PII redaction.
          </p>
        </div>

        {/* Status Indicators Pill Group */}
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto">
          <span className="badge-statutory-green text-[11px] font-medium py-1 px-2.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Colang 2.0 Rails Active</span>
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200/60">
            <Zap className="w-3 h-3 text-blue-600 animate-pulse" />
            <span>Routing Latency: 42ms</span>
          </span>
        </div>
      </div>

      {/* High-End 3-Stage Circuit Architecture */}
      <div className="circuit-board">
        {/* ===================== STAGE 1: INBOUND REQUESTS ===================== */}
        <div className="flex flex-col space-y-2.5">
          <div className="flex items-center justify-between px-1 pb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              1. Inbound HR Intent
            </span>
            <span className="text-[10px] text-blue-600 font-semibold bg-blue-50 px-2 py-0.5 rounded-full">
              Click to route
            </span>
          </div>

          {presets.map((p) => {
            const isSelected = activePreset === p.id;
            const Icon = p.icon;
            return (
              <button
                key={p.id}
                onClick={() => handleSelectPreset(p.id, p.query)}
                className={`w-full text-left p-3.5 rounded-2xl border transition-all duration-200 outline-none focus:outline-none relative group ${
                  isSelected
                    ? 'circuit-card-active'
                    : 'bg-white border-slate-200/90 hover:border-slate-300 hover:bg-slate-50/60'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`p-1.5 rounded-xl transition-colors ${
                        isSelected ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600 group-hover:bg-slate-200'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                    <span className="font-display font-bold text-xs text-slate-900">
                      {p.label}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="flex items-center gap-1 text-[10px] font-bold text-blue-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                      Routed
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 pl-8 line-clamp-1">{p.sub}</p>
              </button>
            );
          })}
        </div>

        {/* ===================== STAGE 2: ROOT ORCHESTRATOR HUB ===================== */}
        <div className="flex flex-col">
          <div className="flex items-center justify-center px-1 pb-1 mb-2.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              2. NeMo Kernel
            </span>
          </div>

          <div className="circuit-hub-box p-5 text-white flex-1 flex flex-col justify-between">
            {/* Animated Processor Icon */}
            <div className="relative mb-3 flex items-center justify-center">
              <div className="absolute w-12 h-12 rounded-full bg-blue-500/20 radar-ping" />
              <div className="w-11 h-11 rounded-2xl bg-blue-600/30 border border-blue-400/50 flex items-center justify-center shadow-inner relative z-10">
                <Cpu className="w-5 h-5 text-blue-400 animate-pulse" />
              </div>
            </div>

            {/* Hub Titles */}
            <div className="text-center">
              <h4 className="font-display font-bold text-xs tracking-tight text-white">
                Root Orchestrator
              </h4>
              <span className="text-[10px] text-blue-400 font-semibold uppercase tracking-wider">
                Google ADK Kernel
              </span>
            </div>

            {/* Live Security & Routing Metrics */}
            <div className="w-full my-3.5 pt-3 border-t border-slate-800/90 space-y-2 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">NeMo Rail:</span>
                <span className="font-bold text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  PASSED
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Active Route:</span>
                <span className="font-bold text-blue-300 font-mono">
                  {current.targetAgent.split(' ')[0]} Agent
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">DPDP Privacy:</span>
                <span className="font-bold text-emerald-400">SCRUBBED</span>
              </div>
            </div>

            {/* Active flow connection line */}
            <div className="w-full pt-2 border-t border-slate-800/80 flex items-center justify-center gap-1.5 text-[10px] text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
              <span className="font-mono text-slate-300 font-medium">Safe Sub-Agent Fleet</span>
            </div>
          </div>
        </div>

        {/* ===================== STAGE 3: AUTONOMOUS EXECUTION FLEET ===================== */}
        <div className="flex flex-col space-y-2.5">
          <div className="flex items-center justify-between px-1 pb-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              3. Autonomous Fleet
            </span>
            <span className="text-[10px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full">
              Live Target
            </span>
          </div>

          {fleetAgents.map((agent) => {
            const isTarget = current.targetId === agent.id;
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                onClick={() => {
                  const matchingPreset = presets.find((p) => p.id === agent.id);
                  if (matchingPreset) {
                    handleSelectPreset(matchingPreset.id, matchingPreset.query);
                  }
                }}
                className={`p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer outline-none ${
                  isTarget
                    ? 'circuit-target-active'
                    : 'bg-white border-slate-200/90 hover:border-slate-300 opacity-70 hover:opacity-100'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`p-1.5 rounded-xl transition-colors ${
                        isTarget
                          ? 'bg-emerald-600 text-white shadow-sm'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                    <span className="font-display font-bold text-xs text-slate-900">
                      {agent.name}
                    </span>
                  </div>
                  {isTarget && (
                    <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      Active
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 pl-8 line-clamp-1">{agent.role}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

