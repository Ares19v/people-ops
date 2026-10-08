import React, { useState, useRef, useEffect } from 'react';
import { User, UserRole } from '../types';
import { Bot, Maximize2, Minimize2, ChevronDown, Check } from 'lucide-react';
import { FeatureExplainerIcon } from './FeatureExplainerIcon';

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
  const [roleOpen, setRoleOpen] = useState(false);
  const roleRef = useRef<HTMLDivElement>(null);

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

  const currentRoleLabel = roles.find((r) => r.value === currentRole)?.label ?? 'Employee';

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (roleRef.current && !roleRef.current.contains(e.target as Node)) {
        setRoleOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <nav className="olixer-nav">
      {/* Brand Logo */}
      <div className="brand-block" onClick={() => setActiveTab('dashboard')}>
        <div className="brand-icon-box">
          <Bot size={22} className="text-slate-900" />
        </div>
        <div className="flex items-center">
          <div className="brand-title">
            PeopleOps
          </div>
          <FeatureExplainerIcon featureKey="navbar_brand" />
        </div>
      </div>

      {/* Center Nav Links with Active Indicator Dot */}
      <div className="hidden md:flex nav-center-menu">
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
        <div className="hidden sm:inline-flex items-center">
          <button
            className="btn-pill-outline outline-none focus:outline-none focus-visible:outline-none focus:ring-0"
            onClick={onToggleFullscreen}
            title={isFullscreen ? 'Switch to Framed Card View' : 'Switch to Full Screen (Default)'}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            <span>{isFullscreen ? 'Framed View' : 'Full Screen'}</span>
          </button>
          <FeatureExplainerIcon featureKey="fullscreen_toggle" />
        </div>

        {/* Custom Role Switcher */}
        <div className="flex items-center">
          <div className="role-switcher" ref={roleRef}>
            <button
              className="role-switcher-trigger outline-none focus:outline-none focus-visible:outline-none"
              onClick={() => setRoleOpen((prev) => !prev)}
            >
              <span>{currentRoleLabel}</span>
              <ChevronDown
                size={13}
                className="role-switcher-chevron"
                style={{ transform: roleOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
              />
            </button>

            {roleOpen && (
              <div className="role-switcher-dropdown">
                {roles.map((r) => {
                  const isSelected = r.value === currentRole;
                  return (
                    <button
                      key={r.value}
                      className={`role-switcher-option ${isSelected ? 'selected' : ''}`}
                      onClick={() => {
                        onRoleSwitch(r.value);
                        setRoleOpen(false);
                      }}
                    >
                      <span>{r.label}</span>
                      {isSelected && <Check size={13} className="text-blue-600 ml-auto shrink-0" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <FeatureExplainerIcon featureKey="role_switcher" />
        </div>

        {/* Ask HR AI Deep Charcoal Pill Button */}
        <div className="flex items-center">
          <button
            onClick={toggleChat}
            className="btn-pill-dark outline-none focus:outline-none focus-visible:outline-none focus:ring-0"
            title="Open PeopleOps AI Assistant"
          >
            <Bot size={15} className="text-blue-400" />
            <span>Ask HR AI</span>
          </button>
          <FeatureExplainerIcon featureKey="agent_drawer_launcher" />
        </div>
      </div>
    </nav>
  );
};
