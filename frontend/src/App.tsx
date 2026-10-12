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
import { Shield, Sparkles, Maximize2 } from 'lucide-react';
import { DemoModeProvider } from './context/DemoModeContext';
import { FeatureExplainerModal } from './components/FeatureExplainerModal';
import { DemoModeToggleBar } from './components/DemoModeToggleBar';
import { AuthLoginModal } from './components/AuthLoginModal';

export const App: React.FC = () => {
  const [currentRole, setCurrentRole] = useState<UserRole>('EMPLOYEE');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [balances, setBalances] = useState<LeaveBalanceSummary | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isChatFullScreen, setIsChatFullScreen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [autoOpenApplyModal, setAutoOpenApplyModal] = useState(false);
  const [autoOpenLogModal, setAutoOpenLogModal] = useState(false);
  const [chatInitialPrompt, setChatInitialPrompt] = useState<string | undefined>(undefined);

  const handleNavigate = (tab: string, options?: { openApplyModal?: boolean; openLogModal?: boolean }) => {
    setActiveTab(tab);
    setAutoOpenApplyModal(!!options?.openApplyModal);
    setAutoOpenLogModal(!!options?.openLogModal);
  };

  const handleOpenChat = (prompt?: string, fullScreen: boolean = false) => {
    if (prompt) setChatInitialPrompt(prompt);
    setIsChatFullScreen(fullScreen);
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

  // Switch role and fetch user data concurrently with zero waterfall latency
  const handleRoleSwitch = async (newRole: UserRole) => {
    setCurrentRole(newRole);
    setLoading(true);
    try {
      const loginRes = await api.mockLogin(newRole);
      // Fetch user profile and balances in parallel
      const [user, bals] = await Promise.all([
        api.getCurrentUser(),
        api.getLeaveBalances(loginRes.access_token ? undefined : undefined),
      ]);
      setCurrentUser(user);
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
    <DemoModeProvider>
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
            toggleChat={() => {
              setIsChatFullScreen(false);
              setIsChatOpen((prev) => !prev);
            }}
            isChatOpen={isChatOpen}
            isFullscreen={isFullscreen}
            onToggleFullscreen={() => setIsFullscreen((prev) => !prev)}
            onOpenAuthModal={() => setIsAuthModalOpen(true)}
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
          <main className="w-full flex-1">
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
            initialFullScreen={isChatFullScreen}
            onClose={() => {
              setIsChatOpen(false);
              setIsChatFullScreen(false);
            }}
            initialPrompt={chatInitialPrompt}
            currentUser={currentUser}
            onActionExecuted={() => {
              refreshBalances();
            }}
          />

          {/* Footer with Master Demo Mode Toggle & Fullscreen AI Launcher */}
          <footer className="app-footer text-xs text-slate-500">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-slate-400" />
                <span>Google ADK Multi-Agent Architecture &bull; NVIDIA NeMo Guardrails &bull; DPDP Act 2023 Compliant</span>
              </div>
              <div className="flex items-center gap-3">
                <DemoModeToggleBar />
                <button
                  onClick={() => handleOpenChat(undefined, true)}
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-full transition-colors outline-none focus:outline-none"
                  title="Open Fullscreen PeopleOps AI Chat Mode"
                >
                  <Maximize2 size={13} />
                </button>
                <div className="hidden lg:block text-slate-300">|</div>
                <div className="hidden lg:block">Maharashtra Shops & Establishments 2017</div>
              </div>
            </div>
          </footer>
        </div>
      </div>

      {/* Feature Explainer Modal with 25% screen blur */}
      <FeatureExplainerModal />

      {/* Interactive Authentication & RBAC Boundary Modal */}
      <AuthLoginModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        currentUser={currentUser}
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          setCurrentRole(user.role);
          setIsAuthModalOpen(false);
          refreshBalances();
        }}
      />
    </DemoModeProvider>
  );
};

export default App;
