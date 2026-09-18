import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { AgentChatResponse, StructuredAction } from '../types';
import {
  X, Send, Bot, Shield, ShieldAlert, Sparkles, CheckCircle2,
  FileText, ArrowRight, CornerDownLeft, AlertTriangle
} from 'lucide-react';

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onActionExecuted?: () => void;
}

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  agentRouted?: string;
  guardrailStatus?: string;
  guardrailTripped?: string;
  citations?: any[];
  structuredAction?: StructuredAction;
  latencyMs?: number;
}

export const AgentChatDrawer: React.FC<ChatDrawerProps> = ({ isOpen, onClose, onActionExecuted }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: 'Hello! I am your Google ADK HR Multi-Agent Assistant protected by NVIDIA NeMo Guardrails. How can I help you today?',
      agentRouted: 'ROOT_ORCHESTRATOR',
      guardrailStatus: 'PASSED',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [executingAction, setExecutingAction] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const userMsgText = input.trim();
    setInput('');

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: userMsgText,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const resp: AgentChatResponse = await api.chatWithAgent(userMsgText);
      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: resp.response,
        agentRouted: resp.agent_routed,
        guardrailStatus: resp.guardrail_status,
        guardrailTripped: resp.guardrail_tripped,
        citations: resp.citations,
        structuredAction: resp.structured_action,
        latencyMs: resp.latency_ms,
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'agent',
          text: `Error connecting to multi-agent backend: ${err.message || 'Unknown error'}`,
          guardrailStatus: 'ERROR',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExecuteAction = async (action: StructuredAction) => {
    setExecutingAction(true);
    try {
      if (action.action_type === 'LEAVE_APPLY') {
        await api.applyLeave(action.action_payload as any);
        alert('✅ Leave application successfully submitted to your manager!');
      } else if (action.action_type === 'TIMESHEET_LOG') {
        await api.logTimesheet(action.action_payload as any);
        alert('✅ Timesheet hours logged successfully!');
      }
      if (onActionExecuted) onActionExecuted();
    } catch (err: any) {
      alert(`Action failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setExecutingAction(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white shadow-2xl border-l border-slate-200 flex flex-col">
      {/* Drawer Header */}
      <div className="px-6 py-4 bg-gradient-to-r from-slate-900 to-slate-800 text-white flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-sm">HR Multi-Agent Assistant</h3>
            <p className="text-xs text-slate-300">Google ADK &bull; NeMo Guardrails</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Agent Header & Safety Badge */}
            {m.sender === 'agent' && (
              <div className="flex items-center gap-2 mb-1 px-1 text-xs">
                <span className="font-semibold text-slate-700 flex items-center gap-1">
                  <Bot className="w-3.5 h-3.5 text-emerald-600" />
                  {m.agentRouted || 'ORCHESTRATOR'}
                </span>
                {m.guardrailStatus === 'INPUT_BLOCKED' && (
                  <span className="flex items-center gap-1 bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                    <ShieldAlert className="w-3 h-3" />
                    NeMo: Blocked
                  </span>
                )}
                {m.guardrailStatus === 'OUTPUT_SCRUBBED' && (
                  <span className="flex items-center gap-1 bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full font-medium">
                    <Shield className="w-3 h-3" />
                    DPDP Masked
                  </span>
                )}
                {m.guardrailStatus === 'PASSED' && (
                  <span className="flex items-center gap-1 bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">
                    <Shield className="w-3 h-3" />
                    NeMo: Safe
                  </span>
                )}
                {m.latencyMs && (
                  <span className="text-slate-400 text-[10px]">{Math.round(m.latencyMs)}ms</span>
                )}
              </div>
            )}

            {/* Bubble */}
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-emerald-600 text-white rounded-br-none shadow-sm'
                  : 'bg-white text-slate-800 rounded-bl-none border border-slate-200 shadow-sm'
              }`}
            >
              <div className="whitespace-pre-wrap">{m.text}</div>

              {/* Citations Card */}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5">
                  <div className="text-xs font-bold text-slate-600 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5 text-blue-600" />
                    Authoritative Citations:
                  </div>
                  {m.citations.map((c, idx) => (
                    <div
                      key={idx}
                      className="bg-blue-50 border border-blue-100 rounded-lg p-2 text-xs text-blue-900"
                    >
                      <div className="font-semibold flex items-center justify-between">
                        <span>{c.source_title}</span>
                        <span className="bg-blue-200/60 px-1.5 py-0.5 rounded text-[10px] font-bold">
                          {c.document_type}
                        </span>
                      </div>
                      <div className="text-blue-700 mt-0.5">{c.citation_text}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Structured Action Proposal */}
              {m.structuredAction && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3">
                    <div className="flex items-center gap-2 text-emerald-900 font-semibold text-xs mb-1">
                      <Sparkles className="w-4 h-4 text-emerald-600" />
                      Proposed Action: {m.structuredAction.action_type}
                    </div>
                    <pre className="text-[11px] bg-white p-2 rounded border border-emerald-100 text-slate-700 overflow-x-auto mb-2 font-mono">
                      {JSON.stringify(m.structuredAction.action_payload, null, 2)}
                    </pre>
                    {m.structuredAction.requires_confirmation && (
                      <button
                        onClick={() => handleExecuteAction(m.structuredAction!)}
                        disabled={executingAction}
                        className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        Confirm & Execute Action
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-slate-500 italic p-2">
            <Bot className="w-4 h-4 text-emerald-600 animate-spin" />
            Routing through Google ADK and evaluating NeMo Guardrails...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="p-4 bg-white border-t border-slate-200">
        <div className="flex items-center gap-2 bg-slate-100 rounded-xl p-1.5 border border-slate-200 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask leave rules, apply for leave, or log hours..."
            className="flex-1 bg-transparent px-3 py-1.5 text-sm text-slate-900 focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500">
          <span>Protected by NeMo Guardrails &bull; DPDP Masked</span>
          <span>Press Enter to send</span>
        </div>
      </div>
    </div>
  );
};
