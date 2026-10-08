import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { AgentChatResponse, StructuredAction } from '../types';
import {
  X, Send, Bot, Shield, ShieldAlert, Sparkles, CheckCircle2,
  FileText, ArrowRight, CornerDownLeft, AlertTriangle, ShieldCheck, RotateCcw,
  Maximize2, Minimize2, Calendar, Clock, RefreshCw
} from 'lucide-react';
import { FeatureExplainerIcon } from './FeatureExplainerIcon';

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onActionExecuted?: () => void;
  initialPrompt?: string;
  initialFullScreen?: boolean;
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

const formatAgentName = (routed?: string) => {
  if (!routed) return 'Root LLM Orchestrator';
  switch (routed.toUpperCase()) {
    case 'ROOT_LLM_ORCHESTRATOR':
    case 'ROOT_ORCHESTRATOR':
      return 'Root LLM Orchestrator';
    case 'HEALTH_SUBAGENT':
    case 'HEALTH_AGENT':
      return 'Occupational Health Subagent';
    case 'ZOHO_SUBAGENT':
      return 'Zoho People Subagent';
    case 'LEAVE_SUBAGENT':
    case 'LEAVE_AGENT':
      return 'Leave Subagent';
    case 'TIMESHEET_SUBAGENT':
    case 'TIMESHEET_AGENT':
      return 'Timesheet Subagent';
    case 'POLICY_RAG_SUBAGENT':
    case 'POLICY_AGENT':
      return 'Policy Graph RAG Subagent';
    default:
      return routed.replace(/_/g, ' ');
  }
};

export const PeopleOpsLogo: React.FC<{
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  showDot?: boolean;
}> = ({ size = 'md', className = '', showDot = true }) => {
  const sizeMap = {
    xs: 'w-5 h-5 rounded-md',
    sm: 'w-7 h-7 rounded-lg',
    md: 'w-8.5 h-8.5 rounded-xl',
    lg: 'w-11 h-11 rounded-2xl',
    xl: 'w-16 h-16 rounded-2xl',
  };
  const iconSizeMap = {
    xs: 12,
    sm: 14,
    md: 18,
    lg: 24,
    xl: 32,
  };
  const dotSizeMap = {
    xs: 'w-1.5 h-1.5 -bottom-0.5 -right-0.5',
    sm: 'w-2 h-2 -bottom-0.5 -right-0.5',
    md: 'w-2.5 h-2.5 -bottom-0.5 -right-0.5',
    lg: 'w-3 h-3 -bottom-0.5 -right-0.5',
    xl: 'w-4 h-4 -bottom-1 -right-1',
  };

  return (
    <div
      className={`relative flex items-center justify-center bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-900 text-white shadow-sm border border-blue-400/30 shrink-0 ${sizeMap[size]} ${className}`}
    >
      <Bot size={iconSizeMap[size]} className="text-white drop-shadow-xs" />
      {showDot && (
        <span
          className={`absolute rounded-full bg-emerald-400 border-[1.5px] border-slate-900 ${dotSizeMap[size]}`}
        />
      )}
    </div>
  );
};

const STARTER_PROMPTS = [
  {
    title: 'Verified Leave Balances',
    description: 'Check available EL, CL, SL, and LWP quotas',
    prompt: 'Check my leave balances and available PTO days',
    icon: Calendar,
  },
  {
    title: 'Maharashtra Labour Law',
    description: 'Overtime compensation rules & 2.0x wage mandate',
    prompt: 'What are overtime wage rules under Section 13 & 14 of Maharashtra Act 2017?',
    icon: Clock,
  },
  {
    title: 'Medical Absence & Doctor Note',
    description: 'Fever triage and medical certification thresholds',
    prompt: 'Employee has fever for 4 days, is a doctor certificate required?',
    icon: ShieldCheck,
  },
  {
    title: 'Zoho People HRMS Sync',
    description: 'Synchronize live external attendance and leaves',
    prompt: 'Sync my attendance and leave records with Zoho People API',
    icon: RefreshCw,
  },
];

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  sender: 'agent',
  text: 'Hello! I am your PeopleOps AI Assistant. How can I assist you with leaves, timesheets, or labour policies today?',
  agentRouted: 'ROOT_LLM_ORCHESTRATOR',
  guardrailStatus: 'PASSED',
};

interface FormattedMessageProps {
  text: string;
}

const FormattedAgentMessage: React.FC<FormattedMessageProps> = ({ text }) => {
  // 1. Sanitize text: strip hashtags, stars, blockquote signs, stray pipe dividers
  const sanitized = text
    .replace(/^[ \t]*#{1,6}[ \t]*/gm, '') // Remove heading hashtags
    .replace(/\*{1,3}(.*?)\*{1,3}/g, '$1') // Remove bold/italic markdown
    .replace(/^[ \t]*>[ \t]*/gm, '') // Remove blockquote markers
    .replace(/\*\*/g, '') // Remove double asterisks
    .replace(/\*/g, '') // Remove single asterisks
    .trim();

  // Split into raw lines
  const rawLines = sanitized.split('\n');

  // Group into blocks: Headers, Lists, Key-Value balance items, Disclaimers, Tables, Paragraphs
  const blocks: Array<{
    type: 'header' | 'list' | 'balance-cards' | 'disclaimer' | 'paragraph' | 'table';
    title?: string;
    items?: Array<{ label: string; value?: string; detail?: string; fullText: string }>;
    content?: string;
    rows?: string[][];
  }> = [];

  let currentList: Array<{ label: string; value?: string; detail?: string; fullText: string }> = [];
  let isBalanceList = false;

  const flushList = () => {
    if (currentList.length > 0) {
      blocks.push({
        type: isBalanceList ? 'balance-cards' : 'list',
        items: [...currentList],
      });
      currentList = [];
      isBalanceList = false;
    }
  };

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i].trim();
    if (!line) {
      flushList();
      continue;
    }

    // Check if line is a table divider like |---|---|
    if (/^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$/.test(line)) {
      continue;
    }

    // Check if line is a table row with pipes | col1 | col2 |
    if (line.startsWith('|') && line.endsWith('|') && line.split('|').length > 2) {
      flushList();
      const cells = line.split('|').map((c) => c.trim()).filter(Boolean);
      const tableRows: string[][] = [cells];
      while (i + 1 < rawLines.length && rawLines[i + 1].trim().startsWith('|')) {
        i++;
        const nextLine = rawLines[i].trim();
        if (!/^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$/.test(nextLine)) {
          const nextCells = nextLine.split('|').map((c) => c.trim()).filter(Boolean);
          if (nextCells.length > 0) tableRows.push(nextCells);
        }
      }
      blocks.push({ type: 'table', rows: tableRows });
      continue;
    }

    // Check if line is a Disclaimer / Statutory / Legal / HITL note
    const isDisclaimer =
      /^(statutory\s*(note|disclaimer)|clinical\s*(&|and)\s*hipaa\s*note|clinical\s*disclaimer|human-in-the-loop\s*checkpoint|notice):/i.test(
        line
      ) ||
      line.includes('does not constitute formal legal advice') ||
      line.includes('This response reflects company policy and the Maharashtra');

    if (isDisclaimer) {
      flushList();
      let disclaimerTitle = 'Statutory Note';
      let disclaimerBody = line;

      const colonIdx = line.indexOf(':');
      if (colonIdx > 0 && colonIdx < 40) {
        disclaimerTitle = line.substring(0, colonIdx).trim();
        disclaimerBody = line.substring(colonIdx + 1).trim();
      }
      blocks.push({
        type: 'disclaimer',
        title: disclaimerTitle,
        content: disclaimerBody,
      });
      continue;
    }

    // Check if line is a bullet item (•, -, or numbered 1., 2.)
    const bulletMatch = line.match(/^([•\-\*]|\d+\.)\s+(.+)$/);
    if (bulletMatch) {
      const itemText = bulletMatch[2].trim();
      const colonSplit = itemText.indexOf(':');

      if (colonSplit > 0 && colonSplit < 40 && !itemText.toLowerCase().includes('http')) {
        const rawLabel = itemText.substring(0, colonSplit).trim();
        const rawRemainder = itemText.substring(colonSplit + 1).trim();

        // Check if rawRemainder contains a trailing parenthesized detail, e.g. "Uncapped (Discretionary management approval)"
        // or "19.0 days (Accrues monthly; max accumulation 45 days)"
        let parsedVal = rawRemainder;
        let parsedDetail: string | undefined = undefined;

        const parenMatch = rawRemainder.match(/^([^(]+?)\s*\(([^()]+)\)$/);
        if (parenMatch) {
          parsedVal = parenMatch[1].trim();
          parsedDetail = parenMatch[2].trim();
        }

        // Check if parsedVal qualifies as a metric/balance card value:
        // 1. Numeric with optional units: e.g. "19.0 days", "7.0 days", "40.0 hrs", "100%", "4 entries"
        // 2. Short status/allowance terms: e.g. "Uncapped", "Unlimited", "Approved", "Pending", "Exempt", "None", "Active"
        const isNumericMetric = /^[0-9.,₹$]+\s*(?:days?|hrs?|hours?|%|d\b|[a-zA-Z]+)?$/i.test(parsedVal);
        const isStatusWord = /^(uncapped|unlimited|exempt|approved|pending|rejected|active|yes|no|none|na|n\/a|valid|eligible)$/i.test(parsedVal);
        const isShortMetric = (parsedVal.length <= 16 && (isNumericMetric || isStatusWord || parsedDetail !== undefined));

        if (isShortMetric) {
          isBalanceList = true;
          currentList.push({
            label: rawLabel,
            value: parsedVal,
            detail: parsedDetail,
            fullText: itemText,
          });
        } else {
          currentList.push({
            label: rawLabel,
            value: rawRemainder,
            fullText: itemText,
          });
        }
      } else {
        currentList.push({
          label: '',
          fullText: itemText,
        });
      }
      continue;
    }

    // Not a bullet point. If we were collecting bullets, flush.
    flushList();

    // Check if line is a section heading (short, ends with a colon, or has header emoji)
    if (
      (line.endsWith(':') && line.length < 80) ||
      (/^(\u23f1|\ud83d\udccb|\ud83d\udcca|\u26a0\ufe0f|[A-Z\s]{3,})\s/i.test(line) && line.endsWith(':'))
    ) {
      blocks.push({
        type: 'header',
        content: line.replace(/:$/, ''),
      });
      continue;
    }

    // Normal paragraph
    blocks.push({
      type: 'paragraph',
      content: line,
    });
  }

  flushList();

  return (
    <div className="space-y-2.5 text-xs">
      {blocks.map((block, bIdx) => {
        if (block.type === 'header') {
          return (
            <div
              key={bIdx}
              className="font-semibold text-slate-900 text-[13px] tracking-tight pb-1 border-b border-slate-100 flex items-center gap-1.5"
            >
              <span>{block.content}</span>
            </div>
          );
        }

        if (block.type === 'balance-cards') {
          return (
            <div key={bIdx} className="grid grid-cols-1 gap-1.5 my-1.5">
              {block.items?.map((item, iIdx) => (
                <div
                  key={iIdx}
                  className="p-2.5 rounded-xl bg-slate-50/90 border border-slate-200/70 hover:bg-white hover:border-blue-200 transition-all shadow-2xs overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-2 min-w-0">
                    <span className="font-semibold text-slate-800 text-xs tracking-tight min-w-0 flex-1 truncate">
                      {item.label}
                    </span>
                    {item.value && (
                      <span className="font-bold text-blue-700 bg-blue-50/80 border border-blue-200/60 px-2 py-0.5 rounded-lg text-[11px] shrink-0 max-w-[45%] text-right truncate">
                        {item.value}
                      </span>
                    )}
                  </div>
                  {item.detail && (
                    <div className="text-[11px] text-slate-500 mt-1 leading-normal break-words">
                      {item.detail}
                    </div>
                  )}
                  {!item.value && !item.detail && (
                    <div className="text-xs text-slate-700 break-words">{item.fullText}</div>
                  )}
                </div>
              ))}
            </div>
          );
        }

        if (block.type === 'list') {
          return (
            <div key={bIdx} className="space-y-1.5 my-1">
              {block.items?.map((item, iIdx) => (
                <div key={iIdx} className="flex items-start gap-2 text-xs text-slate-700 leading-relaxed min-w-0">
                  <span className="text-blue-500 font-bold shrink-0 mt-0.5">•</span>
                  <div className="min-w-0 flex-1 break-words">
                    {item.label ? (
                      <>
                        <span className="font-semibold text-slate-800">{item.label}: </span>
                        <span>{item.value || item.fullText}</span>
                      </>
                    ) : (
                      <span>{item.fullText}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          );
        }

        if (block.type === 'table') {
          return (
            <div key={bIdx} className="my-2 space-y-1 overflow-x-auto max-w-full">
              {block.rows?.map((row, rIdx) => (
                <div
                  key={rIdx}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100 text-xs gap-2 min-w-0"
                >
                  <span className="font-semibold text-slate-800 truncate min-w-0">{row[0]}</span>
                  <span className="text-slate-600 font-medium text-[11px] shrink-0 text-right">
                    {row.slice(1).join(' · ')}
                  </span>
                </div>
              ))}
            </div>
          );
        }

        if (block.type === 'disclaimer') {
          return (
            <div
              key={bIdx}
              className="mt-3 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-500 leading-relaxed flex items-start gap-2 overflow-hidden break-words"
            >
              <ShieldCheck className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1 break-words">
                <span className="font-semibold text-slate-700 block mb-0.5">
                  {block.title}
                </span>
                <span>{block.content}</span>
              </div>
            </div>
          );
        }

        return (
          <p key={bIdx} className="text-xs text-slate-700 leading-relaxed break-words">
            {block.content}
          </p>
        );
      })}
    </div>
  );
};

const getStepsForQuery = (query: string): string[] => {
  const q = query.toLowerCase();
  if (q.includes('leave') || q.includes('vacation') || q.includes('cl') || q.includes('el') || q.includes('sl') || q.includes('holiday') || q.includes('day off')) {
    return [
      'Evaluating query intent & checking NeMo Guardrails...',
      'Encrypting employee identifiers into Zero-PII Vault...',
      'Delegating to Leave Specialist Agent & reading ledger balances...',
      'Auditing statutory leave limits under Shops & Establishments Act...',
      'Synthesizing verified leave decision & actions...',
    ];
  }
  if (q.includes('timesheet') || q.includes('hour') || q.includes('overtime') || q.includes('project') || q.includes('billable')) {
    return [
      'Evaluating query intent & checking NeMo Guardrails...',
      'Accessing Timesheet Service & querying project allocations...',
      'Auditing statutory overtime thresholds (9h daily / 48h weekly)...',
      'Validating double-rate wage compensation (Section 13)...',
      'Synthesizing timesheet audit report...',
    ];
  }
  if (q.includes('sick') || q.includes('health') || q.includes('fever') || q.includes('doctor') || q.includes('medical') || q.includes('hospital')) {
    return [
      'Evaluating clinical emergency triage & NeMo Guardrails...',
      'Scrubbing confidential health markers (HIPAA Safe Harbor)...',
      'Consulting Occupational Health protocol & ESI Act regulations...',
      'Evaluating doctor certification requirements (>2 days)...',
      'Synthesizing clinical support guidance...',
    ];
  }
  if (q.includes('zoho') || q.includes('sync') || q.includes('attendance')) {
    return [
      'Evaluating query intent & checking NeMo Guardrails...',
      'Initiating bi-directional Zoho People REST v2 sync...',
      'Querying attendance records & remote logs...',
      'Reconciling external HRMS payload with local ledger...',
      'Finalizing synchronized records display...',
    ];
  }
  if (q.includes('policy') || q.includes('rule') || q.includes('act') || q.includes('law') || q.includes('maharashtra') || q.includes('karnataka') || q.includes('delhi')) {
    return [
      'Evaluating query intent & checking NeMo Guardrails...',
      'Querying NetworkX Policy Graph & ChromaDB Hybrid RAG...',
      'Evaluating state statutory mandates (Maharashtra/Karnataka/Delhi)...',
      'Verifying legal invariants with Adversarial Statutory Critic...',
      'Extracting authoritative citations & synthesizing response...',
    ];
  }
  return [
    'Evaluating query intent & verifying safety guardrails...',
    'Scrubbing sensitive identifiers into Zero-PII Token Vault...',
    'Routing request to autonomous Google ADK Multi-Agent Fleet...',
    'Consulting statutory compliance rules & enterprise policy...',
    'Synthesizing verified response & action items...',
  ];
};

export const AgentChatDrawer: React.FC<ChatDrawerProps> = ({
  isOpen,
  onClose,
  onActionExecuted,
  initialPrompt,
  initialFullScreen = false,
}) => {
  const [sessionId, setSessionId] = useState<string>(() => {
    let saved = localStorage.getItem('chat_session_id');
    if (!saved) {
      saved = `sess_${Math.random().toString(36).substring(2, 10)}`;
      localStorage.setItem('chat_session_id', saved);
    }
    return saved;
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [loadingStepsList, setLoadingStepsList] = useState<string[]>([]);
  const [executingAction, setExecutingAction] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(initialFullScreen);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && initialFullScreen) {
      setIsFullScreen(true);
    }
  }, [isOpen, initialFullScreen]);

  // Fluid step progression timer while loading
  useEffect(() => {
    let interval: any = null;
    if (isLoading && loadingStepsList.length > 0) {
      interval = setInterval(() => {
        setLoadingStep((prev) => {
          if (prev < loadingStepsList.length - 1) {
            return prev + 1;
          }
          return prev;
        });
      }, 950);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading, loadingStepsList]);

  // Load past conversation history from PostgreSQL checkpoint / memory on open
  useEffect(() => {
    let isSubscribed = true;
    const loadConversationHistory = async () => {
      try {
        const mem = await api.getChatMemory(sessionId);
        if (isSubscribed && mem && mem.history && mem.history.length > 0) {
          const loaded: Message[] = mem.history.map((turn, index) => ({
            id: `persisted_${index}_${Date.now()}`,
            sender: turn.role === 'user' ? 'user' : 'agent',
            text: turn.content,
            agentRouted: turn.role === 'user' ? undefined : 'ROOT_LLM_ORCHESTRATOR',
            guardrailStatus: 'PASSED',
          }));
          setMessages(loaded);
        }
      } catch (err) {
        console.warn('Notice: Could not load past session memory:', err);
      }
    };

    if (isOpen) {
      loadConversationHistory();
    }

    return () => {
      isSubscribed = false;
    };
  }, [sessionId, isOpen]);

  const quickPrompts = [
    { label: 'Leave balances', prompt: 'Check my leave balances and available PTO days' },
    { label: 'Maharashtra max hours', prompt: 'What is daily max hours under Maharashtra Act 2017?' },
    { label: 'Doctor certificate rule', prompt: 'Employee has fever for 4 days, do I need a doctor certificate?' },
    { label: 'Sync Zoho People', prompt: 'Sync my attendance and leave records with Zoho People API' },
  ];

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (isFullScreen) {
          setIsFullScreen(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isFullScreen, onClose]);

  // Reset fullscreen when drawer is closed
  useEffect(() => {
    if (!isOpen) {
      setIsFullScreen(false);
    }
  }, [isOpen]);

  // If initialPrompt provided when drawer opens, populate input
  useEffect(() => {
    if (isOpen && initialPrompt) {
      setInput(initialPrompt);
    }
  }, [isOpen, initialPrompt]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleResetConversation = async () => {
    try {
      await api.clearChatMemory(sessionId);
    } catch (err) {
      // Ignore
    }
    const newSessionId = `sess_${Math.random().toString(36).substring(2, 10)}`;
    localStorage.setItem('chat_session_id', newSessionId);
    setSessionId(newSessionId);
    setMessages([]);
  };

  const handleSendText = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return;
    const userMsgText = textToSend.trim();
    setInput('');

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: userMsgText,
    };
    setMessages((prev) => [...prev, userMsg]);

    const steps = getStepsForQuery(userMsgText);
    setLoadingStepsList(steps);
    setLoadingStep(0);
    setIsLoading(true);

    try {
      const resp: AgentChatResponse = await api.chatWithAgent(userMsgText, sessionId);
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
    <>
      {!isFullScreen && (
        <div
          className="fixed inset-0 z-40 popup-screen-blur"
          onClick={onClose}
        />
      )}
      <div
        className={`fixed z-50 bg-white flex flex-col transition-all duration-300 ease-in-out ${
          isFullScreen
            ? 'inset-0 w-full h-full shadow-none'
            : 'inset-y-0 right-0 w-full max-w-md shadow-2xl border-l border-slate-200'
        }`}
      >
      {/* Drawer Header - Formal & Minimalist Executive Styling */}
      <div className="px-5 py-3.5 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800/80 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-display font-semibold text-[13px] tracking-tight text-white">PeopleOps AI</h3>
            <FeatureExplainerIcon featureKey="agent_root_orchestrator" />
          </div>
          <p className="text-[10px] text-slate-400 font-normal">Enterprise People & HR Intelligence</p>
        </div>
        <div className="flex items-center gap-1 text-slate-400">
          <button
            onClick={handleResetConversation}
            title="New Conversation"
            className="hover:text-white p-1.5 rounded-lg transition-colors hover:bg-slate-800/80 outline-none"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsFullScreen((prev) => !prev)}
            title={isFullScreen ? "Collapse to Drawer (Esc)" : "Expand to Fullscreen"}
            className="hover:text-white p-1.5 rounded-lg transition-colors hover:bg-slate-800/80 outline-none"
          >
            {isFullScreen ? (
              <Minimize2 className="w-3.5 h-3.5" />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" />
            )}
          </button>
          <FeatureExplainerIcon featureKey="agent_persistent_memory" />
          <button
            onClick={onClose}
            title="Close"
            className="hover:text-white p-1.5 rounded-lg transition-colors hover:bg-slate-800/80 ml-0.5 outline-none"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Body: ChatGPT Floating Mid-Air Hero OR Conversational Stream */}
      {messages.length === 0 ? (
        <div className="flex-1 overflow-y-auto flex flex-col justify-center items-center p-6 sm:p-10 bg-gradient-to-b from-white via-slate-50/50 to-slate-100/30">
          <div className="max-w-2xl w-full mx-auto flex flex-col items-center text-center my-auto py-6">
            {/* Formal Minimalist Typography */}
            <h2 className="font-display font-bold text-2xl sm:text-3xl text-slate-900 tracking-tight mb-2">
              How can PeopleOps assist you today?
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 max-w-md mx-auto mb-8 font-normal leading-relaxed">
              Autonomous workforce intelligence for leave allocations, statutory compliance, clinical triage, and HRMS records.
            </p>

            {/* Floating Mid-Air Input Box (ChatGPT style) */}
            <div className="w-full mb-8">
              <div className="relative flex items-center bg-white rounded-2xl border border-slate-200/90 shadow-md hover:shadow-lg focus-within:shadow-xl focus-within:border-blue-600 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all p-2 pl-4">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && input.trim()) {
                      handleSendText(input);
                    }
                  }}
                  placeholder="Message PeopleOps AI or ask an HR question..."
                  className="flex-1 bg-transparent text-xs sm:text-sm text-slate-900 placeholder-slate-400 outline-none focus:outline-none pr-3"
                  autoFocus
                />
                <button
                  onClick={() => handleSendText(input)}
                  disabled={!input.trim() || isLoading}
                  className={`p-2.5 rounded-xl transition-all ${
                    input.trim() && !isLoading
                      ? 'bg-slate-900 text-white hover:bg-blue-600 shadow-sm cursor-pointer'
                      : 'bg-slate-100 text-slate-300 cursor-not-allowed'
                  }`}
                  title="Send message"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2.5 text-[11px] text-slate-400 flex items-center justify-center gap-2">
                <span>Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[10px] border border-slate-200 shadow-2xs">Enter ↵</kbd> to ask</span>
                <span>&bull;</span>
                <span>Protected by NVIDIA NeMo Guardrails & DPDP Act</span>
              </div>
            </div>

            {/* Starter Suggestion Prompt Cards (2x2 Grid) */}
            <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
              {STARTER_PROMPTS.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => handleSendText(item.prompt)}
                    disabled={isLoading}
                    className="group p-3.5 rounded-xl bg-white/90 hover:bg-white border border-slate-200/80 hover:border-blue-400/80 hover:shadow-md transition-all duration-200 flex items-start gap-3 outline-none focus:outline-none text-left"
                  >
                    <div className="w-8 h-8 rounded-lg bg-blue-50 group-hover:bg-blue-600 text-blue-600 group-hover:text-white flex items-center justify-center shrink-0 transition-colors">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-display font-semibold text-xs text-slate-800 group-hover:text-blue-600 transition-colors">
                        {item.title}
                      </div>
                      <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                        {item.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Messages List */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 bg-slate-50/70">
            <div className={`mx-auto w-full space-y-4 ${isFullScreen ? 'max-w-4xl' : ''}`}>
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
                >
                  {/* Agent Header & Safety Badge */}
                  {m.sender === 'agent' && (
                    <div className="flex items-center gap-2 mb-1 px-1 text-xs">
                      <span className="font-display font-semibold text-slate-700 text-[11px] bg-white px-2.5 py-0.5 rounded-lg border border-slate-200/80 shadow-2xs">
                        {formatAgentName(m.agentRouted)}
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
                        <span className="badge-statutory-green text-[10px] inline-flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3" />
                          NeMo: Safe
                          <FeatureExplainerIcon featureKey="agent_nemo_guardrails" />
                        </span>
                      )}
                      {m.latencyMs && (
                        <span className="text-slate-400 text-[10px] font-mono">{Math.round(m.latencyMs)}ms</span>
                      )}
                    </div>
                  )}

                  {/* Bubble */}
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-relaxed min-w-0 overflow-hidden break-words ${
                      m.sender === 'user'
                        ? 'bg-blue-600 text-white rounded-br-none shadow-sm'
                        : 'bg-white text-slate-800 rounded-bl-none border border-slate-200 shadow-sm'
                    }`}
                  >
                    {m.sender === 'agent' ? (
                      <FormattedAgentMessage text={m.text} />
                    ) : (
                      <div className="whitespace-pre-wrap">{m.text}</div>
                    )}

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
                            className="bg-blue-50/70 border border-blue-100 rounded-xl p-2 text-[11px] text-blue-900 overflow-hidden"
                          >
                            <div className="font-semibold flex items-center justify-between gap-2 min-w-0">
                              <span className="truncate flex-1 min-w-0">{c.source_title}</span>
                              <span className="bg-blue-200/60 px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0">
                                {c.document_type}
                              </span>
                            </div>
                            <div className="text-blue-700 mt-0.5 font-mono text-[10px] break-words">{c.citation_text}</div>
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
                <div className="mx-2 my-2 p-3.5 rounded-2xl bg-gradient-to-br from-slate-50/95 to-blue-50/40 border border-slate-200/80 shadow-xs backdrop-blur-xs transition-all duration-300">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className="relative flex items-center justify-center w-5 h-5 rounded-full bg-blue-600/10 text-blue-600">
                        <Sparkles className="w-3 h-3 animate-spin [animation-duration:4s]" />
                        <span className="absolute inset-0 rounded-full bg-blue-500/20 animate-ping opacity-60" />
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-600 gemini-dot-1" />
                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 gemini-dot-2" />
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 gemini-dot-3" />
                      </div>
                    </div>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold font-mono tracking-tight bg-blue-100/70 text-blue-700 border border-blue-200/50">
                      Step {Math.min(loadingStep + 1, loadingStepsList.length || 5)} of {loadingStepsList.length || 5}
                    </span>
                  </div>
                  <div className="min-h-[22px] flex items-center">
                    <span
                      key={loadingStep}
                      className="step-fade-in font-display font-medium text-[12px] text-slate-800 leading-snug tracking-tight"
                    >
                      {loadingStepsList[loadingStep] || 'Evaluating query intent & guardrails...'}
                    </span>
                  </div>
                  <div className="mt-2.5 w-full bg-slate-200/70 rounded-full h-1 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-600 via-indigo-500 to-cyan-500 rounded-full transition-all duration-700 ease-out"
                      style={{
                        width: `${Math.min(100, (((loadingStep + 1) / (loadingStepsList.length || 5)) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Quick Suggestion Prompts - Clean wrap, no scroller */}
          <div className="px-3.5 py-2 bg-slate-50/90 border-t border-slate-200/80 shrink-0">
            <div
              className={`mx-auto w-full flex flex-wrap items-center gap-1.5 no-scrollbar ${
                isFullScreen ? 'max-w-4xl' : ''
              }`}
            >
              {quickPrompts.map((qp, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendText(qp.prompt)}
                  disabled={isLoading}
                  title={qp.prompt}
                  className="text-[11px] font-medium text-slate-700 bg-white hover:bg-blue-50/80 hover:text-blue-700 hover:border-blue-300 px-2.5 py-1 rounded-full border border-slate-200/90 shadow-2xs transition-all shrink-0 outline-none focus:outline-none"
                >
                  {qp.label}
                </button>
              ))}
            </div>
          </div>

          {/* Input Tray */}
          <div className="p-3.5 sm:p-4 bg-white border-t border-slate-100 shrink-0">
            <div className={`mx-auto w-full ${isFullScreen ? 'max-w-4xl' : ''}`}>
              <div className="flex items-center gap-2 bg-slate-50 p-1.5 sm:p-2 rounded-2xl border border-slate-200 focus-within:bg-white focus-within:border-blue-600 transition-all shadow-xs">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendText(input)}
                  placeholder="Ask anything or request action..."
                  className="flex-1 bg-transparent px-3 py-1.5 text-xs sm:text-sm text-slate-900 outline-none focus:outline-none"
                />
                <button
                  onClick={() => handleSendText(input)}
                  disabled={!input.trim() || isLoading}
                  className="btn-pill-dark px-3 sm:px-4 py-1.5 sm:py-2 text-xs outline-none focus:outline-none flex items-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Send</span>
                </button>
              </div>
              {isFullScreen && (
                <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400 px-1">
                  <span>Secured with DPDP Zero-PII Vault &bull; NeMo Guardrails Active</span>
                  <span className="font-mono text-slate-400">Esc to exit fullscreen</span>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
    </>
  );
};
