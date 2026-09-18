import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, LeaveBalanceSummary, LeaveApplication } from '../types';
import { Calendar, CheckCircle2, Clock, XCircle, AlertCircle, Plus, ShieldCheck } from 'lucide-react';

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
        reason,
      });
      setShowApplyModal(false);
      setStartDate('');
      setEndDate('');
      setReason('');
      onRefreshBalances();
      await loadApplications();
      alert('Leave application submitted successfully! Routed to manager inbox.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to submit leave application.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecision = async (applicationId: string, decision: 'APPROVE' | 'REJECT') => {
    const comments = prompt(`Enter comments for ${decision.toLowerCase()} (optional):`) || undefined;
    try {
      await api.decideLeave(applicationId, decision, comments);
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
          <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-600" />
            Leave Ledger & Balance Tracking
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Authoritative balance ledger compliant with Maharashtra Shops & Establishments Act, 2017.
          </p>
        </div>
        <button
          onClick={() => setShowApplyModal(true)}
          className="btn-pill-dark self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Apply for Leave</span>
        </button>
      </div>

      {/* Verified Balances Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {balances?.balances.map((b) => (
          <div key={b.leave_type} className="card-olixer p-5">
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-xs text-slate-700">
                {b.leave_type === 'EL' && 'Earned Leave (EL)'}
                {b.leave_type === 'CL' && 'Casual Leave (CL)'}
                {b.leave_type === 'SL' && 'Sick Leave (SL)'}
                {b.leave_type === 'LWP' && 'Leave Without Pay'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">
                {b.leave_type}
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-1.5">
              <span className="font-display text-3xl font-extrabold text-slate-900">
                {b.leave_type === 'LWP' ? '∞' : b.available_balance}
              </span>
              <span className="text-xs text-slate-500 font-medium">days available</span>
            </div>
            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-medium">
              <span>Used: {b.used_days}d</span>
              <span>Pending: {b.pending_days}d</span>
              {b.carry_forwarded > 0 && <span>Carry: {b.carry_forwarded}d</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200/80 pb-2">
        <button
          onClick={() => setActiveTab('my_leaves')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'my_leaves'
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          My Leave History ({applications.length})
        </button>
        {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
          <button
            onClick={() => setActiveTab('approvals')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'approvals'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span>Manager Approval Inbox</span>
            {pendingApprovals.length > 0 && (
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] flex items-center justify-center font-bold">
                {pendingApprovals.length}
              </span>
            )}
          </button>
        )}
      </div>

      {/* Applications Table */}
      <div className="card-olixer p-0 overflow-hidden">
        {activeTab === 'my_leaves' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50/80 text-slate-600 font-display font-bold border-b border-slate-200/70">
                <tr>
                  <th className="p-4">Type</th>
                  <th className="p-4">Dates</th>
                  <th className="p-4">Days</th>
                  <th className="p-4">Reason</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Applied At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {applications.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400">
                      No leave applications found. Click "Apply for Leave" above.
                    </td>
                  </tr>
                ) : (
                  applications.map((app) => (
                    <tr key={app.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="p-4 font-display font-bold text-slate-900">{app.leave_type}</td>
                      <td className="p-4 font-medium">
                        {app.start_date} &rarr; {app.end_date}
                      </td>
                      <td className="p-4 font-bold">{app.total_days}</td>
                      <td className="p-4 text-slate-600 max-w-xs truncate">{app.reason}</td>
                      <td className="p-4">
                        <span
                          className={
                            app.status === 'APPROVED'
                              ? 'badge-statutory-green'
                              : app.status === 'REJECTED'
                              ? 'badge-statutory-red'
                              : 'badge-statutory-amber'
                          }
                        >
                          {app.status === 'APPROVED' && <CheckCircle2 className="w-3 h-3" />}
                          {app.status === 'REJECTED' && <XCircle className="w-3 h-3" />}
                          {app.status === 'SUBMITTED' && <Clock className="w-3 h-3" />}
                          {app.status}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400">{new Date(app.applied_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50/80 text-slate-600 font-display font-bold border-b border-slate-200/70">
                <tr>
                  <th className="p-4">Applicant</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Dates</th>
                  <th className="p-4">Days</th>
                  <th className="p-4">Reason</th>
                  <th className="p-4 text-right">Manager Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pendingApprovals.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400">
                      All pending applications have been decided. Inbox is clear!
                    </td>
                  </tr>
                ) : (
                  pendingApprovals.map((app) => (
                    <tr key={app.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="p-4 font-display font-semibold text-slate-900">{app.user_id}</td>
                      <td className="p-4 font-bold">{app.leave_type}</td>
                      <td className="p-4 font-medium">
                        {app.start_date} &rarr; {app.end_date}
                      </td>
                      <td className="p-4 font-bold">{app.total_days}</td>
                      <td className="p-4 text-slate-600 max-w-xs truncate">{app.reason}</td>
                      <td className="p-4 text-right space-x-2">
                        <button
                          onClick={() => handleDecision(app.id, 'APPROVE')}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleDecision(app.id, 'REJECT')}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
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

      {/* Apply Leave Modal */}
      {showApplyModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-olixer max-w-lg w-full bg-white p-6 sm:p-8 shadow-2xl relative">
            <h3 className="font-display text-lg font-bold text-slate-900 mb-1">
              Apply for Statutory Leave
            </h3>
            <p className="text-xs text-slate-500 mb-6">
              Requests are validated against your available ledger and the Maharashtra Shops & Establishments Act 2017.
            </p>

            {errorMsg && (
              <div className="p-3 mb-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleApply} className="space-y-4 text-xs">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Leave Category</label>
                <select
                  value={leaveType}
                  onChange={(e) => setLeaveType(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 bg-white font-medium focus:outline-none focus:border-blue-600"
                >
                  <option value="EL">Earned Leave (EL) &bull; Max 45-day accumulation</option>
                  <option value="CL">Casual Leave (CL) &bull; 8 days/yr</option>
                  <option value="SL">Sick Leave (SL) &bull; Medical recovery</option>
                  <option value="LWP">Leave Without Pay (LWP)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Reason & Notes</label>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="State reason for absence..."
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>

              <div className="pt-4 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowApplyModal(false)}
                  className="btn-pill-outline"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-pill-dark"
                >
                  {submitting ? 'Validating...' : 'Submit to Leave Agent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
