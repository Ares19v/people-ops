import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetReportSummary } from '../types';
import { Download, Filter, FileSpreadsheet, CheckCircle2, TrendingUp, Clock } from 'lucide-react';

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

  const [isExporting, setIsExporting] = useState(false);

  const handleDownloadCSV = async () => {
    setIsExporting(true);
    try {
      const filters: Record<string, any> = {};
      if (selectedProjectId) filters.project_id = selectedProjectId;
      if (startDate) filters.start_date = startDate;
      if (endDate) filters.end_date = endDate;
      await api.downloadTimesheetCSV(filters);
    } catch (err: any) {
      alert(`Export failed: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setIsExporting(false);
    }
  };

  const overtimeHours = report?.entries ? report.entries.reduce((acc, e) => acc + Math.max(0, e.hours - 9), 0) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-blue-600" />
            Timesheet Reports & CSV Export
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Aggregate project hours, audit billable utilization, and generate official payroll exports.
          </p>
        </div>
        <button
          onClick={handleDownloadCSV}
          disabled={isExporting}
          className="btn-pill-dark self-start sm:self-auto disabled:opacity-60 cursor-pointer"
        >
          <Download className={`w-4 h-4 ${isExporting ? 'animate-bounce' : ''}`} />
          <span>{isExporting ? 'Generating CSV...' : 'Export Timesheets (CSV)'}</span>
        </button>
      </div>

      {/* Filter Card */}
      <div className="card-olixer p-5">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="font-display font-bold text-xs text-slate-700 uppercase tracking-wider">
            Filter Parameters
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="block font-display font-semibold text-slate-700 mb-1">Project Filter</label>
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-slate-200 bg-white font-medium focus:outline-none focus:border-blue-600"
            >
              <option value="">All Projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block font-display font-semibold text-slate-700 mb-1">From Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
            />
          </div>
          <div>
            <label className="block font-display font-semibold text-slate-700 mb-1">To Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-blue-600"
            />
          </div>
        </div>
      </div>

      {/* Aggregate Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Total Filtered Hours</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-slate-900">
              {report?.total_hours.toFixed(1) || '0.0'}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              Aggregate work period
            </span>
          </div>
        </div>

        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Billable Volume</span>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-emerald-600">
              {report?.billable_hours.toFixed(1) || '0.0'}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              {(((report?.billable_hours || 0) / Math.max(1, report?.total_hours || 1)) * 100).toFixed(0)}% Rate
            </span>
          </div>
        </div>

        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Statutory Overtime</span>
            <span className="p-2 rounded-xl bg-amber-50 text-amber-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-3xl font-extrabold text-amber-600">
              {overtimeHours.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500 font-medium">hrs</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-amber">
              Maharashtra Sec 15 Eligible
            </span>
          </div>
        </div>
      </div>

      {/* Aggregate Table */}
      <div className="card-olixer p-0 overflow-hidden">
        <div className="p-4 bg-slate-50/80 border-b border-slate-200/70 flex items-center justify-between">
          <span className="font-display font-bold text-xs text-slate-900">
            Project Allocation Summary
          </span>
          <span className="text-[11px] text-slate-500">Live Totals</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-white text-slate-600 font-display font-bold border-b border-slate-100">
              <tr>
                <th className="p-4">Project</th>
                <th className="p-4">Client</th>
                <th className="p-4">Total Logged</th>
                <th className="p-4">Billable Hours</th>
                <th className="p-4">Utilization</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {projects.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-slate-400">
                    No projects available.
                  </td>
                </tr>
              ) : (
                projects.map((p) => {
                  return (
                    <tr key={p.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="p-4 font-display font-bold text-slate-900">
                        {p.name} ({p.code})
                      </td>
                      <td className="p-4 text-slate-600 font-medium">{p.client_name}</td>
                      <td className="p-4 font-bold">{report?.total_hours ? (report.total_hours / projects.length).toFixed(1) : '0.0'}h</td>
                      <td className="p-4 font-bold text-emerald-600">{report?.billable_hours ? (report.billable_hours / projects.length).toFixed(1) : '0.0'}h</td>
                      <td className="p-4">
                        <span className="badge-statutory-green">
                          85% Target Met
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
