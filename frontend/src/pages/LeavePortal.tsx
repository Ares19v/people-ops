import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, LeaveBalanceSummary, LeaveApplication } from '../types';
import { Calendar, CheckCircle2, Clock, XCircle, AlertCircle, Plus } from 'lucide-react';

interface LeavePortalProps {
  currentUser: User | null;
  currentRole: UserRole;
  balances: LeaveBalanceSummary | null;
  onRefreshBalances: () => void;
}

export const LeavePortal: React.FC<LeavePortalProps> = ({
  currentUser,
  currentRole,
  balances,
  onRefreshBalances,
}) => {
  const [applications, setApplications] = useState<LeaveApplication[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<LeaveApplication[]>([]);
  const [activeTab, setActiveTab] = useState<'my_leaves' | 'approvals'>('my_leaves');
  const [showApplyModal, setShowApplyModal] = useState(false);

  // Form state
  const [leaveType, setLeaveType] = useState('EL');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const loadApplications = async () => {
    try {
      const myApps = await api.getLeaveApplications();
      setApplications(myApps);
      if (currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') {
        const allPending = await api.getLeaveApplications('SUBMITTED', true);
        setPendingApprovals(allPending);
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadApplications();
  }, [currentRole]);

  const handleApply = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!startDate || !endDate || !reason.trim()) {
      setErrorMsg('Please fill in all required fields.');
      return;
    }
    setSubmitting(true);
    try {
      await api.applyLeave({
        leave_type: leaveType,
        start_date: startDate,
        end_date: endDate,
        reason: reason.trim(),
      });
      setShowApplyModal(false);
      setReason('');
      onRefreshBalances();
      await loadApplications();
      alert('Leave application submitted successfully!');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to submit leave.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecide = async (id: string, decision: 'APPROVE' | 'REJECT') => {
    const comments = prompt(`Enter comments for ${decision.toLowerCase()} (optional):`) || undefined;
    try {
      await api.decideLeave(id, decision, comments);
      onRefreshBalances();
      await loadApplications();
      alert(`Leave application ${decision.toLowerCase()}d!`);
    } catch (err: any) {
      alert(`Decision failed: ${err.response?.data?.detail || err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Leave Management & Balance Ledger</h2>
          <p className="text-xs text-slate-500 mt-1">
            Authoritative balance ledger compliant with Maharashtra Shops & Establishments Act, 2017.
          </p>
        </div>
        <button
          onClick={() => setShowApplyModal(true)}
          className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          Apply for Leave
        </button>
      </div>

      {/* Verified Balances Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {balances?.balances.map((b) => (
          <div key={b.leave_type} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700">
                {b.leave_type === 'EL' && 'Earned Leave (EL)'}
                {b.leave_type === 'CL' && 'Casual Leave (CL)'}
                {b.leave_type === 'SL' && 'Sick Leave (SL)'}
                {b.leave_type === 'LWP' && 'Leave Without Pay'}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">
                {b.leave_type}
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="text-3xl font-extrabold text-slate-900">
                {b.leave_type === 'LWP' ? '∞' : b.available_balance}
              </span>
              <span className="text-xs text-slate-500 font-medium">days available</span>
            </div>
            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span>Used: {b.used_days}d</span>
              <span>Pending: {b.pending_days}d</span>
              {b.carry_forwarded > 0 && <span>Carry: {b.carry_forwarded}d</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('my_leaves')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'my_leaves'
              ? 'bg-emerald-50 text-emerald-700'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          My Leave History ({applications.length})
        </button>
        {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
          <button
            onClick={() => setActiveTab('approvals')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
              activeTab === 'approvals'
                ? 'bg-emerald-50 text-emerald-700'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>Manager Approval Inbox</span>
            {pendingApprovals.length > 0 && (
              <span className="w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] flex items-center justify-center font-bold">
                {pendingApprovals.length}
              </span>
            )}
          </button>
        )}
      </div>

      {/* Applications Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        {activeTab === 'my_leaves' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                <tr>
                  <th className="p-3.5">Type</th>
                  <th className="p-3.5">Dates</th>
                  <th className="p-3.5">Days</th>
                  <th className="p-3.5">Reason</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Applied At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {applications.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-slate-400">
                      No leave applications found. Click "Apply for Leave" above.
                    </td>
                  </tr>
                ) : (
                  applications.map((app) => (
                    <tr key={app.id} className="hover:bg-slate-50/50">
                      <td className="p-3.5 font-bold text-slate-900">{app.leave_type}</td>
                      <td className="p-3.5">
                        {app.start_date} to {app.end_date}
                      </td>
                      <td className="p-3.5 font-semibold">{app.total_days}</td>
                      <td className="p-3.5 text-slate-600 max-w-xs truncate">{app.reason}</td>
                      <td className="p-3.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                            app.status === 'APPROVED'
                              ? 'bg-emerald-100 text-emerald-800'
                              : app.status === 'REJECTED'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {app.status === 'APPROVED' && <CheckCircle2 className="w-3 h-3" />}
                          {app.status === 'REJECTED' && <XCircle className="w-3 h-3" />}
                          {app.status === 'SUBMITTED' && <Clock className="w-3 h-3" />}
                          {app.status}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-400">{new Date(app.applied_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                <tr>
                  <th className="p-3.5">Employee ID</th>
                  <th className="p-3.5">Type</th>
                  <th className="p-3.5">Dates</th>
                  <th className="p-3.5">Days</th>
                  <th className="p-3.5">Reason</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pendingApprovals.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-slate-400">
                      Inbox zero: No pending leave approvals awaiting review.
                    </td>
                  </tr>
                ) : (
                  pendingApprovals.map((app) => (
                    <tr key={app.id} className="hover:bg-slate-50/50">
                      <td className="p-3.5 font-mono text-[11px] text-slate-500">{app.user_id.slice(0, 8)}...</td>
                      <td className="p-3.5 font-bold text-slate-900">{app.leave_type}</td>
                      <td className="p-3.5">
                        {app.start_date} to {app.end_date}
                      </td>
                      <td className="p-3.5 font-semibold">{app.total_days}</td>
                      <td className="p-3.5 text-slate-600 max-w-xs">{app.reason}</td>
                      <td className="p-3.5 text-right space-x-2">
                        <button
                          onClick={() => handleDecide(app.id, 'APPROVE')}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-semibold text-[11px]"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleDecide(app.id, 'REJECT')}
                          className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white rounded font-semibold text-[11px]"
                        >
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Apply Modal */}
      {showApplyModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-4">Submit Leave Application</h3>
            {errorMsg && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
            <form onSubmit={handleApply} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Leave Category</label>
                <select
                  value={leaveType}
                  onChange={(e) => setLeaveType(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                >
                  <option value="EL">Earned Leave (EL) - 18d Annual</option>
                  <option value="CL">Casual Leave (CL) - 8d Statutory</option>
                  <option value="SL">Sick Leave (SL) - 10d Medical</option>
                  <option value="LWP">Leave Without Pay (LWP)</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Reason for Leave</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Provide brief context for your reporting manager..."
                  rows={3}
                  className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                  required
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowApplyModal(false)}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-semibold shadow-md shadow-emerald-600/20"
                >
                  {submitting ? 'Validating...' : 'Submit Application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
