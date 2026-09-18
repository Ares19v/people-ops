import React from 'react';
import { User, UserRole } from '../types';
import { Bot, Calendar, Clock, FileText, LayoutDashboard, UserPlus, Shield, Sparkles, Maximize2, Minimize2 } from 'lucide-react';

interface NavbarProps {
  currentUser: User | null;
  currentRole: UserRole;
  onRoleSwitch: (role: UserRole) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  toggleChat: () => void;
  isChatOpen: boolean;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  currentRole,
  onRoleSwitch,
  activeTab,
  setActiveTab,
  toggleChat,
  isChatOpen,
  isFullscreen,
  onToggleFullscreen,
}) => {
  const roles: { label: string; value: UserRole }[] = [
    { label: 'Employee', value: 'EMPLOYEE' },
    { label: 'HR Associate', value: 'HR_ASSOCIATE' },
    { label: 'HR Manager', value: 'HR_MANAGER' },
    { label: 'Admin', value: 'ADMIN' },
  ];

  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'leaves', label: 'Leave Ledger' },
    { id: 'timesheets', label: 'Timesheets' },
    { id: 'reports', label: 'Reports & CSV' },
    { id: 'policy', label: 'HR Policy RAG' },
    ...(currentRole !== 'EMPLOYEE' ? [{ id: 'onboarding', label: 'Onboarding' }] : []),
  ];

  return (
    <nav className="olixer-nav">
      {/* Brand Logo */}
      <div className="brand-block" onClick={() => setActiveTab('dashboard')}>
        <div className="brand-icon-box">
          <Bot size={22} className="text-slate-900" />
        </div>
        <div>
          <div className="brand-title">
            PeopleOps<span style={{ color: 'var(--blue-brand)' }}>.adk</span>
          </div>
          <div className="brand-sub">Google ADK &bull; NeMo Guardrails</div>
        </div>
      </div>

      {/* Center Nav Links with Active Indicator Dot */}
      <div className="hidden lg:flex nav-center-menu">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              className={`nav-item-link ${isActive ? 'active' : ''} outline-none focus:outline-none focus-visible:outline-none focus:ring-0`}
              onClick={() => setActiveTab(item.id)}
            >
              <span>{item.label}</span>
              {isActive && <div className="nav-dot" />}
            </button>
          );
        })}
      </div>

      {/* Right Actions */}
      <div className="nav-actions">
        {/* Fullscreen / Framed View Toggle */}
        <button
          className="btn-pill-outline hidden sm:inline-flex outline-none focus:outline-none focus-visible:outline-none focus:ring-0"
          onClick={onToggleFullscreen}
          title={isFullscreen ? "Switch to Framed Card View" : "Switch to Full Screen (Default)"}
        >
          {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          <span>{isFullscreen ? "Framed View" : "Full Screen"}</span>
        </button>

        {/* Role Switcher Pill */}
        <div className="relative inline-flex items-center">
          <select
            value={currentRole}
            onChange={(e) => onRoleSwitch(e.target.value as UserRole)}
            className="btn-pill-outline appearance-none pr-8 cursor-pointer bg-white text-xs font-semibold outline-none focus:outline-none focus-visible:outline-none focus:ring-0"
          >
            {roles.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-[10px]">
            ▼
          </div>
        </div>

        {/* Ask HR AI Deep Charcoal Pill Button */}
        <button
          onClick={toggleChat}
          className="btn-pill-dark outline-none focus:outline-none focus-visible:outline-none focus:ring-0"
          title="Open Google ADK HR Assistant"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <Bot size={15} />
          <span>Ask HR AI</span>
        </button>
      </div>
    </nav>
  );
};
