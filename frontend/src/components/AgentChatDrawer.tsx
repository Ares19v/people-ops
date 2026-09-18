import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { AgentChatResponse, StructuredAction } from '../types';
import {
  X, Send, Bot, Shield, ShieldAlert, Sparkles, CheckCircle2,
  FileText, ArrowRight, CornerDownLeft, AlertTriangle, ShieldCheck
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
      text: 'Hello! I am your Google ADK HR Multi-Agent Assistant protected by NVIDIA NeMo Guardrails. Ask me about leave balances, Maharashtra labour laws, timesheet rules, or onboarding.',
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
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col">
      {/* Drawer Header */}
      <div className="px-5 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-display font-bold text-sm tracking-tight">HR Multi-Agent Assistant</h3>
            <p className="text-[11px] text-slate-400">Google ADK &bull; NeMo Guardrails</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/70">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Agent Header & Safety Badge */}
            {m.sender === 'agent' && (
              <div className="flex items-center gap-2 mb-1 px-1 text-xs">
                <span className="font-display font-semibold text-slate-700 flex items-center gap-1 text-[11px]">
                  <Bot className="w-3.5 h-3.5 text-blue-600" />
                  {m.agentRouted || 'ORCHESTRATOR'}
                </span>
                {m.guardrailStatus === 'INPUT_BLOCKED' && (
                  <span className="badge-statutory-red text-[10px]">
                    <ShieldAlert className="w-3 h-3" />
                    NeMo: Blocked
                  </span>
                )}
                {m.guardrailStatus === 'OUTPUT_SCRUBBED' && (
                  <span className="badge-statutory-amber text-[10px]">
                    <Shield className="w-3 h-3" />
                    DPDP Masked
                  </span>
                )}
                {m.guardrailStatus === 'PASSED' && (
                  <span className="badge-statutory-green text-[10px]">
                    <ShieldCheck className="w-3 h-3" />
                    NeMo: Safe
                  </span>
                )}
                {m.latencyMs && (
                  <span className="text-slate-400 text-[10px] font-mono">{Math.round(m.latencyMs)}ms</span>
                )}
              </div>
            )}

            {/* Bubble */}
            <div
              className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none shadow-sm'
                  : 'bg-white text-slate-800 rounded-bl-none border border-slate-200 shadow-sm'
              }`}
            >
              <div className="whitespace-pre-wrap">{m.text}</div>

              {/* Citations Card */}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5">
                  <div className="text-[11px] font-display font-bold text-slate-600 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5 text-blue-600" />
                    Authoritative Citations:
                  </div>
                  {m.citations.map((c, idx) => (
                    <div
                      key={idx}
                      className="bg-blue-50/70 border border-blue-100 rounded-xl p-2 text-[11px] text-blue-900"
                    >
                      <div className="font-semibold flex items-center justify-between">
                        <span>{c.source_title}</span>
                        <span className="bg-blue-200/60 px-1.5 py-0.5 rounded text-[9px] font-bold">
                          {c.document_type}
                        </span>
                      </div>
                      <div className="text-blue-700 mt-0.5 font-mono text-[10px]">{c.citation_text}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Structured Action Execution Button */}
              {m.structuredAction && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <button
                    onClick={() => handleExecuteAction(m.structuredAction!)}
                    disabled={executingAction}
                    className="w-full btn-pill-dark text-xs py-2 justify-center"
                  >
                    <span>Execute Action: {m.structuredAction.action_type}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-slate-400 text-xs pl-2">
            <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" />
            <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]" />
            <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]" />
            <span className="font-display font-semibold text-[11px]">Evaluating NeMo rails & agent intent...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Tray */}
      <div className="p-3.5 bg-white border-t border-slate-200">
        <div className="flex items-center gap-2 bg-slate-50 p-1.5 rounded-2xl border border-slate-200 focus-within:bg-white focus-within:border-blue-600 transition-all">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask anything or request action..."
            className="flex-1 bg-transparent px-3 py-1.5 text-xs text-slate-900 focus:outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="btn-pill-dark px-3 py-1.5 text-xs"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
