import React, { useState } from 'react';
import { 
  CheckCircle2, 
  Clock, 
  XCircle, 
  AlertCircle, 
  Calendar, 
  Sparkles, 
  Copy, 
  Check, 
  Code2, 
  Eye, 
  User as UserIcon,
  Shield,
  Briefcase,
  FileText
} from 'lucide-react';

export interface EmployeeInfo {
  name: string;
  email: string;
  role: string;
  department: string;
  initials: string;
  colorClass: string;
}

export const EMPLOYEES: Record<string, EmployeeInfo> = {
  'EMP-001': {
    name: 'Devansh Tyagi',
    email: 'devansh.tyagi@intelera.com',
    role: 'Chief Technology Officer',
    department: 'Leadership',
    initials: 'DT',
    colorClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  },
  'EMP-002': {
    name: 'Vikram Malhotra',
    email: 'vikram.malhotra@intelera.com',
    role: 'HR Operations Manager',
    department: 'Human Resources',
    initials: 'VM',
    colorClass: 'bg-purple-50 text-purple-700 border-purple-200',
  },
  'EMP-003': {
    name: 'Priya Patel',
    email: 'priya.patel@intelera.com',
    role: 'HR Operations Associate',
    department: 'Human Resources',
    initials: 'PP',
    colorClass: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  'EMP-004': {
    name: 'Aarav Sharma',
    email: 'aarav.sharma@intelera.com',
    role: 'Senior Software Engineer',
    department: 'Engineering',
    initials: 'AS',
    colorClass: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  'EMP-005': {
    name: 'Sneha Kulkarni',
    email: 'sneha.kulkarni@intelera.com',
    role: 'Operations Associate',
    department: 'Operations',
    initials: 'SK',
    colorClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
};

export const getEmployeeInfo = (userIdentifier?: string): EmployeeInfo => {
  if (!userIdentifier) {
    return {
      name: 'System Automated',
      email: 'system@intelera.com',
      role: 'System Automated',
      department: 'Platform',
      initials: 'SYS',
      colorClass: 'bg-slate-50 text-slate-700 border-slate-200',
    };
  }

  const raw = String(userIdentifier).trim();
  
  // Lookup by ID
  if (EMPLOYEES[raw.toUpperCase()]) {
    return EMPLOYEES[raw.toUpperCase()];
  }

  // Lookup by email
  const byEmail = Object.values(EMPLOYEES).find(
    (e) => e.email.toLowerCase() === raw.toLowerCase()
  );
  if (byEmail) return byEmail;

  // Lookup by email prefix (e.g. devansh.tyagi or aarav.sharma)
  const byPrefix = Object.values(EMPLOYEES).find(
    (e) => e.email.split('@')[0].toLowerCase() === raw.toLowerCase()
  );
  if (byPrefix) return byPrefix;

  // Fallback nicely formatted name
  const cleanName = raw.includes('@')
    ? raw.split('@')[0].replace('.', ' ')
    : raw.replace(/[-_]/g, ' ');

  const initials = cleanName
    .split(' ')
    .filter(Boolean)
    .map((p) => p[0].toUpperCase())
    .slice(0, 2)
    .join('');

  return {
    name: cleanName.replace(/\b\w/g, (c) => c.toUpperCase()),
    email: raw.includes('@') ? raw : `${raw}@intelera.com`,
    role: 'Team Member',
    department: 'Operations',
    initials: initials || 'EM',
    colorClass: 'bg-slate-50 text-slate-700 border-slate-200',
  };
};

export const EmployeeAvatarChip: React.FC<{
  userIdentifier?: string;
  showDetails?: boolean;
  size?: 'xs' | 'sm' | 'md';
}> = ({ userIdentifier, showDetails = true, size = 'md' }) => {
  const emp = getEmployeeInfo(userIdentifier);

  if (size === 'xs') {
    return (
      <div className="inline-flex items-center gap-1.5" title={`${emp.name} (${emp.email})`}>
        <span
          className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold border ${emp.colorClass}`}
        >
          {emp.initials}
        </span>
        <span className="font-display font-medium text-[11px] text-slate-800 truncate max-w-[130px]">
          {emp.name}
        </span>
      </div>
    );
  }

  if (size === 'sm') {
    return (
      <div className="inline-flex items-center gap-2" title={`${emp.name} (${emp.email})`}>
        <span
          className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border ${emp.colorClass}`}
        >
          {emp.initials}
        </span>
        <div className="min-w-0 text-left">
          <span className="font-display font-semibold text-xs text-slate-900 truncate block">
            {emp.name}
          </span>
          {showDetails && (
            <span className="text-[10px] text-slate-500 truncate block">
              {emp.role}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-2.5" title={`${emp.name} (${emp.email})`}>
      <span
        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border shadow-xs ${emp.colorClass}`}
      >
        {emp.initials}
      </span>
      <div className="min-w-0 text-left">
        <div className="font-display font-semibold text-xs text-slate-900 leading-tight truncate">
          {emp.name}
        </div>
        {showDetails && (
          <div className="text-[11px] text-slate-500 leading-tight truncate mt-0.5">
            {emp.role} &bull; {emp.department}
          </div>
        )}
      </div>
    </div>
  );
};

export const LeaveTypeBadge: React.FC<{ type: string }> = ({ type }) => {
  const norm = String(type).toUpperCase();
  switch (norm) {
    case 'EL':
    case 'EARNED_LEAVE':
    case 'EARNED LEAVE':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200/80">
          <Calendar className="w-3.5 h-3.5 text-blue-600" />
          Earned Leave (EL)
        </span>
      );
    case 'CL':
    case 'CASUAL_LEAVE':
    case 'CASUAL LEAVE':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-sky-50 text-sky-700 border border-sky-200/80">
          <Calendar className="w-3.5 h-3.5 text-sky-600" />
          Casual Leave (CL)
        </span>
      );
    case 'SL':
    case 'SICK_LEAVE':
    case 'SICK LEAVE':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200/80">
          <Calendar className="w-3.5 h-3.5 text-amber-600" />
          Sick Leave (SL)
        </span>
      );
    case 'LWP':
    case 'LEAVE_WITHOUT_PAY':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
          <Calendar className="w-3.5 h-3.5 text-slate-500" />
          Leave Without Pay (LWP)
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-800 border border-slate-200">
          {norm}
        </span>
      );
  }
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const norm = String(status).toUpperCase();
  if (norm === 'APPROVED' || norm === 'COMPLETED' || norm === 'VERIFIED' || norm === 'SUCCESS' || norm === 'ACTIVE') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        {status}
      </span>
    );
  }
  if (norm === 'SUBMITTED' || norm === 'PENDING' || norm === 'IN_PROGRESS' || norm === 'UNDER_REVIEW') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200 shadow-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
        {norm === 'SUBMITTED' ? 'Under Review' : status}
      </span>
    );
  }
  if (norm === 'REJECTED' || norm === 'CANCELLED' || norm === 'FAILED' || norm === 'INACTIVE') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200 shadow-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
        {status}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
      {status}
    </span>
  );
};

export const RoleBadge: React.FC<{ role: string }> = ({ role }) => {
  const norm = String(role).toUpperCase();
  const colorMap: Record<string, string> = {
    ADMIN: 'bg-slate-900 text-white border-slate-900',
    HR_MANAGER: 'bg-purple-50 text-purple-800 border-purple-200',
    HR_ASSOCIATE: 'bg-blue-50 text-blue-800 border-blue-200',
    EMPLOYEE: 'bg-slate-100 text-slate-700 border-slate-200',
    SYSTEM: 'bg-amber-50 text-amber-800 border-amber-200',
  };

  const labelMap: Record<string, string> = {
    ADMIN: 'Admin',
    HR_MANAGER: 'HR Manager',
    HR_ASSOCIATE: 'HR Associate',
    EMPLOYEE: 'Employee',
  };

  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide border shadow-2xs ${
        colorMap[norm] || 'bg-slate-100 text-slate-700 border-slate-200'
      }`}
    >
      {labelMap[norm] || role}
    </span>
  );
};

export const EntityIdBadge: React.FC<{ id: string; truncateLength?: number }> = ({ 
  id, 
  truncateLength = 28 
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const displayId = id.length > truncateLength ? `${id.slice(0, truncateLength)}...` : id;

  return (
    <button
      onClick={handleCopy}
      title="Click to copy identifier"
      className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200/90 transition-all cursor-pointer group"
    >
      <span>{displayId}</span>
      {copied ? (
        <Check className="w-3 h-3 text-emerald-600 shrink-0" />
      ) : (
        <Copy className="w-3 h-3 text-slate-400 group-hover:text-slate-600 shrink-0 opacity-60 group-hover:opacity-100" />
      )}
    </button>
  );
};

export const HoursBadge: React.FC<{ hours: number; isBillable?: boolean }> = ({
  hours,
  isBillable = true,
}) => {
  const hasOvertime = hours > 9.0;
  const overtimeHours = (hours - 9.0).toFixed(1);

  return (
    <div className="inline-flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="font-display font-extrabold text-sm text-slate-900">
          {hours.toFixed(1)} hrs
        </span>
        <span
          className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${
            isBillable
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}
        >
          {isBillable ? 'Billable' : 'Internal'}
        </span>
      </div>
      {hasOvertime && (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
          <Sparkles className="w-3 h-3 text-amber-600" />
          +{overtimeHours}h OT @ 2.0x (Sec 13)
        </span>
      )}
    </div>
  );
};

export const DateRangeBadge: React.FC<{
  startDate: string;
  endDate: string;
  totalDays: number;
}> = ({ startDate, endDate, totalDays }) => {
  const isSingleDay = startDate === endDate || totalDays === 1;

  const formatDate = (dStr: string) => {
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return dStr;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dStr;
    }
  };

  return (
    <div className="inline-flex flex-col text-left">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900">
        <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        {isSingleDay ? (
          <span>{formatDate(startDate)}</span>
        ) : (
          <span>
            {formatDate(startDate)} &rarr; {formatDate(endDate)}
          </span>
        )}
      </div>
      <div className="text-[11px] font-medium text-slate-500 mt-0.5 pl-5">
        {totalDays} {totalDays === 1 ? 'working day' : 'working days'}
      </div>
    </div>
  );
};

export const JsonPayloadModal: React.FC<{
  payload: any;
  title?: string;
}> = ({ payload, title = 'Payload Details' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const formattedJson = typeof payload === 'object' ? JSON.stringify(payload, null, 2) : String(payload);
  const preview = typeof payload === 'object' ? JSON.stringify(payload) : String(payload);

  const handleCopy = () => {
    navigator.clipboard.writeText(formattedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-600 bg-slate-50 hover:bg-slate-100 px-2 py-1 rounded-md border border-slate-200 transition-all cursor-pointer"
        title="Click to view full payload"
      >
        <Code2 className="w-3.5 h-3.5 text-slate-500" />
        <span className="truncate max-w-[140px]">{preview}</span>
        <Eye className="w-3 h-3 text-slate-400" />
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full overflow-hidden p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Code2 className="w-4 h-4 text-blue-600" />
                <h4 className="font-display font-bold text-sm text-slate-900">{title}</h4>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-semibold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="bg-slate-900 text-slate-100 p-3.5 rounded-xl font-mono text-xs overflow-x-auto max-h-72">
              <pre>{formattedJson}</pre>
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={handleCopy}
                className="btn-pill-outline text-xs py-1.5 px-3 flex items-center gap-1.5 cursor-pointer"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="btn-pill-dark text-xs py-1.5 px-4 cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
