import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import {
  AgentChatResponse,
  StructuredAction,
  User,
  UserChatSession,
  ActiveMemoryWindowResponse,
  SessionSummaryItem,
} from '../types';
import {
  X, Send, Bot, Shield, ShieldAlert, Sparkles, CheckCircle2,
  FileText, ArrowRight, CornerDownLeft, AlertTriangle, ShieldCheck, RotateCcw,
  Maximize2, Minimize2, Calendar, Clock, RefreshCw, History, Plus, Trash2,
  Brain, ChevronRight, MessageSquare, AlertCircle, ChevronLeft
} from 'lucide-react';
import { FeatureExplainerIcon } from './FeatureExplainerIcon';

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onActionExecuted?: () => void;
  initialPrompt?: string;
  initialFullScreen?: boolean;
  currentUser?: User | null;
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
      'Querying Pinecone policy index...',
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

const formatRelativeDate = (isoStr?: string) => {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours < 1) {
      const diffMins = Math.max(1, Math.floor(diffMs / (1000 * 60)));
      return `${diffMins}m ago`;
    }
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffHours < 48) return 'Yesterday';
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch (e) {
    return '';
  }
};

const getNextUserSessionId = (email?: string, increment: boolean = false): string => {
  const prefix = email ? email.split('@')[0].toLowerCase() : 'devansh.tyagi';
  const key = `user_session_idx_${prefix}`;
  let currentIdx = parseInt(localStorage.getItem(key) || '1', 10);
  if (isNaN(currentIdx) || currentIdx < 1) currentIdx = 1;
  
  if (increment) {
    currentIdx += 1;
    localStorage.setItem(key, currentIdx.toString());
  } else if (!localStorage.getItem(key)) {
    localStorage.setItem(key, '1');
  }
  
  const sid = `sess_${prefix}_${currentIdx}`;
  localStorage.setItem('chat_session_id', sid);
  return sid;
};

export const AgentChatDrawer: React.FC<ChatDrawerProps> = ({
  isOpen,
  onClose,
  onActionExecuted,
  initialPrompt,
  initialFullScreen = false,
  currentUser,
}) => {
  const [sessionId, setSessionId] = useState<string>(() => {
    return getNextUserSessionId(currentUser?.email, false);
  });

  // Whenever the active logged-in user changes (e.g. switched in RBAC modal), sync the session ID
  useEffect(() => {
    if (currentUser?.email) {
      const prefix = currentUser.email.split('@')[0].toLowerCase();
      if (!sessionId.startsWith(`sess_${prefix}_`)) {
        const fresh = getNextUserSessionId(currentUser.email, false);
        setSessionId(fresh);
        setMessages([]);
      }
    }
  }, [currentUser?.email]);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [loadingStepsList, setLoadingStepsList] = useState<string[]>([]);
  const [executingAction, setExecutingAction] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(initialFullScreen);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Cross-conversation Sessions and 5-Session Sliding Window states
  const [sessions, setSessions] = useState<UserChatSession[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
  const [activeMemoryWindow, setActiveMemoryWindow] = useState<ActiveMemoryWindowResponse | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);
  const [isPurgingHistory, setIsPurgingHistory] = useState<boolean>(false);

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

  const loadSessions = async () => {
    try {
      const data = await api.getUserSessions();
      if (data && data.sessions) {
        setSessions(data.sessions);
      }
    } catch (err) {
      console.warn('Notice: Could not load user sessions:', err);
    }
  };

  const loadMemoryWindow = async (sid?: string) => {
    try {
      const data = await api.getActiveMemoryWindow(sid || sessionId);
      if (data) {
        setActiveMemoryWindow(data);
      }
    } catch (err) {
      console.warn('Notice: Could not load active memory window:', err);
    }
  };

  const loadConversationHistory = async (targetSessionId: string) => {
    try {
      const data = await api.getSessionTurns(targetSessionId);
      if (data && data.messages && data.messages.length > 0) {
        const loaded: Message[] = data.messages.map((turn) => ({
          id: turn.id,
          sender: turn.role === 'user' ? 'user' : 'agent',
          text: turn.content,
          agentRouted: turn.role === 'user' ? undefined : (turn.metadata?.routed_agent || 'ROOT_LLM_ORCHESTRATOR'),
          guardrailStatus: turn.metadata?.guardrail_status || 'PASSED',
          citations: turn.metadata?.citations || [],
          structuredAction: turn.metadata?.structured_action,
          latencyMs: turn.metadata?.latency_ms,
        }));
        setMessages(loaded);
        return;
      }
    } catch (err) {
      // 404 is normal for a brand new uncheckpointed session
      try {
        const mem = await api.getChatMemory(targetSessionId);
        if (mem && mem.history && mem.history.length > 0) {
          const loaded: Message[] = mem.history.map((turn, index) => ({
            id: `persisted_${index}_${Date.now()}`,
            sender: turn.role === 'user' ? 'user' : 'agent',
            text: turn.content,
            agentRouted: turn.role === 'user' ? undefined : 'ROOT_LLM_ORCHESTRATOR',
            guardrailStatus: 'PASSED',
          }));
          setMessages(loaded);
          return;
        }
      } catch (e) {
        // Fall through
      }
    }
    setMessages([]);
  };

  // Load history, user sessions, and sliding memory window on open
  useEffect(() => {
    if (isOpen) {
      loadSessions();
      loadMemoryWindow(sessionId);
      loadConversationHistory(sessionId);
    }
  }, [sessionId, isOpen]);

  const handleNewChat = async () => {
    // If current conversation has turns, summarize it to slide into 5-session window
    if (messages.length > 0) {
      try {
        await api.summarizeSession(sessionId);
      } catch (err) {
        console.warn('Could not summarize on new chat:', err);
      }
    }
    const fresh = getNextUserSessionId(currentUser?.email, true);
    setSessionId(fresh);
    setMessages([]);
    setIsHistoryOpen(false);
    loadSessions();
    loadMemoryWindow(fresh);
  };

  const handleSelectSession = async (targetId: string) => {
    if (targetId === sessionId) {
      setIsHistoryOpen(false);
      return;
    }
    if (messages.length > 0) {
      try {
        api.summarizeSession(sessionId).catch(() => {});
      } catch (e) {}
    }

    setLoadingSessionId(targetId);
    setSessionId(targetId);
    setIsHistoryOpen(false);
    await loadConversationHistory(targetId);
    await loadMemoryWindow(targetId);
    setLoadingSessionId(null);
  };

  const handleDeleteSession = async (targetId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat session?')) return;
    try {
      await api.deleteSession(targetId);
      if (targetId === sessionId) {
        const fresh = getNextUserSessionId(currentUser?.email, false);
        setSessionId(fresh);
        setMessages([]);
      }
      loadSessions();
      loadMemoryWindow();
    } catch (err: any) {
      alert('Failed to delete session: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handlePurgeAllHistory = async () => {
    if (!confirm('Are you sure you want to completely purge all your chat history from the database? Under the DPDP Act Right to Erasure, all your chat sessions, messages, and memory records will be permanently deleted.')) return;
    setIsPurgingHistory(true);
    try {
      await api.purgeUserChatHistory();
      setSessions([]);
      setMessages([]);
      const fresh = getNextUserSessionId(currentUser?.email, true);
      setSessionId(fresh);
      await loadMemoryWindow(fresh);
    } catch (err: any) {
      alert('Failed to purge chat history: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsPurgingHistory(false);
    }
  };

  const handleManualSummarize = async () => {
    if (messages.length === 0) {
      alert('Please send at least one message in this conversation before generating a summary.');
      return;
    }
    setIsSummarizing(true);
    try {
      await api.summarizeSession(sessionId);
      await loadMemoryWindow(sessionId);
      await loadSessions();
      alert('✅ Session summary generated and recorded into your 5-session rolling window!');
    } catch (e: any) {
      alert('Failed to generate summary: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsSummarizing(false);
    }
  };

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

  const handleResetConversation = () => {
    handleNewChat();
  };

  const handleSendText = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return;
    const userMsgText = textToSend.trim();
    setInput('');

    const nextMsgIdx = messages.length + 1;
    const userMsg: Message = {
      id: `msg_${sessionId}_${nextMsgIdx}`,
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
        id: `msg_${sessionId}_${nextMsgIdx + 1}`,
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
      setTimeout(() => {
        loadSessions();
        loadMemoryWindow(sessionId);
      }, 500);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg_${sessionId}_${nextMsgIdx + 1}`,
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
            : 'inset-y-0 right-0 w-full max-w-md md:max-w-xl shadow-2xl border-l border-slate-200'
        }`}
      >
        {/* Drawer Header - Formal Executive Minimalist Styling */}
        <div className="px-4 py-3 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800 shrink-0 select-none">
          {/* Left: Clean Brand Identity */}
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="font-display font-semibold text-sm tracking-tight text-white leading-tight truncate">
                PeopleOps AI
              </h3>
              <p className="text-[11px] text-slate-400 font-normal leading-tight truncate">
                Enterprise People & HR Intelligence
              </p>
            </div>
          </div>

          {/* Right: Clean, Executive Action Controls */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* New Chat Button */}
            <button
              onClick={handleNewChat}
              title="New Conversation"
              className="px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700/80 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-2xs"
            >
              <Plus className="w-3.5 h-3.5 text-blue-400" />
              <span>New Chat</span>
            </button>

            {/* History Toggle */}
            <button
              onClick={() => setIsHistoryOpen((prev) => !prev)}
              title={isHistoryOpen ? "Close History" : "Past Conversations"}
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                isHistoryOpen
                  ? 'text-white bg-slate-800'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <History className="w-4 h-4" />
            </button>

            <div className="h-3.5 w-px bg-slate-800 mx-0.5" />

            {/* Fullscreen Toggle */}
            <button
              onClick={() => setIsFullScreen((prev) => !prev)}
              title={isFullScreen ? "Collapse to Drawer (Esc)" : "Expand to Fullscreen"}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              {isFullScreen ? (
                <Minimize2 className="w-4 h-4" />
              ) : (
                <Maximize2 className="w-4 h-4" />
              )}
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              title="Close"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Main Body Area: History Sidebar + Active Chat Stream */}
        <div className="flex-1 flex overflow-hidden relative">
          {/* Conversation History Sidebar / Overlay */}
          {isHistoryOpen && (
            <div
              className={`${
                isFullScreen
                  ? 'w-72 border-r border-slate-200 bg-slate-50 flex flex-col shrink-0 z-20'
                  : 'absolute inset-y-0 left-0 w-full sm:w-80 bg-slate-50 z-30 border-r border-slate-200 shadow-xl flex flex-col'
              }`}
            >
              {/* History Header - Formal Opaque Executive Styling */}
              <div className="p-3.5 border-b border-slate-200 flex items-center justify-between bg-white shrink-0">
                <div className="flex items-center gap-2">
                  <History className="w-4 h-4 text-slate-700" />
                  <h4 className="font-semibold text-xs text-slate-900 tracking-tight">Past Conversations</h4>
                  <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono font-medium border border-slate-200">
                    {sessions.length}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleNewChat}
                    title="Start New Chat"
                    className="p-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                  {!isFullScreen && (
                    <button
                      onClick={() => setIsHistoryOpen(false)}
                      title="Close Past Conversations"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Sessions List - Solid Opaque Background */}
              <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50">
                {sessions.length === 0 ? (
                  <div className="p-6 text-center bg-white rounded-xl border border-slate-200/80 shadow-2xs my-2">
                    <MessageSquare className="w-8 h-8 mx-auto mb-2 text-slate-300 stroke-[1.5]" />
                    <p className="font-semibold text-xs text-slate-700">No past conversations</p>
                    <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                      Your chats are saved and checkpointed automatically under your employee profile.
                    </p>
                  </div>
                ) : (
                  sessions.map((sess) => {
                    const isActive = sess.id === sessionId;
                    return (
                      <div
                        key={sess.id}
                        onClick={() => handleSelectSession(sess.id)}
                        className={`group relative p-3 rounded-xl border text-left cursor-pointer transition-all ${
                          isActive
                            ? 'bg-white border-blue-600 shadow-xs ring-1 ring-blue-600/15'
                            : 'bg-white hover:bg-slate-100/70 border-slate-200 hover:border-slate-300 shadow-2xs'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              {isActive && (
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" />
                              )}
                              <p className={`text-xs font-semibold truncate ${isActive ? 'text-blue-900' : 'text-slate-800'}`}>
                                {sess.title || 'Conversation'}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400 font-mono">
                              <span>{formatRelativeDate(sess.updated_at || sess.created_at)}</span>
                              <span>&bull;</span>
                              <span>{sess.message_count} msgs</span>
                            </div>
                          </div>
                          <button
                            onClick={(e) => handleDeleteSession(sess.id, e)}
                            title="Delete Conversation"
                            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all shrink-0 cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Privacy Footer - Solid Opaque */}
              <div className="p-3 bg-white border-t border-slate-200 text-[10px] text-slate-500 shrink-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 text-slate-700 font-medium">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>DPDP Act Private Vault</span>
                  </div>
                  <button
                    onClick={handlePurgeAllHistory}
                    disabled={isPurgingHistory || sessions.length === 0}
                    title="Permanently erase all your chat history and memory from the database (DPDP Right to Erasure)"
                    className="px-2 py-0.5 rounded text-[10px] font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="w-2.5 h-2.5 text-slate-400" />
                    <span>{isPurgingHistory ? 'Purging...' : 'Purge'}</span>
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 leading-snug">
                  Strictly isolated to your account. No other employee or admin has access.
                </p>
              </div>
            </div>
          )}

          {/* Conversation Stream & Hero Area */}
          <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-white">
            {messages.length === 0 ? (
              <div className="flex-1 overflow-y-auto flex flex-col justify-center items-center p-6 sm:p-10 bg-gradient-to-b from-white via-slate-50/50 to-slate-100/30">
                <div className="max-w-2xl w-full mx-auto flex flex-col items-center text-center my-auto py-6">
                  {/* Formal Minimalist Typography */}
                  <h2 className="font-display font-bold text-2xl sm:text-3xl text-slate-900 tracking-tight mb-2">
                    How can PeopleOps assist you today?
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 max-w-md mx-auto mb-6 font-normal leading-relaxed">
                    Autonomous workforce intelligence for leave allocations, statutory compliance, clinical triage, and HRMS records.
                  </p>

                  {/* Cross-Conversation Continuity Recall Card */}
                  {(() => {
                    const pendingSummary = activeMemoryWindow?.summaries?.find((s) => s.pending_action);
                    if (!pendingSummary) return null;
                    return (
                      <div className="w-full mb-6 p-4 rounded-2xl bg-gradient-to-br from-amber-50/90 via-amber-50/60 to-orange-50/80 border border-amber-200 shadow-sm text-left animate-fade-in">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-700 flex items-center justify-center shrink-0">
                              <Sparkles className="w-4 h-4 text-amber-600" />
                            </div>
                            <div>
                              <span className="text-[10px] font-bold tracking-wider text-amber-800 uppercase flex items-center gap-1">
                                Cross-Conversation Recall
                                <span className="font-normal text-amber-600">({pendingSummary.session_title})</span>
                              </span>
                              <h4 className="text-xs font-semibold text-slate-800">Unfinished Workflow Detected</h4>
                            </div>
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold border border-amber-300/80 shrink-0">
                            Pending Action
                          </span>
                        </div>
                        <p className="mt-2.5 text-xs text-slate-700 leading-relaxed">
                          In your previous conversation, you had an unsubmitted request: <span className="font-semibold text-slate-900">"{pendingSummary.pending_action}"</span>. Shall we continue where we were?
                        </p>
                        <div className="mt-3 flex items-center gap-2">
                          <button
                            onClick={() => handleSendText(`Let's continue where we left off with: ${pendingSummary.pending_action}`)}
                            disabled={isLoading}
                            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-blue-600 text-white text-xs font-medium transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
                          >
                            <span>Continue Request</span>
                            <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleSendText(`I don't need to proceed with that previous request. Let's start something new.`)}
                            disabled={isLoading}
                            className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 text-slate-600 border border-slate-200 text-xs font-medium transition-colors cursor-pointer"
                          >
                            Start Fresh
                          </button>
                        </div>
                      </div>
                    );
                  })()}

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
                          className="group p-3.5 rounded-xl bg-white/90 hover:bg-white border border-slate-200/80 hover:border-blue-400/80 hover:shadow-md transition-all duration-200 flex items-start gap-3 outline-none focus:outline-none text-left cursor-pointer"
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
                        className="text-[11px] font-medium text-slate-700 bg-white hover:bg-blue-50/80 hover:text-blue-700 hover:border-blue-300 px-2.5 py-1 rounded-full border border-slate-200/90 shadow-2xs transition-all shrink-0 outline-none focus:outline-none cursor-pointer"
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
                        className="btn-pill-dark px-3 sm:px-4 py-1.5 sm:py-2 text-xs outline-none focus:outline-none flex items-center gap-1.5 cursor-pointer"
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
        </div>
      </div>

      {/* 5-Session Sliding Window Rolling Memory Modal */}
      {isMemoryModalOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden animate-fade-in">
            {/* Modal Header */}
            <div className="px-5 py-4 bg-slate-900 text-white flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                  <Brain className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-sm">5-Session Sliding Window Memory</h3>
                  <p className="text-[11px] text-slate-400">Cross-conversation context injected into Root Orchestrator</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-indigo-900/60 text-indigo-300 border border-indigo-700/60">
                  {activeMemoryWindow?.retained_summaries_count ?? 0} / 5 Retained
                </span>
                <button
                  onClick={() => setIsMemoryModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Subheader / Explanation */}
            <div className="p-4 bg-slate-50 border-b border-slate-200/80 text-xs text-slate-600 shrink-0 leading-relaxed">
              <p>
                <strong className="text-slate-800">Retention Policy:</strong> The agent maintains a rolling window of your latest <strong className="text-slate-800">5 conversation summaries</strong> (S<sub>n-4</sub> &rarr; S<sub>n</sub>). Older conversations slide out of active prompt memory while remaining stored in PostgreSQL.
              </p>
              <p className="mt-1 text-[11px] text-slate-500 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Strictly isolated to your employee account ({currentUser?.email}). No other employee or admin can view this memory.</span>
              </p>
            </div>

            {/* Summaries List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {(!activeMemoryWindow || activeMemoryWindow.summaries.length === 0) ? (
                <div className="p-8 text-center text-slate-400 text-xs">
                  <Brain className="w-8 h-8 mx-auto mb-2 text-slate-300 stroke-[1.5]" />
                  <p className="font-medium text-slate-600">No session summaries in memory yet</p>
                  <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
                    Once you conclude conversations or start a New Chat, automated summaries with detected entities and pending actions will slide into this 5-session window.
                  </p>
                </div>
              ) : (
                activeMemoryWindow.summaries.map((sum, idx) => (
                  <div
                    key={sum.id || idx}
                    className="p-3.5 rounded-xl bg-white border border-slate-200/90 shadow-2xs hover:border-slate-300 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-700 font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <h4 className="font-display font-semibold text-xs text-slate-800 truncate">
                          {sum.session_title || 'Session'}
                        </h4>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {sum.pending_action ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium border border-amber-200">
                            Action Pending
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium border border-emerald-200">
                            Completed
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400 font-mono">
                          {formatRelativeDate(sum.created_at)}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-700 leading-relaxed mt-1">
                      {sum.summary_text}
                    </p>

                    {sum.pending_action && (
                      <div className="mt-2.5 p-2 rounded-lg bg-amber-50 border border-amber-200/80 text-[11px] text-amber-900 flex items-start gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <strong className="font-semibold">Unfinished Workflow: </strong>
                          <span>{sum.pending_action}</span>
                        </div>
                      </div>
                    )}

                    {sum.key_entities && Object.keys(sum.key_entities).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {Object.entries(sum.key_entities).map(([k, v]) => (
                          <span
                            key={k}
                            className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md font-mono"
                          >
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between shrink-0">
              <button
                onClick={handleManualSummarize}
                disabled={isSummarizing || messages.length === 0}
                className={`text-xs px-3 py-1.5 rounded-xl font-medium transition-all flex items-center gap-1.5 ${
                  messages.length > 0 && !isSummarizing
                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer'
                    : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isSummarizing ? 'Summarizing...' : 'Summarize Active Session Now'}</span>
              </button>
              <button
                onClick={() => setIsMemoryModalOpen(false)}
                className="btn-pill-dark text-xs py-1.5 px-4 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </>
  );
};
