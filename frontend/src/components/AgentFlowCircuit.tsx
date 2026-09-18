import React, { useState } from 'react';
import { Bot, ShieldCheck, ShieldAlert, Cpu, ArrowRight, Zap, FileText, Calendar, Clock, Sparkles } from 'lucide-react';

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
      guardrailCheck: 'Input Rail: Policy conflict check & overlap validation',
    },
    {
      id: 'policy' as const,
      label: 'Maharashtra Law Graph RAG',
      sub: 'Statutory Overtime & Hours',
      query: 'What is the maximum daily working hours and overtime pay under Maharashtra Act 2017?',
      targetAgent: 'HR Policy Agent',
      guardrailCheck: 'Output Rail: Legal disclaimer attached & citations extracted',
    },
    {
      id: 'timesheet' as const,
      label: 'Timesheet Entry',
      sub: 'Hours Logging & Overtime Audit',
      query: 'Log 9.5 hours for Project Apollo with 0.5h overtime',
      targetAgent: 'Timesheet Agent',
      guardrailCheck: 'Dual Rail: 9h/day limit check & DPDP scrubbed trace',
    },
  ];

  const current = presets.find((p) => p.id === activePreset) || presets[1];

  return (
    <div className="card-olixer overflow-hidden p-6 sm:p-8" style={{ position: 'relative' }}>
      {/* Background SVG Flow Connectors */}
      <svg
        className="hidden lg:block absolute inset-0 w-full h-full pointer-events-none z-0"
        viewBox="0 0 1000 340"
        preserveAspectRatio="none"
      >
        {/* Left top to center */}
        <path
          d="M 290 85 C 370 85, 410 170, 500 170"
          fill="none"
          stroke={activePreset === 'leave' ? '#2563eb' : '#cbd5e1'}
          strokeWidth={activePreset === 'leave' ? '2.5' : '1.5'}
          strokeDasharray={activePreset === 'leave' ? 'none' : '4 4'}
        />
        {/* Left center to center */}
        <path
          d="M 290 170 C 370 170, 410 170, 500 170"
          fill="none"
          stroke={activePreset === 'policy' ? '#2563eb' : '#cbd5e1'}
          strokeWidth={activePreset === 'policy' ? '2.5' : '1.5'}
        />
        {/* Left bottom to center */}
        <path
          d="M 290 255 C 370 255, 410 170, 500 170"
          fill="none"
          stroke={activePreset === 'timesheet' ? '#2563eb' : '#cbd5e1'}
          strokeWidth={activePreset === 'timesheet' ? '2.5' : '1.5'}
          strokeDasharray={activePreset === 'timesheet' ? 'none' : '4 4'}
        />
        {/* Center to right top */}
        <path
          d="M 500 170 C 590 170, 630 85, 710 85"
          fill="none"
          stroke={activePreset === 'leave' ? '#059669' : '#cbd5e1'}
          strokeWidth={activePreset === 'leave' ? '2.5' : '1.5'}
        />
        {/* Center to right center */}
        <path
          d="M 500 170 C 590 170, 630 170, 710 170"
          fill="none"
          stroke={activePreset === 'policy' ? '#059669' : '#cbd5e1'}
          strokeWidth={activePreset === 'policy' ? '2.5' : '1.5'}
        />
        {/* Center to right bottom */}
        <path
          d="M 500 170 C 590 170, 630 255, 710 255"
          fill="none"
          stroke={activePreset === 'timesheet' ? '#059669' : '#cbd5e1'}
          strokeWidth={activePreset === 'timesheet' ? '2.5' : '1.5'}
        />
      </svg>

      {/* Header bar inside card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
            <h3 className="font-display font-bold text-base text-slate-900 tracking-tight">
              Google ADK Multi-Agent Flow Circuit &bull; NeMo Safety Boundary
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time intent routing through NVIDIA NeMo Guardrails to specialized autonomous agents.
          </p>
        </div>
        <div className="badge-statutory-green self-start sm:self-auto">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>DPDP Act 2023 Scrubbing Active</span>
        </div>
      </div>

      {/* 3 Column Interactive Circuit Diagram */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_270px_minmax(220px,1fr)] gap-6 xl:gap-8 items-center relative z-10">
        {/* LEFT COLUMN: Inbound Requests */}
        <div className="space-y-3">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            1. Inbound HR Requests (Click to route)
          </div>
          {presets.map((p) => {
            const isSelected = activePreset === p.id;
            return (
              <div
                key={p.id}
                onClick={() => {
                  setActivePreset(p.id);
                  if (onSelectQuery) onSelectQuery(p.query);
                }}
                className={`p-3.5 rounded-2xl border cursor-pointer transition-all outline-none focus:outline-none ${
                  isSelected
                    ? 'bg-blue-50/80 border-blue-600 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-display font-bold text-xs text-slate-900">{p.label}</span>
                  {isSelected && <span className="w-2 h-2 rounded-full bg-blue-600" />}
                </div>
                <p className="text-[11px] text-slate-500 mt-1 line-clamp-1">{p.sub}</p>
              </div>
            );
          })}
        </div>

        {/* CENTER COLUMN: NeMo Perimeter & Root Orchestrator */}
        <div className="w-full max-w-[260px] mx-auto flex flex-col items-center justify-center p-5 rounded-3xl bg-slate-900 text-white shadow-xl border border-slate-800 relative">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center mb-3">
            <Cpu className="w-6 h-6 text-blue-400" />
          </div>
          <span className="font-display font-bold text-sm tracking-tight text-white">
            Root Orchestrator
          </span>
          <span className="text-[11px] text-blue-400 font-semibold mt-0.5">
            Google ADK Kernel
          </span>

          <div className="mt-4 w-full pt-3 border-t border-slate-800 space-y-2 text-[11px]">
            <div className="flex items-center justify-between text-slate-300">
              <span className="text-slate-400">NeMo Input Rail:</span>
              <span className="font-semibold text-emerald-400">PASSED</span>
            </div>
            <div className="flex items-center justify-between text-slate-300">
              <span className="text-slate-400">Target Sub-Agent:</span>
              <span className="font-bold text-blue-300">{current.targetAgent}</span>
            </div>
            <div className="flex items-center justify-between text-slate-300">
              <span className="text-slate-400">PII Scrubbing:</span>
              <span className="font-semibold text-emerald-400">ENFORCED</span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Specialized Execution Agents */}
        <div className="space-y-3">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            2. Autonomous Execution Fleet (Click to inspect)
          </div>

          <div
            onClick={() => {
              setActivePreset('leave');
              if (onSelectQuery) onSelectQuery(presets[0].query);
            }}
            className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
              activePreset === 'leave'
                ? 'bg-emerald-50/80 border-emerald-600 shadow-sm'
                : 'bg-white border-slate-200 hover:border-slate-300 opacity-70 hover:opacity-100'
            }`}
          >
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-600" />
              <span className="font-display font-bold text-xs text-slate-900">Leave Agent</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Validates EL/CL/SL balances, checks overlap, records audit entries.
            </p>
          </div>

          <div
            onClick={() => {
              setActivePreset('policy');
              if (onSelectQuery) onSelectQuery(presets[1].query);
            }}
            className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
              activePreset === 'policy'
                ? 'bg-emerald-50/80 border-emerald-600 shadow-sm'
                : 'bg-white border-slate-200 hover:border-slate-300 opacity-70 hover:opacity-100'
            }`}
          >
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-600" />
              <span className="font-display font-bold text-xs text-slate-900">HR Policy Agent</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Queries Neo4j & Maharashtra 2017 Graph RAG with citations.
            </p>
          </div>

          <div
            onClick={() => {
              setActivePreset('timesheet');
              if (onSelectQuery) onSelectQuery(presets[2].query);
            }}
            className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
              activePreset === 'timesheet'
                ? 'bg-emerald-50/80 border-emerald-600 shadow-sm'
                : 'bg-white border-slate-200 hover:border-slate-300 opacity-70 hover:opacity-100'
            }`}
          >
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-600" />
              <span className="font-display font-bold text-xs text-slate-900">Timesheet Agent</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Checks 9h daily/48h weekly limits, alerts overtime, triggers manager approvals.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
