import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetReportSummary } from '../types';
import { Download, Filter, FileSpreadsheet, CheckCircle2, TrendingUp } from 'lucide-react';

interface ReportsPortalProps {
  currentUser: User | null;
  currentRole: UserRole;
}

export const ReportsPortal: React.FC<ReportsPortalProps> = ({ currentUser, currentRole }) => {
  const [report, setReport] = useState<TimesheetReportSummary | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const loadData = async () => {
    try {
      const projs = await api.getProjects();
      setProjects(projs);
      const filters: Record<string, any> = {};
      if (selectedProjectId) filters.project_id = selectedProjectId;
      if (startDate) filters.start_date = startDate;
      if (endDate) filters.end_date = endDate;
      const rep = await api.getTimesheetReport(filters);
      setReport(rep);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedProjectId, startDate, endDate, currentRole]);

  const handleDownloadCSV = () => {
    const filters: Record<string, any> = {};
    if (selectedProjectId) filters.project_id = selectedProjectId;
    if (startDate) filters.start_date = startDate;
    if (endDate) filters.end_date = endDate;
    const url = api.getTimesheetCSVUrl(filters);
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Timesheet Reports & CSV Export</h2>
          <p className="text-xs text-slate-500 mt-1">
            Aggregate project hours, audit billable utilization, and generate official payroll exports.
          </p>
        </div>
        <button
          onClick={handleDownloadCSV}
          className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center gap-2 self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          Export Timesheets (CSV)
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2 text-slate-500 font-semibold">
          <Filter className="w-4 h-4 text-emerald-600" />
          Filters:
        </div>
        <div className="flex items-center gap-2">
          <label className="text-slate-600 font-medium">Project:</label>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="p-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-900"
          >
            <option value="">All Projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-slate-600 font-medium">From:</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="p-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-900"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-slate-600 font-medium">To:</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="p-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-900"
          />
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Total Tracked Hours</span>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {report?.total_hours.toFixed(1) || '0.0'} hrs
          </div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Billable Hours</span>
          <div className="mt-2 text-2xl font-bold text-emerald-600">
            {report?.billable_hours.toFixed(1) || '0.0'} hrs
          </div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Non-Billable</span>
          <div className="mt-2 text-2xl font-bold text-slate-700">
            {report?.non_billable_hours.toFixed(1) || '0.0'} hrs
          </div>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-medium">Billable Ratio</span>
          <div className="mt-2 text-2xl font-bold text-blue-600">
            {report?.total_hours ? Math.round((report.billable_hours / report.total_hours) * 100) : 0}%
          </div>
        </div>
      </div>

      {/* Detailed Entries Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
              <tr>
                <th className="p-3.5">Employee</th>
                <th className="p-3.5">Project</th>
                <th className="p-3.5">Task</th>
                <th className="p-3.5">Date</th>
                <th className="p-3.5">Hours</th>
                <th className="p-3.5">Billable</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(!report?.entries || report.entries.length === 0) ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-slate-400">
                    No records match the current filter selection.
                  </td>
                </tr>
              ) : (
                report.entries.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50">
                    <td className="p-3.5 font-bold text-slate-900">{item.employee_name || 'Staff'}</td>
                    <td className="p-3.5">{item.project_name || item.project_id}</td>
                    <td className="p-3.5 font-medium">{item.task_name}</td>
                    <td className="p-3.5">{item.entry_date}</td>
                    <td className="p-3.5 font-bold">{item.hours.toFixed(1)}</td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          item.is_billable ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {item.is_billable ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td className="p-3.5">{item.status}</td>
                    <td className="p-3.5 text-slate-500 max-w-xs truncate">{item.notes || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
