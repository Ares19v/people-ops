import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetEntry, TimesheetReportSummary } from '../types';
import { Clock, CheckCircle2, Plus, AlertCircle, FileText, Check, X } from 'lucide-react';

interface TimesheetPortalProps {
  currentUser: User | null;
  currentRole: UserRole;
}

export const TimesheetPortal: React.FC<TimesheetPortalProps> = ({ currentUser, currentRole }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [report, setReport] = useState<TimesheetReportSummary | null>(null);
  const [showLogModal, setShowLogModal] = useState(false);
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
      await loadData();
      alert('Timesheet entry recorded successfully!');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to log hours.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Timesheet Management</h2>
          <p className="text-xs text-slate-500 mt-1">
            Standard: 8 hrs/day (40 hrs/week). Maximum daily threshold: 16 hrs.
          </p>
        </div>
        <button
          onClick={() => setShowLogModal(true)}
          className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          Log Daily Hours
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Total Hours Logged</span>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {report?.total_hours.toFixed(1) || '0.0'} hrs
          </div>
          <div className="text-[11px] text-slate-500 mt-1">{report?.entry_count || 0} recorded tasks</div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Billable Hours</span>
          <div className="mt-2 text-2xl font-bold text-emerald-600">
            {report?.billable_hours.toFixed(1) || '0.0'} hrs
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">
            {report?.total_hours ? Math.round((report.billable_hours / report.total_hours) * 100) : 0}% billability
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Non-Billable Hours</span>
          <div className="mt-2 text-2xl font-bold text-slate-700">
            {report?.non_billable_hours.toFixed(1) || '0.0'} hrs
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Internal operations</div>
        </div>
      </div>

      {/* Entries Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">Recent Timesheet Entries</h3>
          <span className="text-xs text-slate-500">Auto-validating daily hours limit</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
              <tr>
                <th className="p-3.5">Date</th>
                <th className="p-3.5">Employee</th>
                <th className="p-3.5">Project</th>
                <th className="p-3.5">Task Description</th>
                <th className="p-3.5">Hours</th>
                <th className="p-3.5">Billable</th>
                <th className="p-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(!report?.entries || report.entries.length === 0) ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-400">
                    No timesheet records found. Click "Log Daily Hours" to start.
                  </td>
                </tr>
              ) : (
                report.entries.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50/50">
                    <td className="p-3.5 font-medium">{e.entry_date}</td>
                    <td className="p-3.5 font-semibold text-slate-900">{e.employee_name || 'Current User'}</td>
                    <td className="p-3.5 text-slate-600">{e.project_name || 'Internal'}</td>
                    <td className="p-3.5 font-medium text-slate-800">{e.task_name}</td>
                    <td className="p-3.5 font-bold">{e.hours.toFixed(1)}</td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          e.is_billable ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {e.is_billable ? 'Billable' : 'Non-Billable'}
                      </span>
                    </td>
                    <td className="p-3.5">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                          e.status === 'APPROVED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : e.status === 'REJECTED'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {e.status}
                      </span>
                    </td>
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
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-4">Log Daily Timesheet</h3>
            {errorMsg && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
            <form onSubmit={handleLogTime} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Project</label>
                <select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                  required
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Task Name</label>
                <input
                  type="text"
                  value={taskName}
                  onChange={(e) => setTaskName(e.target.value)}
                  placeholder="e.g. API Gateway integration, code review..."
                  className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Date</label>
                  <input
                    type="date"
                    value={entryDate}
                    onChange={(e) => setEntryDate(e.target.value)}
                    className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Hours Logged</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="16"
                    value={hours}
                    onChange={(e) => setHours(Number(e.target.value))}
                    className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                    required
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="billableCheck"
                  checked={isBillable}
                  onChange={(e) => setIsBillable(e.target.checked)}
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
                />
                <label htmlFor="billableCheck" className="text-slate-700 font-medium">
                  Billable to client project
                </label>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Notes (Optional)</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Additional context or deliverables..."
                  rows={2}
                  className="w-full p-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-900 focus:bg-white focus:outline-none"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLogModal(false)}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-semibold shadow-md shadow-emerald-600/20"
                >
                  {submitting ? 'Recording...' : 'Submit Entry'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
