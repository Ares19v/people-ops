import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { User, UserRole, Project, TimesheetReportSummary } from '../types';
import { 
  Download, 
  Filter, 
  FileSpreadsheet, 
  CheckCircle2, 
  TrendingUp, 
  Clock, 
  Database,
  Building2,
  Calendar,
  Layers,
  Sparkles,
  BarChart3
} from 'lucide-react';
import { FeatureExplainerIcon } from '../components/FeatureExplainerIcon';
import { DatabaseInspector } from '../components/DatabaseInspector';
import { 
  EmployeeAvatarChip, 
  HoursBadge, 
  StatusBadge, 
  EntityIdBadge 
} from '../utils/formatters';

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
  const [isDbMode, setIsDbMode] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'projects' | 'entries'>('projects');
  const [isExporting, setIsExporting] = useState(false);

  const isAdmin = currentRole === 'ADMIN';

  useEffect(() => {
    if (!isAdmin && isDbMode) {
      setIsDbMode(false);
    }
  }, [isAdmin, isDbMode]);

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
  const billablePercent = report && report.total_hours > 0 
    ? Math.round((report.billable_hours / report.total_hours) * 100) 
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center">
            <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
              {isAdmin ? (
                <button
                  onClick={() => setIsDbMode(!isDbMode)}
                  className="group relative p-1 -m-1 rounded-xl transition-all duration-200 hover:bg-slate-100 active:scale-95 cursor-pointer focus:outline-none"
                  title={isDbMode ? "Click icon to return to Reports View" : "Click icon to switch to Database Mode"}
                >
                  {isDbMode ? (
                    <Database className="w-5 h-5 text-slate-800 transition-transform duration-200 group-hover:scale-110" />
                  ) : (
                    <FileSpreadsheet className="w-5 h-5 text-slate-700 transition-transform duration-200 group-hover:scale-110" />
                  )}
                  <span className="sr-only">Toggle Database Mode</span>
                </button>
              ) : (
                <FileSpreadsheet className="w-5 h-5 text-slate-700" />
              )}
              <span>{isAdmin && isDbMode ? "Database Mode & SQL Inspector" : "Timesheet Reports & CSV Export"}</span>
              {isAdmin && isDbMode && (
                <span className="px-2 py-0.5 rounded-full bg-slate-900 text-white text-[10px] font-bold">
                  SQL Active
                </span>
              )}
            </h2>
            <FeatureExplainerIcon featureKey="reports_summary_kpis" />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {isAdmin && isDbMode
              ? "Clean relational PostgreSQL SQL views, joined tables, and conversation turns."
              : "Aggregate project hours, audit billable utilization, and generate official payroll exports."}
          </p>
        </div>
        {(!isAdmin || !isDbMode) && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadCSV}
              disabled={isExporting}
              className="btn-pill-dark self-start sm:self-auto disabled:opacity-60 cursor-pointer flex items-center gap-2"
            >
              <Download className={`w-4 h-4 ${isExporting ? 'animate-bounce' : ''}`} />
              <span>{isExporting ? 'Generating CSV...' : 'Export Timesheets (CSV)'}</span>
            </button>
            <FeatureExplainerIcon featureKey="reports_csv_export" />
          </div>
        )}
      </div>

      {isAdmin && isDbMode ? (
        <DatabaseInspector />
      ) : (
        <>
          {/* Filter Card */}
          <div className="card-olixer p-4 bg-white border border-slate-200 shadow-2xs">
            <div className="flex items-center gap-2 mb-3">
              <Filter className="w-3.5 h-3.5 text-slate-500" />
              <span className="font-display font-bold text-xs text-slate-700 uppercase tracking-wider">
                Report Filters
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">Project</label>
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  className="w-full p-2 rounded-xl border border-slate-200 bg-white font-medium focus:outline-none focus:border-slate-400"
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
                <label className="block font-display font-semibold text-slate-700 mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full p-2 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-slate-400"
                />
              </div>
              <div>
                <label className="block font-display font-semibold text-slate-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full p-2 rounded-xl border border-slate-200 font-medium focus:outline-none focus:border-slate-400"
                />
              </div>
            </div>
          </div>

          {/* Aggregate KPI Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Total Filtered Hours */}
            <div className="card-olixer p-5 bg-white border border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span className="font-display font-semibold text-slate-600">Total Filtered Hours</span>
                <span className="p-2 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
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
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                  <CheckCircle2 className="w-3 h-3 text-blue-600" />
                  {report?.entry_count || 0} Timesheet Logs
                </span>
              </div>
            </div>

            {/* Billable Volume */}
            <div className="card-olixer p-5 bg-white border border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span className="font-display font-semibold text-slate-600">Billable Volume</span>
                <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100">
                  <TrendingUp className="w-4 h-4" />
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="font-display text-3xl font-extrabold text-emerald-700">
                  {report?.billable_hours.toFixed(1) || '0.0'}
                </span>
                <span className="text-xs text-slate-500 font-medium">hrs</span>
              </div>
              <div className="mt-3">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {billablePercent}% Billable Rate
                </span>
              </div>
            </div>

            {/* Statutory Overtime */}
            <div className="card-olixer p-5 bg-white border border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span className="font-display font-semibold text-slate-600">Statutory Overtime</span>
                <span className="p-2 rounded-xl bg-amber-50 text-amber-600 border border-amber-100">
                  <Sparkles className="w-4 h-4" />
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="font-display text-3xl font-extrabold text-amber-700">
                  {overtimeHours.toFixed(1)}
                </span>
                <span className="text-xs text-slate-500 font-medium">hrs</span>
              </div>
              <div className="mt-3">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                  Maharashtra Sec 13 (2.0x Rate)
                </span>
              </div>
            </div>
          </div>

          {/* Tab Navigation for Reports */}
          <div className="flex items-center justify-between border-b border-slate-200 pb-2 pt-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('projects')}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
                  activeTab === 'projects'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                <Building2 className="w-3.5 h-3.5" />
                <span>Project Summary ({projects.length})</span>
              </button>
              <button
                onClick={() => setActiveTab('entries')}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
                  activeTab === 'entries'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Detailed Timesheet Logs ({report?.entries?.length || 0})</span>
              </button>
            </div>
          </div>

          {/* Table Container */}
          {activeTab === 'projects' ? (
            <div className="card-olixer p-0 overflow-hidden border border-slate-200 bg-white shadow-sm">
              <div className="p-4 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-slate-600" />
                  <span className="font-display font-bold text-xs text-slate-900">
                    Project Allocation Summary
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-medium">Aggregated across active assignments</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50/90 border-b border-slate-200 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      <th className="py-3.5 px-4">Project</th>
                      <th className="py-3.5 px-4">Client</th>
                      <th className="py-3.5 px-4">Total Logged</th>
                      <th className="py-3.5 px-4">Billable Hours</th>
                      <th className="py-3.5 px-4">Utilization Target</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {projects.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-400 text-xs">
                          No active projects configured.
                        </td>
                      </tr>
                    ) : (
                      projects.map((p) => {
                        const projEntries = report?.entries?.filter(e => e.project_id === p.id) || [];
                        const projTotal = projEntries.reduce((acc, e) => acc + e.hours, 0);
                        const projBillable = projEntries.filter(e => e.is_billable).reduce((acc, e) => acc + e.hours, 0);
                        const rate = projTotal > 0 ? Math.round((projBillable / projTotal) * 100) : 85;

                        return (
                          <tr key={p.id} className="hover:bg-slate-50/75 transition-colors">
                            <td className="py-3.5 px-4">
                              <div className="font-display font-bold text-xs text-slate-900">
                                {p.name}
                              </div>
                              <div className="mt-0.5">
                                <EntityIdBadge id={p.code} />
                              </div>
                            </td>
                            <td className="py-3.5 px-4 text-xs font-semibold text-slate-700">
                              <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-800 border border-slate-200/80">
                                {p.client_name}
                              </span>
                            </td>
                            <td className="py-3.5 px-4">
                              <span className="font-display font-extrabold text-sm text-slate-900">
                                {projTotal.toFixed(1)} hrs
                              </span>
                            </td>
                            <td className="py-3.5 px-4">
                              <span className="font-display font-extrabold text-sm text-emerald-700">
                                {projBillable.toFixed(1)} hrs
                              </span>
                            </td>
                            <td className="py-3.5 px-4">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <CheckCircle2 className="w-3 h-3" />
                                {rate}% Billable Target
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
          ) : (
            <div className="card-olixer p-0 overflow-hidden border border-slate-200 bg-white shadow-sm">
              <div className="p-4 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-slate-600" />
                  <span className="font-display font-bold text-xs text-slate-900">
                    Detailed Timesheet Records
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-medium">
                  {report?.entries?.length || 0} Individual Work Logs
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50/90 border-b border-slate-200 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      <th className="py-3.5 px-4">Timesheet ID</th>
                      <th className="py-3.5 px-4">Employee</th>
                      <th className="py-3.5 px-4">Project & Task</th>
                      <th className="py-3.5 px-4">Date</th>
                      <th className="py-3.5 px-4">Hours Logged</th>
                      <th className="py-3.5 px-4">Approval Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {!report?.entries || report.entries.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400 text-xs">
                          No timesheet entries matching current filters.
                        </td>
                      </tr>
                    ) : (
                      report.entries.map((entry) => (
                        <tr key={entry.id} className="hover:bg-slate-50/75 transition-colors">
                          <td className="py-3 px-4">
                            <EntityIdBadge id={entry.id} />
                          </td>
                          <td className="py-3 px-4">
                            <EmployeeAvatarChip userIdentifier={entry.user_id} size="sm" showDetails={true} />
                          </td>
                          <td className="py-3 px-4">
                            <div className="font-display font-bold text-xs text-slate-900">
                              {entry.project_name || entry.project_id}
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              {entry.task_name}
                            </div>
                          </td>
                          <td className="py-3 px-4 whitespace-nowrap">
                            <span className="inline-flex items-center gap-1.5 text-xs text-slate-700 font-medium">
                              <Calendar className="w-3.5 h-3.5 text-slate-400" />
                              {new Date(entry.entry_date).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <HoursBadge hours={entry.hours} isBillable={entry.is_billable} />
                          </td>
                          <td className="py-3 px-4">
                            <StatusBadge status={entry.status} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
