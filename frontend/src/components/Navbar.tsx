import React from 'react';
import { User, UserRole } from '../types';
import { Bot, Calendar, Clock, FileText, LayoutDashboard, UserPlus, Shield, Sparkles, Network } from 'lucide-react';

interface NavbarProps {
  currentUser: User | null;
  currentRole: UserRole;
  onRoleSwitch: (role: UserRole) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  toggleChat: () => void;
  isChatOpen: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  currentRole,
  onRoleSwitch,
  activeTab,
  setActiveTab,
  toggleChat,
  isChatOpen,
}) => {
  const roles: { label: string; value: UserRole }[] = [
    { label: 'Employee', value: 'EMPLOYEE' },
    { label: 'HR Associate', value: 'HR_ASSOCIATE' },
    { label: 'HR Manager', value: 'HR_MANAGER' },
    { label: 'Admin', value: 'ADMIN' },
  ];

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'leaves', label: 'Leave Ledger', icon: Calendar },
    { id: 'timesheets', label: 'Timesheets', icon: Clock },
    { id: 'reports', label: 'Reports & CSV', icon: FileText },
    { id: 'policy', label: 'HR Policy RAG', icon: Shield },
    { id: 'graph', label: 'Code Graph', icon: Network },
    ...(currentRole !== 'EMPLOYEE' ? [{ id: 'onboarding', label: 'Onboarding', icon: UserPlus }] : []),
  ];

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <span className="text-lg font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">
                Antigravity HR
              </span>
              <span className="block text-xs font-semibold text-emerald-600 uppercase tracking-wider">
                ADK Multi-Agent + NeMo
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-600' : 'text-slate-500'}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right: Role Switcher & Agent Chat Trigger */}
          <div className="flex items-center gap-3">
            {/* Quick Role Switcher */}
            <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200">
              <span className="text-xs font-medium text-slate-500 px-2 hidden sm:inline">Role:</span>
              <select
                value={currentRole}
                onChange={(e) => onRoleSwitch(e.target.value as UserRole)}
                className="bg-transparent text-xs font-semibold text-slate-800 border-none focus:ring-0 cursor-pointer pr-4"
              >
                {roles.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Multi-Agent Assistant Button */}
            <button
              onClick={toggleChat}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-semibold transition-all shadow-sm ${
                isChatOpen
                  ? 'bg-emerald-700 text-white shadow-emerald-700/20'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-600/20'
              }`}
            >
              <Sparkles className="w-4 h-4 animate-pulse" />
              <span>AI Agents</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
