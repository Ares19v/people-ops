import React, { useState, useEffect } from 'react';
import { api } from './api';
import { User, UserRole, LeaveBalanceSummary } from './types';
import { Navbar } from './components/Navbar';
import { AgentChatDrawer } from './components/AgentChatDrawer';
import { Dashboard } from './pages/Dashboard';
import { LeavePortal } from './pages/LeavePortal';
import { TimesheetPortal } from './pages/TimesheetPortal';
import { ReportsPortal } from './pages/ReportsPortal';
import { PolicySearchPortal } from './pages/PolicySearchPortal';
import { OnboardingWizard } from './pages/OnboardingWizard';
import { Shield, Sparkles } from 'lucide-react';

export const App: React.FC = () => {
  const [currentRole, setCurrentRole] = useState<UserRole>('EMPLOYEE');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [balances, setBalances] = useState<LeaveBalanceSummary | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [autoOpenApplyModal, setAutoOpenApplyModal] = useState(false);
  const [autoOpenLogModal, setAutoOpenLogModal] = useState(false);
  const [chatInitialPrompt, setChatInitialPrompt] = useState<string | undefined>(undefined);

  const handleNavigate = (tab: string, options?: { openApplyModal?: boolean; openLogModal?: boolean }) => {
    setActiveTab(tab);
    setAutoOpenApplyModal(!!options?.openApplyModal);
    setAutoOpenLogModal(!!options?.openLogModal);
  };

  const handleOpenChat = (prompt?: string) => {
    if (prompt) setChatInitialPrompt(prompt);
    setIsChatOpen(true);
  };

  // Sync fullscreen class with document.body
  useEffect(() => {
    if (isFullscreen) {
      document.body.classList.add('is-fullscreen');
    } else {
      document.body.classList.remove('is-fullscreen');
    }
  }, [isFullscreen]);

  // Switch role and fetch user data
  const handleRoleSwitch = async (newRole: UserRole) => {
    setCurrentRole(newRole);
    setLoading(true);
    try {
      await api.mockLogin(newRole);
      const user = await api.getCurrentUser();
      setCurrentUser(user);
      const bals = await api.getLeaveBalances(user.id);
      setBalances(bals);
    } catch (err) {
      console.error('Role switch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const refreshBalances = async () => {
    if (!currentUser) return;
    try {
      const bals = await api.getLeaveBalances(currentUser.id);
      setBalances(bals);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    handleRoleSwitch('EMPLOYEE');
  }, []);

  return (
    <div className={`floating-canvas ${isFullscreen ? 'is-fullscreen' : ''}`}>
      {/* Background Decorative Grid and Ambient Glow */}
      <div className="canvas-grid-bg" />
      <div className="canvas-glow" />

      {/* Main Container Content */}
      <div className="canvas-content">
        {/* Top Navbar */}
        <Navbar
          currentUser={currentUser}
          currentRole={currentRole}
          onRoleSwitch={handleRoleSwitch}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          toggleChat={() => setIsChatOpen((prev) => !prev)}
          isChatOpen={isChatOpen}
          isFullscreen={isFullscreen}
          onToggleFullscreen={() => setIsFullscreen((prev) => !prev)}
        />

        {/* Mobile Navigation Pills */}
        <div className="flex md:hidden overflow-x-auto gap-2 pb-3 mb-6 border-b border-slate-100">
          {[
            { id: 'dashboard', label: 'Dashboard' },
            { id: 'leaves', label: 'Leaves' },
            { id: 'timesheets', label: 'Timesheets' },
            { id: 'reports', label: 'Reports' },
            { id: 'policy', label: 'HR Policy RAG' },
            ...(currentRole !== 'EMPLOYEE' ? [{ id: 'onboarding', label: 'Onboarding' }] : []),
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                activeTab === item.id
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Main Content Area */}
        <main className="w-full">
          {loading ? (
            <div className="flex flex-col items-center justify-center min-h-[420px] text-slate-500">
              <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mb-3" />
              <span className="text-xs font-semibold">Switching authenticated role & initializing Google ADK tools...</span>
            </div>
          ) : (
            <>
              {activeTab === 'dashboard' && (
                <Dashboard
                  currentUser={currentUser}
                  currentRole={currentRole}
                  balances={balances}
                  onNavigate={handleNavigate}
                  openChat={handleOpenChat}
                />
              )}
              {activeTab === 'leaves' && (
                <LeavePortal
                  currentUser={currentUser}
                  currentRole={currentRole}
                  balances={balances}
                  onRefreshBalances={refreshBalances}
                  initialOpenApplyModal={autoOpenApplyModal}
                />
              )}
              {activeTab === 'timesheets' && (
                <TimesheetPortal
                  currentUser={currentUser}
                  currentRole={currentRole}
                  initialOpenLogModal={autoOpenLogModal}
                />
              )}
              {activeTab === 'reports' && (
                <ReportsPortal currentUser={currentUser} currentRole={currentRole} />
              )}
              {activeTab === 'policy' && <PolicySearchPortal />}
              {activeTab === 'onboarding' && (
                <OnboardingWizard currentUser={currentUser} currentRole={currentRole} />
              )}
            </>
          )}
        </main>

        {/* AI Assistant Chat Drawer */}
        <AgentChatDrawer
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          initialPrompt={chatInitialPrompt}
          onActionExecuted={() => {
            refreshBalances();
          }}
        />

        {/* Footer */}
        <footer className="mt-16 pt-6 border-t border-slate-200/70 text-xs text-slate-500">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-600" />
              <span>Google ADK Multi-Agent Architecture &bull; NVIDIA NeMo Guardrails &bull; DPDP Act 2023 Compliant</span>
            </div>
            <div>Antigravity Global Technologies Pvt Ltd &bull; Maharashtra Shops & Establishments 2017</div>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default App;
