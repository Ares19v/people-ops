import React, { useState } from 'react';
import { User, UserRole } from '../types';
import { api } from '../api';
import { Shield, Key, Lock, Unlock, UserCheck, AlertTriangle, CheckCircle2, X, RefreshCw } from 'lucide-react';

interface AuthLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User | null;
  onLoginSuccess: (user: User) => void;
}

const PRESET_ACCOUNTS = [
  {
    role: 'ADMIN' as UserRole,
    name: 'Devansh Tyagi',
    email: 'devansh.tyagi@intelera.com',
    password: 'password123',
    desc: 'Full Access: System Prompts, All Leaves, Timesheets, Audits, Sync',
    badge: 'bg-purple-100 text-purple-800 border-purple-300'
  },
  {
    role: 'HR_MANAGER' as UserRole,
    name: 'Vikram Malhotra',
    email: 'vikram.malhotra@intelera.com',
    password: 'password123',
    desc: 'Manager Access: Leave Approvals, Department Timesheets & Reports',
    badge: 'bg-blue-100 text-blue-800 border-blue-300'
  },
  {
    role: 'HR_ASSOCIATE' as UserRole,
    name: 'Priya Patel',
    email: 'priya.patel@intelera.com',
    password: 'password123',
    desc: 'Associate Access: Onboarding Wizard, Document Verification, View Leaves',
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-300'
  },
  {
    role: 'EMPLOYEE' as UserRole,
    name: 'Aarav Sharma',
    email: 'aarav.sharma@intelera.com',
    password: 'password123',
    desc: 'Employee Access: View/Apply Own Leaves, Log Timesheets, AI HR Chat',
    badge: 'bg-amber-100 text-amber-800 border-amber-300'
  },
  {
    role: 'EMPLOYEE' as UserRole,
    name: 'Sneha Kulkarni',
    email: 'sneha.kulkarni@intelera.com',
    password: 'password123',
    desc: 'Isolated Employee: Tests BOLA data isolation against Aarav Sharma',
    badge: 'bg-slate-100 text-slate-800 border-slate-300'
  }
];

export const AuthLoginModal: React.FC<AuthLoginModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onLoginSuccess
}) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ action: string; status: 'ALLOW' | 'BLOCK'; message: string; httpCode: number } | null>(null);

  if (!isOpen) return null;

  const handleLogin = async (e?: React.FormEvent, customEmail?: string, customPassword?: string) => {
    if (e) e.preventDefault();
    setError(null);
    setLoading(true);
    setTestResult(null);

    const loginEmail = customEmail || email;
    const loginPass = customPassword || password;

    try {
      await api.login(loginEmail, loginPass);
      const user = await api.getCurrentUser();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (acc: typeof PRESET_ACCOUNTS[0]) => {
    setEmail(acc.email);
    setPassword(acc.password);
    handleLogin(undefined, acc.email, acc.password);
  };

  const runBoundaryTest = async (testType: 'SYSTEM_PROMPTS' | 'OTHER_EMPLOYEE_BALANCE') => {
    setLoading(true);
    setTestResult(null);
    try {
      if (testType === 'SYSTEM_PROMPTS') {
        const res = await api.getPrompts();
        setTestResult({
          action: 'Inspect System Prompts (/agents/prompts)',
          status: 'ALLOW',
          httpCode: 200,
          message: `ACCESS GRANTED: Found ${res.prompts?.length || 0} active dynamic agent prompts in DB.`
        });
      } else if (testType === 'OTHER_EMPLOYEE_BALANCE') {
        // Attempt to access other employee balance
        const foreignId = currentUser?.id === 'usr-aarav' ? 'usr-sneha' : 'usr-aarav';
        const res = await api.getLeaveBalances(foreignId);
        setTestResult({
          action: 'Query Foreign Employee Balance (BOLA Check)',
          status: 'ALLOW',
          httpCode: 200,
          message: `ACCESS GRANTED: Authorized for employee ${foreignId} (${res.balances?.length} quotas).`
        });
      }
    } catch (err: any) {
      const code = err?.response?.status || 403;
      const detail = err?.response?.data?.detail || 'Access Forbidden';
      setTestResult({
        action: testType === 'SYSTEM_PROMPTS' ? 'Inspect System Prompts' : 'Query Foreign Employee Balance',
        status: 'BLOCK',
        httpCode: code,
        message: `🛡️ SECURITY BLOCKED (HTTP ${code}): ${detail}`
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/30 text-blue-400 flex items-center justify-center border border-blue-500/30">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">Authentication & RBAC Boundary Inspector</h3>
              <p className="text-xs text-slate-400">Verify user credentials, information boundaries & BOLA defenses</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Active User Badge & Privacy Scope */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Authenticated Identity</span>
              <div className="flex items-center gap-2 mt-1">
                <span className="font-bold text-slate-900">{currentUser?.full_name || 'Anonymous / Guest'}</span>
                <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-blue-100 text-blue-800 font-semibold">
                  {currentUser?.role || 'NONE'}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{currentUser?.email} • {currentUser?.department}</p>
            </div>
            <div className="flex flex-wrap gap-1.5 sm:max-w-xs">
              {currentUser?.permissions?.slice(0, 4).map((p) => (
                <span key={p} className="text-[10px] font-mono px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700">
                  {p}
                </span>
              ))}
              {(currentUser?.permissions?.length || 0) > 4 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">
                  +{(currentUser?.permissions?.length || 0) - 4} more
                </span>
              )}
            </div>
          </div>

          {/* Quick 1-Click Role Switcher */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Select Test Persona (1-Click Authenticate)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {PRESET_ACCOUNTS.map((acc) => {
                const isSelected = currentUser?.email === acc.email;
                return (
                  <button
                    key={acc.email}
                    onClick={() => handleQuickLogin(acc)}
                    className={`p-3 rounded-xl text-left border transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'border-blue-600 bg-blue-50/50 shadow-sm ring-1 ring-blue-500'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/80'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-semibold text-sm text-slate-900">{acc.name}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${acc.badge}`}>
                        {acc.role}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">{acc.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Direct Credentials Login Form */}
          <form onSubmit={handleLogin} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Manual Credentials Sign-In</h4>
            {error && (
              <div className="p-2.5 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-600 mb-1">Corporate Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="devansh.tyagi@intelera.com"
                  required
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-600 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full text-xs font-semibold py-2 px-4 rounded-lg bg-slate-900 text-white hover:bg-slate-800 transition flex items-center justify-center gap-2 shadow-sm"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
              <span>Sign In with Password</span>
            </button>
          </form>

          {/* Live Security Boundary Test Panel */}
          <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-blue-950 uppercase tracking-wider">Live RBAC & Information Boundary Tests</h4>
                <p className="text-xs text-blue-800">Test if active persona can probe restricted resources</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => runBoundaryTest('SYSTEM_PROMPTS')}
                disabled={loading}
                className="text-xs px-3 py-1.5 rounded-lg bg-white border border-blue-300 text-blue-900 font-medium hover:bg-blue-100/60 shadow-2xs flex items-center gap-1.5"
              >
                <Lock className="w-3.5 h-3.5 text-blue-600" />
                <span>Test System Prompts Access (Admin Only)</span>
              </button>

              <button
                onClick={() => runBoundaryTest('OTHER_EMPLOYEE_BALANCE')}
                disabled={loading}
                className="text-xs px-3 py-1.5 rounded-lg bg-white border border-blue-300 text-blue-900 font-medium hover:bg-blue-100/60 shadow-2xs flex items-center gap-1.5"
              >
                <Shield className="w-3.5 h-3.5 text-blue-600" />
                <span>Test Foreign Employee Quota Access (BOLA)</span>
              </button>
            </div>

            {testResult && (
              <div
                className={`p-3 rounded-xl border text-xs flex items-start gap-2.5 animate-in fade-in ${
                  testResult.status === 'ALLOW'
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                    : 'bg-red-50 border-red-300 text-red-900'
                }`}
              >
                {testResult.status === 'ALLOW' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="font-semibold">{testResult.action} [HTTP {testResult.httpCode}]</div>
                  <p className="mt-0.5 font-mono text-[11px]">{testResult.message}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
