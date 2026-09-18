import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetEntry, TimesheetReportSummary } from '../types';
import { Clock, CheckCircle2, Plus, AlertCircle, FileText, Check, X, ShieldCheck } from 'lucide-react';

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
      const projs = await api.getProjects();
      setProjects(projs);
      if (projs.length > 0 && !selectedProject) {
        setSelectedProject(projs[0].id);
      }
      const rep = await api.getTimesheetReport();
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
          <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
            <Clock className="w-5 h-5 text-blue-600" />
            Timesheet Management & Overtime Audit
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Logs project hours, verifies Maharashtra 9h/day & 48h/week statutory limits, and audits overtime.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && submittedEntries.length ? (
            <button
              onClick={() => handleBatchDecision('APPROVE')}
              className="btn-pill-outline"
            >
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span>Approve All ({submittedEntries.length})</span>
            </button>
          ) : null}
          <button
            onClick={() => setShowLogModal(true)}
            className="btn-pill-dark"
          >
            <Plus className="w-4 h-4" />
            <span>Log Working Hours</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <span className="font-display font-semibold text-slate-600">Billable Hours</span>
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
            <span className="font-display font-semibold text-slate-600">Statutory Overtime</span>
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
            <span className="font-display font-semibold text-slate-600">Pending Review</span>
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
      <div className="card-olixer p-0 overflow-hidden">
        <div className="px-5 py-3.5 bg-slate-50/50 border-b border-slate-200/70 flex items-center justify-between">
          <span className="font-display font-bold text-xs text-slate-900">
            Recorded Time Entries ({allEntries.length})
          </span>
          <span className="text-[11px] text-slate-500">Sorted by Date (Recent First)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50/80 text-slate-600 font-display font-bold border-b border-slate-200/70">
              <tr>
                <th className="p-4">Date</th>
                <th className="p-4">Project</th>
                <th className="p-4">Task Description</th>
                <th className="p-4">Hours</th>
                <th className="p-4">Billable</th>
                <th className="p-4">Status</th>
                <th className="p-4">Logged By</th>
                {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
                  <th className="p-4 text-right">Action</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {allEntries.length === 0 ? (
                <tr>
                  <td colSpan={currentRole === 'HR_MANAGER' || currentRole === 'ADMIN' ? 8 : 7} className="p-8 text-center text-slate-400">
                    No timesheet entries recorded yet. Click "Log Working Hours" to submit.
                  </td>
                </tr>
              ) : (
                allEntries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="p-4 font-semibold text-slate-900">{entry.entry_date}</td>
                    <td className="p-4">
                      <span className="font-display font-bold text-slate-900">{entry.project_name || 'Client Engagement'}</span>
                    </td>
                    <td className="p-4 text-slate-600 max-w-sm truncate">{entry.task_name}</td>
                    <td className="p-4 font-display font-bold text-slate-900">
                      {entry.hours.toFixed(1)}h
                      {entry.hours > 9 && (
                        <span className="ml-2 text-[10px] text-amber-600 font-semibold bg-amber-50 px-1.5 py-0.5 rounded">
                          +{(entry.hours - 9).toFixed(1)}h OT
                        </span>
                      )}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${entry.is_billable ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                        {entry.is_billable ? 'Billable' : 'Internal'}
                      </span>
                    </td>
                    <td className="p-4">
                      <span
                        className={
                          entry.status === 'APPROVED'
                            ? 'badge-statutory-green'
                            : entry.status === 'REJECTED'
                            ? 'badge-statutory-red'
                            : 'badge-statutory-amber'
                        }
                      >
                        {entry.status === 'APPROVED' && <CheckCircle2 className="w-3 h-3" />}
                        {entry.status === 'SUBMITTED' && <Clock className="w-3 h-3" />}
                        {entry.status}
                      </span>
                    </td>
                    <td className="p-4 text-slate-500 font-medium">{entry.employee_name || 'Member'}</td>
                    {(currentRole === 'HR_MANAGER' || currentRole === 'ADMIN') && (
                      <td className="p-4 text-right">
                        {entry.status === 'SUBMITTED' ? (
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              onClick={() => handleSingleDecision(entry.id, 'APPROVE')}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[11px] font-semibold transition-all shadow-sm"
                              title="Approve this entry"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleSingleDecision(entry.id, 'REJECT')}
                              className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-semibold transition-all shadow-sm"
                              title="Reject this entry"
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-[11px] italic">Decided</span>
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

      {/* Log Time Modal */}
      {showLogModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-olixer max-w-lg w-full bg-white p-6 sm:p-8 shadow-2xl relative">
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
