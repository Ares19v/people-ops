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
  const [loading, setLoading] = useState(true);

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
    <div className="min-h-screen bg-slate-50 flex flex-col selection:bg-emerald-500 selection:text-white">
      {/* Top Navigation */}
      <Navbar
        currentUser={currentUser}
        currentRole={currentRole}
        onRoleSwitch={handleRoleSwitch}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        toggleChat={() => setIsChatOpen((prev) => !prev)}
        isChatOpen={isChatOpen}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500">
            <div className="w-10 h-10 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin mb-3" />
            <span className="text-xs font-semibold">Switching authenticated role & initializing Google ADK tools...</span>
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && (
              <Dashboard
                currentUser={currentUser}
                currentRole={currentRole}
                balances={balances}
                onNavigate={(tab) => setActiveTab(tab)}
                openChat={() => setIsChatOpen(true)}
              />
            )}
            {activeTab === 'leaves' && (
              <LeavePortal
                currentUser={currentUser}
                currentRole={currentRole}
                balances={balances}
                onRefreshBalances={refreshBalances}
              />
            )}
            {activeTab === 'timesheets' && (
              <TimesheetPortal currentUser={currentUser} currentRole={currentRole} />
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
        onActionExecuted={() => {
          refreshBalances();
        }}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-600" />
            <span>Google ADK Architecture &bull; NVIDIA NeMo Guardrails 0.24 &bull; DPDP Act 2023 Compliant</span>
          </div>
          <div>Antigravity Global Technologies Pvt Ltd &bull; Maharashtra Shops & Establishments 2017</div>
        </div>
      </footer>
    </div>
  );
};

export default App;
