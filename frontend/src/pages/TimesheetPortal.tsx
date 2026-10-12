import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetEntry, TimesheetReportSummary } from '../types';
import { Clock, CheckCircle2, Plus, AlertCircle, FileText, Check, X, ShieldCheck, Building2, Calendar } from 'lucide-react';
import { FeatureExplainerIcon } from '../components/FeatureExplainerIcon';
import { ZohoPeopleIntegrationHub } from '../components/ZohoPeopleIntegrationHub';
import { EmployeeAvatarChip, StatusBadge, HoursBadge } from '../utils/formatters';

interface TimesheetPortalProps {
  currentUser: User | null;
  currentRole: UserRole;
  initialOpenLogModal?: boolean;
}

export const TimesheetPortal: React.FC<TimesheetPortalProps> = ({
  currentUser,
  currentRole,
  initialOpenLogModal = false,
}) => {
  const [subView, setSubView] = useState<'timesheets' | 'zoho'>('timesheets');
  const [projects, setProjects] = useState<Project[]>([]);
  const [report, setReport] = useState<TimesheetReportSummary | null>(null);
  const [showLogModal, setShowLogModal] = useState(initialOpenLogModal);
  const [selectedProject, setSelectedProject] = useState('');
  const [taskName, setTaskName] = useState('');
  const [entryDate, setEntryDate] = useState(new Date().toISOString().split('T')[0]);
  const [hours, setHours] = useState(8.0);
  const [isBillable, setIsBillable] = useState(true);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const loadData = async () => {
    try {
      const [projs, rep] = await Promise.all([
        api.getProjects(),
        api.getTimesheetReport(),
      ]);
      setProjects(projs);
      if (projs.length > 0 && !selectedProject) {
        setSelectedProject(projs[0].id);
      }
      setReport(rep);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentRole]);

  const allEntries = report?.entries || [];
  const submittedEntries = allEntries.filter((e) => e.status === 'SUBMITTED');
  const approvedEntries = allEntries.filter((e) => e.status === 'APPROVED');
  const overtimeHours = allEntries.reduce((acc, e) => acc + Math.max(0, e.hours - 9), 0);

  const handleLogTime = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!selectedProject || !taskName.trim() || hours <= 0) {
      setErrorMsg('Please complete all required timesheet fields.');
      return;
    }
    setSubmitting(true);
    try {
      await api.logTimesheet({
        project_id: selectedProject,
        task_name: taskName.trim(),
        entry_date: entryDate,
        hours: Number(hours),
        is_billable: isBillable,
        notes: notes.trim() || undefined,
      });
      setShowLogModal(false);
      setTaskName('');
      setNotes('');
      setHours(8.0);
      await loadData();
      alert('Time entry logged! Evaluated against Maharashtra 9h/day cap.');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to log timesheet entry.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBatchDecision = async (decision: 'APPROVE' | 'REJECT') => {
    if (!submittedEntries.length) return;
    const ids = submittedEntries.map((e) => e.id);
    try {
      await api.decideTimesheets(ids, decision);
      await loadData();
      alert(`Batch ${decision.toLowerCase()} completed for ${ids.length} entries.`);
    } catch (err: any) {
      alert(`Decision error: ${err.message}`);
    }
  };

  const handleSingleDecision = async (entryId: string, decision: 'APPROVE' | 'REJECT') => {
    try {
      await api.decideTimesheets([entryId], decision);
      await loadData();
    } catch (err: any) {
      alert(`Decision error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSubView((prev) => (prev === 'timesheets' ? 'zoho' : 'timesheets'))}
              className="p-1 -ml-1 rounded-xl hover:bg-blue-50 active:scale-95 transition-all text-blue-600 focus:outline-none group flex items-center justify-center cursor-pointer"
              title={subView === 'timesheets' ? "Switch to Zoho People HRMS Hub" : "Back to Timesheets Grid"}
            >
              {subView === 'timesheets' ? (
                <Clock className="w-5 h-5 text-blue-600 group-hover:scale-110 transition-transform" />
              ) : (
                <Building2 className="w-5 h-5 text-blue-600 group-hover:scale-110 transition-transform" />
              )}
            </button>
            <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
              {subView === 'timesheets' ? 'Timesheet Management & Overtime Audit' : 'Zoho People HRMS Live Integration Hub'}
            </h2>
            <FeatureExplainerIcon featureKey="timesheet_grid" />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {subView === 'timesheets'
              ? 'Logs project hours, verifies Maharashtra 9h/day & 48h/week statutory limits, and audits overtime.'
              : 'Live OAuth 2.0 biometric attendance synchronization, employee hierarchy, and audit ledger.'}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {subView === 'zoho' && (
            <button
              onClick={() => setSubView('timesheets')}
              className="btn-pill-outline text-xs"
            >
              <Clock className="w-3.5 h-3.5 text-blue-600" />
              <span>Back to Timesheets</span>
            </button>
          )}

          {subView === 'timesheets' && (
            <>
              {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && submittedEntries.length ? (
                <button
                  onClick={() => handleBatchDecision('APPROVE')}
                  className="btn-pill-outline"
                >
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Approve All ({submittedEntries.length})</span>
                </button>
              ) : null}
              <div className="flex items-center">
                <button
                  onClick={() => setShowLogModal(true)}
                  className="btn-pill-dark"
                >
                  <Plus className="w-4 h-4" />
                  <span>Log Working Hours</span>
                </button>
                <FeatureExplainerIcon featureKey="quarterly_overtime_cap" />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Zoho Integration Hub SubView */}
      {subView === 'zoho' && (
        <ZohoPeopleIntegrationHub />
      )}

      {/* Timesheets Grid SubView */}
      {subView === 'timesheets' && (
        <>
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Total Hours</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-slate-900">
              {report?.total_hours.toFixed(1) || '0.0'}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs total</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              Logged across all projects
            </span>
          </div>
        </div>

        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-600">Billable Hours</span>
              <FeatureExplainerIcon featureKey="billable_ratio_tracking" />
            </div>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-emerald-600">
              {report?.billable_hours.toFixed(1) || '0.0'}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs client-billed</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              {(((report?.billable_hours || 0) / Math.max(1, report?.total_hours || 1)) * 100).toFixed(0)}% Utilization Rate
            </span>
          </div>
        </div>

        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-600">Statutory Overtime</span>
              <FeatureExplainerIcon featureKey="overtime_statutory_audit" />
            </div>
            <span className="p-2 rounded-xl bg-amber-50 text-amber-600">
              <AlertCircle className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-amber-600">
              {overtimeHours.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs (&gt;9h/day)</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-amber">
              Sec 15: 2x Regular Pay
            </span>
          </div>
        </div>

        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center">
              <span className="font-display font-semibold text-slate-600">Pending Review</span>
              <FeatureExplainerIcon featureKey="timesheet_manager_approval" />
            </div>
            <span className="p-2 rounded-xl bg-purple-50 text-purple-600">
              <FileText className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-purple-600">
              {submittedEntries.length}
            </span>
            <span className="text-xs text-slate-500 font-medium">entries</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <ShieldCheck className="w-3 h-3" />
              Awaiting manager signoff
            </span>
          </div>
        </div>
      </div>

      {/* Timesheet Entries Table */}
      <div className="card-olixer p-0 overflow-hidden shadow-xs border border-slate-200/80 bg-white">
        <div className="p-4 bg-slate-50/90 border-b border-slate-200/80 flex items-center justify-between">
          <span className="font-display font-bold text-xs text-slate-900 uppercase tracking-wider">
            Recorded Time Entries ({allEntries.length})
          </span>
          <span className="text-[11px] text-slate-500 font-medium">Sorted by Date (Recent First)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200/80">
              <tr>
                <th className="py-3.5 px-4 font-bold text-[11px]">Logged By</th>
                <th className="py-3.5 px-4 font-bold text-[11px]">Date</th>
                <th className="py-3.5 px-4 font-bold text-[11px]">Project & Task</th>
                <th className="py-3.5 px-4 font-bold text-[11px]">Hours & Overtime</th>
                <th className="py-3.5 px-4 font-bold text-[11px]">Approval Status</th>
                {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
                  <th className="py-3.5 px-4 font-bold text-[11px] text-right">Manager Action</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {allEntries.length === 0 ? (
                <tr>
                  <td colSpan={currentRole === 'HR_MANAGER' || currentRole === 'ADMIN' ? 6 : 5} className="py-12 px-4 text-center">
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      <Clock className="w-8 h-8 text-slate-300 mb-2 stroke-[1.5]" />
                      <p className="font-display font-semibold text-slate-600 text-sm">No timesheet entries recorded</p>
                      <p className="text-xs text-slate-400 mt-0.5">Click "Log Working Hours" above to submit hours.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                allEntries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50/70 transition-colors group">
                    <td className="py-3.5 px-4">
                      <EmployeeAvatarChip userIdentifier={entry.user_id} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-slate-700 font-medium whitespace-nowrap">
                      {new Date(entry.entry_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col">
                        <span className="font-display font-bold text-slate-900 text-xs">
                          {entry.project_name || 'Client Engagement'}
                        </span>
                        <span className="text-slate-600 text-[11px] truncate max-w-sm mt-0.5">
                          {entry.task_name}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <HoursBadge hours={entry.hours} isBillable={entry.is_billable} />
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={entry.status} />
                    </td>
                    {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
                      <td className="py-3.5 px-4 text-right">
                        {entry.status === 'SUBMITTED' ? (
                          <div className="inline-flex items-center gap-1.5 justify-end">
                            <button
                              onClick={() => handleSingleDecision(entry.id, 'APPROVE')}
                              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer inline-flex items-center gap-1"
                              title="Approve this entry"
                            >
                              <Check className="w-3 h-3" />
                              Approve
                            </button>
                            <button
                              onClick={() => handleSingleDecision(entry.id, 'REJECT')}
                              className="px-3 py-1 bg-rose-600 hover:bg-rose-700 active:scale-95 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer inline-flex items-center gap-1"
                              title="Reject this entry"
                            >
                              <X className="w-3 h-3" />
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-xs font-medium">Decided</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )}

      {/* Log Time Modal */}
      {showLogModal && (
        <div 
          className="fixed inset-0 z-50 popup-screen-blur flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowLogModal(false); }}
        >
          <div className="card-olixer modal-animate max-w-lg w-full bg-white p-6 sm:p-8 glass-modal-card relative">
            <button
              onClick={() => setShowLogModal(false)}
              className="absolute top-6 right-6 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="font-display text-lg font-bold text-slate-900 mb-1">
              Log Working Hours
            </h3>
            <p className="text-xs text-slate-500 mb-6">
              Track project work and automatically verify daily/weekly overtime thresholds under Section 15.
            </p>

            {errorMsg && (
              <div className="p-3 mb-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleLogTime} className="space-y-4 text-xs">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Project</label>
                <select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-200 bg-white font-medium focus:outline-none focus:border-blue-600"
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.code}) &bull; {p.client_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Task Description</label>
                <input
                  type="text"
                  value={taskName}
                  onChange={(e) => setTaskName(e.target.value)}
                  placeholder="e.g. Agent workflow optimization & NeMo rule fine-tuning"
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1">Date</label>
                  <input
                    type="date"
                    value={entryDate}
                    onChange={(e) => setEntryDate(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1">Hours Worked</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="24"
                    value={hours}
                    onChange={(e) => setHours(Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="billableCheck"
                  checked={isBillable}
                  onChange={(e) => setIsBillable(e.target.checked)}
                  className="w-4 h-4 rounded text-blue-600 focus:ring-0 cursor-pointer"
                />
                <label htmlFor="billableCheck" className="text-xs text-slate-700 font-medium cursor-pointer">
                  Mark this entry as billable to client
                </label>
              </div>

              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Notes / Blockers (Optional)</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Optional details..."
                  className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
                />
              </div>

              <div className="pt-4 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowLogModal(false)}
                  className="btn-pill-outline"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-pill-dark"
                >
                  {submitting ? 'Logging...' : 'Submit to Timesheet Agent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
