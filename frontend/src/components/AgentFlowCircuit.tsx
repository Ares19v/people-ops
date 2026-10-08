import React, { useState } from 'react';
import { Cpu, FileText, Calendar, Clock, HeartPulse, RefreshCw, Brain, Sparkles, ShieldCheck, ArrowRight } from 'lucide-react';

interface AgentFlowCircuitProps {
  onSelectQuery?: (query: string) => void;
}

export const AgentFlowCircuit: React.FC<AgentFlowCircuitProps> = ({ onSelectQuery }) => {
  const [activePreset, setActivePreset] = useState<'leave' | 'policy' | 'timesheet' | 'health' | 'zoho'>('policy');

  const presets = [
    {
      id: 'leave' as const,
      label: 'Leave Application',
      sub: 'EL / CL / SL Statutory Request',
      query: 'I want to apply for 3 days Casual Leave from next Monday',
      targetAgent: 'Leave Subagent',
      targetId: 'leave',
      railStatus: 'Input Rail: 0 Policy Conflicts',
      icon: Calendar,
    },
    {
      id: 'policy' as const,
      label: 'Maharashtra Law Graph RAG',
      sub: 'Statutory Overtime & Hours',
      query: 'What is the maximum daily working hours and overtime pay under Maharashtra Act 2017?',
      targetAgent: 'Policy Graph RAG Subagent',
      targetId: 'policy',
      railStatus: 'Output Rail: Legal Citations Extracted',
      icon: FileText,
    },
    {
      id: 'timesheet' as const,
      label: 'Timesheet Entry & Overtime',
      sub: 'Hours Logging & Sec 13/14 Audit',
      query: 'What is the statutory overtime rate if I work 11 hours on a project?',
      targetAgent: 'Timesheet Subagent',
      targetId: 'timesheet',
      railStatus: 'Dual Rail: 9h Limit & DPDP Scrubbed',
      icon: Clock,
    },
    {
      id: 'health' as const,
      label: 'Occupational Health',
      sub: 'Sick Protocols & Doctor Certificate',
      query: 'Employee requesting 4 days of sick leave with fever, do I need a medical certificate?',
      targetAgent: 'Occupational Health Subagent',
      targetId: 'health',
      railStatus: 'Clinical Triage & HIPAA Sanitized',
      icon: HeartPulse,
    },
    {
      id: 'zoho' as const,
      label: 'Zoho People HRMS Sync',
      sub: 'Live REST v2 Attendance & Records',
      query: 'Sync my attendance and leave records with Zoho People API.',
      targetAgent: 'Zoho People Subagent',
      targetId: 'zoho',
      railStatus: 'REST v2 Integration & Zero Raw PII',
      icon: RefreshCw,
    },
  ];

  const current = presets.find((p) => p.id === activePreset) || presets[1];

  const fleetAgents = [
    {
      id: 'leave',
      name: 'Leave Subagent',
      icon: Calendar,
      role: 'Balance Ledger & Carry-Forward Validation',
      stat: 'Sec 18 Compliant',
    },
    {
      id: 'policy',
      name: 'Policy Graph RAG Subagent',
      icon: FileText,
      role: 'Graph RAG & Statutory Law Indexer',
      stat: 'Maharashtra Act 2017',
    },
    {
      id: 'timesheet',
      name: 'Timesheet Subagent',
      icon: Clock,
      role: '9h Daily / 48h Weekly Cap Auditing',
      stat: 'Sec 13 & 14 Overtime',
    },
    {
      id: 'health',
      name: 'Occupational Health Subagent',
      icon: HeartPulse,
      role: 'Clinical Triage, HIPAA & Medical Leave',
      stat: 'Doctor Cert Mandate',
    },
    {
      id: 'zoho',
      name: 'Zoho People Subagent',
      icon: RefreshCw,
      role: 'Live REST v2 Attendance & Leave Sync',
      stat: 'HRMS Bi-Directional',
    },
  ];

  const handleSelectPreset = (id: 'leave' | 'policy' | 'timesheet' | 'health' | 'zoho', query: string) => {
    setActivePreset(id);
    if (onSelectQuery) {
      onSelectQuery(query);
    }
  };

  const activeIndex = Math.max(0, presets.findIndex((p) => p.id === activePreset));
  const wirePoints = [
    { yCard: 10, yPort: 38 },
    { yCard: 30, yPort: 44 },
    { yCard: 50, yPort: 50 },
    { yCard: 70, yPort: 56 },
    { yCard: 90, yPort: 62 },
  ];

  return (
    <div className="card-olixer overflow-hidden p-6 sm:p-7 relative border border-slate-200/90 shadow-sm bg-gradient-to-b from-white via-slate-50/60 to-blue-50/20">
      {/* Header bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 mb-6 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-display font-bold text-base text-slate-900 tracking-tight">
              Root LLM Multi-Agent Flow Circuit — 5 Autonomous Subagents
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Root LLM dispatch with Langfuse prompt decoupling, multi-turn memory, NeMo guardrails, and zero-PII boundary.
          </p>
        </div>
      </div>

      {/* 5-Column High-End Converging Circuit Architecture */}
      <div className="circuit-board">
        {/* ===================== COLUMN 1: INBOUND REQUESTS ===================== */}
        <div className="flex flex-col h-full">
          <div className="flex items-center px-1 pb-2 h-7">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              1. Inbound HR Intent
            </span>
          </div>

          <div className="flex-1 grid grid-rows-5 gap-2.5">
            {presets.map((p) => {
              const isSelected = activePreset === p.id;
              const Icon = p.icon;
              return (
                <button
                  key={p.id}
                  onClick={() => handleSelectPreset(p.id, p.query)}
                  className={`w-full text-left p-2.5 sm:p-3 rounded-xl border transition-all duration-150 outline-none focus:outline-none relative group flex flex-col justify-center ${
                    isSelected
                      ? 'circuit-card-active'
                      : 'bg-gradient-to-r from-white to-slate-50/80 border-slate-200/90 hover:border-blue-300 hover:from-blue-50/30 hover:to-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`p-1.5 rounded-lg transition-colors shrink-0 ${
                          isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-slate-200'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                      </span>
                      <span className="font-display font-semibold text-xs text-slate-900 truncate">
                        {p.label}
                      </span>
                    </div>
                    {isSelected && (
                      <span className="text-[10px] font-bold text-blue-600 shrink-0">
                        Routed
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 pl-7 line-clamp-1">{p.sub}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* ===================== COLUMN 2: CONVERGING WIRES (LEFT) ===================== */}
        <div className="hidden lg:flex flex-col h-full pointer-events-none select-none">
          <div className="h-7" />
          <div className="flex-1 relative w-full">
            <svg
              className="w-full h-full overflow-visible"
              viewBox="0 0 52 100"
              preserveAspectRatio="none"
            >
              {wirePoints.map((wp, idx) => {
                const isActive = idx === activeIndex;
                const d = `M 0,${wp.yCard} C 26,${wp.yCard} 26,${wp.yPort} 53,${wp.yPort}`;
                return (
                  <path
                    key={`wire-left-${idx}`}
                    d={d}
                    fill="none"
                    stroke={isActive ? '#2563eb' : '#cbd5e1'}
                    strokeWidth={isActive ? '2' : '1.25'}
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>
          </div>
        </div>

        {/* ===================== COLUMN 3: ROOT ORCHESTRATOR HUB ===================== */}
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-center px-1 pb-2 h-7">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              2. Root Orchestrator Kernel
            </span>
          </div>

          <div className="circuit-hub-box p-3.5 sm:p-4 flex-1 flex flex-col justify-between relative">
            {/* Header: Core Identification */}
            <div className="text-center pt-0.5 pb-1">
              <div className="mb-2 flex items-center justify-center">
                <div className="w-8 h-8 rounded-lg bg-slate-900/70 border border-slate-700/60 flex items-center justify-center text-slate-200 shadow-sm">
                  <Brain className="w-4 h-4 text-slate-200" />
                </div>
              </div>
              <h4 className="font-display font-semibold text-xs tracking-tight text-white">
                Root LLM Orchestrator
              </h4>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                Google ADK Multi-Agent Kernel
              </p>
            </div>

            {/* Architectural Specifications — Minimal & Uncluttered */}
            <div className="bg-slate-900/40 rounded-xl border border-slate-800/60 p-3 w-full space-y-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Prompts</span>
                <span className="text-slate-200 font-mono text-[11px]">Langfuse</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Memory</span>
                <span className="text-slate-200 font-mono text-[11px]">Multi-Turn</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Guardrails</span>
                <span className="text-slate-200 font-mono text-[11px]">NeMo</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Privacy</span>
                <span className="text-slate-200 font-mono text-[11px]">DPDP Vault</span>
              </div>
            </div>

            {/* Current Delegation Target */}
            <div className="bg-slate-900/50 rounded-xl border border-slate-700/60 py-2.5 px-3 text-left w-full">
              <div className="text-xs font-semibold text-white tracking-tight flex items-center justify-between">
                <span className="truncate">{current.targetAgent}</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              </div>
            </div>
          </div>
        </div>

        {/* ===================== COLUMN 4: DIVERGING WIRES (RIGHT) ===================== */}
        <div className="hidden lg:flex flex-col h-full pointer-events-none select-none">
          <div className="h-7" />
          <div className="flex-1 relative w-full">
            <svg
              className="w-full h-full overflow-visible"
              viewBox="0 0 52 100"
              preserveAspectRatio="none"
            >
              {wirePoints.map((wp, idx) => {
                const isActive = idx === activeIndex;
                const d = `M -1,${wp.yPort} C 26,${wp.yPort} 26,${wp.yCard} 52,${wp.yCard}`;
                return (
                  <path
                    key={`wire-right-${idx}`}
                    d={d}
                    fill="none"
                    stroke={isActive ? '#059669' : '#cbd5e1'}
                    strokeWidth={isActive ? '2' : '1.25'}
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>
          </div>
        </div>

        {/* ===================== COLUMN 5: AUTONOMOUS EXECUTION FLEET ===================== */}
        <div className="flex flex-col h-full">
          <div className="flex items-center px-1 pb-2 h-7">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              3. Autonomous Fleet
            </span>
          </div>

          <div className="flex-1 grid grid-rows-5 gap-2.5">
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
                  className={`p-2.5 sm:p-3 rounded-xl border transition-all duration-150 cursor-pointer outline-none relative flex flex-col justify-center ${
                    isTarget
                      ? 'circuit-target-active'
                      : 'bg-gradient-to-l from-white to-slate-50/80 border-slate-200/90 hover:border-slate-300 opacity-80 hover:opacity-100 hover:from-blue-50/20 hover:to-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`p-1.5 rounded-lg transition-colors shrink-0 ${
                          isTarget ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                      </span>
                      <span className="font-display font-semibold text-xs text-slate-900 truncate">
                        {agent.name}
                      </span>
                    </div>
                    {isTarget && (
                      <span className="text-[10px] font-bold text-emerald-600 shrink-0">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 pl-7 line-clamp-1">{agent.role}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

