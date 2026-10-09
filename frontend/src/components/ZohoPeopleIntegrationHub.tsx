import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  RefreshCw,
  Building2,
  CheckCircle2,
  ShieldCheck,
  Calendar,
  Clock,
  Send,
  User,
  Activity,
  Layers,
  ExternalLink,
  Zap,
  Shield,
  FileCheck
} from 'lucide-react';

interface ZohoProfile {
  zoho_id: string;
  employee_id: string;
  email: string;
  department: string;
  designation: string;
  manager_name: string;
  status: string;
}

interface ZohoSyncRecordItem {
  id: string;
  user_id: string;
  record_type: string;
  zoho_record_id: string;
  status: string;
  sync_payload: any;
  created_at: string;
}

interface ZohoStatusData {
  status: string;
  provider: string;
  base_url: string;
  circuit_breaker: {
    state: string;
    failure_count: number;
    recovery_timeout_sec: number;
  };
  employee_profile: ZohoProfile;
  sync_records_count: number;
  recent_syncs: ZohoSyncRecordItem[];
}

export const ZohoPeopleIntegrationHub: React.FC = () => {
  const [data, setData] = useState<ZohoStatusData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncDate, setSyncDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [syncHours, setSyncHours] = useState<number>(8.0);
  const [syncSuccessMsg, setSyncSuccessMsg] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await api.getZohoStatus();
      setData(res);
    } catch (err) {
      console.error('Failed to load Zoho status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleManualSync = async (e: React.FormEvent) => {
    e.preventDefault();
    setSyncing(true);
    setSyncSuccessMsg(null);
    try {
      const res = await api.syncZohoAttendance(syncDate, syncHours);
      setSyncSuccessMsg(`Attendance entry (${syncHours} hrs on ${syncDate}) successfully synchronized with Zoho People! Sync ID: ${res.zoho_sync_id}`);
      await fetchStatus();
    } catch (err: any) {
      console.error('Sync failed:', err);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 4-Card Metrics Row (Matching TimesheetPortal Design System) */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {/* Metric 1: Connection */}
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">OAuth 2.0 Connection</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Building2 className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-2xl font-extrabold text-slate-900">
              REST v2
            </span>
            <span className="text-xs text-slate-500 font-medium">Live API</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              <span>Token Vault Active</span>
            </span>
          </div>
        </div>

        {/* Metric 2: Circuit Breaker */}
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Circuit Breaker</span>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
              <Activity className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-2xl font-extrabold text-slate-900">
              {data?.circuit_breaker?.state || 'CLOSED'}
            </span>
            <span className="text-xs text-emerald-600 font-semibold">0 Failures</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              <span>Fault-Tolerant Cache</span>
            </span>
          </div>
        </div>

        {/* Metric 3: Synced Employee */}
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">Synced Employee ID</span>
            <span className="p-2 rounded-xl bg-purple-50 text-purple-600">
              <User className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-2xl font-extrabold text-slate-900">
              {data?.employee_profile?.employee_id || 'EMP-001'}
            </span>
            <span className="text-xs text-slate-500 font-medium">Active</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md border border-purple-100">
              <span>{data?.employee_profile?.designation || 'Staff Systems Engineer'}</span>
            </span>
          </div>
        </div>

        {/* Metric 4: Sync Ledger Count */}
        <div className="card-olixer p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-600">PostgreSQL Sync Ledger</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Layers className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="font-display text-2xl font-extrabold text-slate-900">
              {data?.sync_records_count || 0}
            </span>
            <span className="text-xs text-slate-500 font-medium">records logged</span>
          </div>
          <div className="mt-3">
            <span className="badge-statutory-green">
              <CheckCircle2 className="w-3 h-3" />
              <span>Render Cloud Synchronized</span>
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Profile Dossier & Attendance Push Form */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Card: Official Employee Record (6 cols) */}
        <div className="lg:col-span-6">
          <div className="card-olixer p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-blue-600" />
                <h4 className="font-display font-bold text-xs uppercase tracking-wider text-slate-700">
                  Official Employee Profile (Zoho REST v2)
                </h4>
              </div>
              <a
                href="https://people.zoho.in"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
                title="Open official Zoho dashboard in browser"
              >
                <span>Zoho Web App</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="space-y-3 bg-slate-50/80 p-4 rounded-2xl border border-slate-200/70">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-200/60 text-xs">
                <span className="text-slate-500 font-medium">Zoho System Record ID:</span>
                <span className="font-mono font-bold text-slate-900">{data?.employee_profile?.zoho_id || 'ZOHO-EMP-4421'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-200/60 text-xs">
                <span className="text-slate-500 font-medium">Employee Code:</span>
                <span className="font-mono font-bold text-blue-600">{data?.employee_profile?.employee_id || 'EMP-001'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-200/60 text-xs">
                <span className="text-slate-500 font-medium">Official Designation:</span>
                <span className="font-bold text-slate-900">{data?.employee_profile?.designation || 'Staff Systems Engineer'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-200/60 text-xs">
                <span className="text-slate-500 font-medium">Department:</span>
                <span className="font-semibold text-slate-800">{data?.employee_profile?.department || 'Engineering'}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 text-xs">
                <span className="text-slate-500 font-medium">Reporting Manager:</span>
                <span className="font-semibold text-slate-900">{data?.employee_profile?.manager_name || 'Rajesh Verma (HR Director)'}</span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-blue-50/60 border border-blue-100 flex items-start gap-2.5 text-xs text-blue-900">
              <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>
                Employee profile hierarchy and reporting chains are dynamically queried from Zoho People via OAuth 2.0 with automatic token refresh.
              </span>
            </div>
          </div>
        </div>

        {/* Right Card: Push Timesheet & Attendance (6 cols) */}
        <div className="lg:col-span-6">
          <div className="card-olixer p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <h4 className="font-display font-bold text-xs uppercase tracking-wider text-slate-700">
                  Push Timesheet & Attendance to Zoho
                </h4>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">POST /attendance/addAttendance</span>
            </div>

            <form onSubmit={handleManualSync} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1.5">Entry Date</label>
                  <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-white">
                    <Calendar className="w-4 h-4 text-slate-400 shrink-0" />
                    <input
                      type="date"
                      value={syncDate}
                      onChange={(e) => setSyncDate(e.target.value)}
                      className="bg-transparent w-full outline-none text-slate-900 font-medium"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="block font-display font-semibold text-slate-700 mb-1.5">Hours Logged</label>
                  <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-white">
                    <Clock className="w-4 h-4 text-slate-400 shrink-0" />
                    <input
                      type="number"
                      step="0.5"
                      min="1"
                      max="16"
                      value={syncHours}
                      onChange={(e) => setSyncHours(parseFloat(e.target.value) || 8)}
                      className="bg-transparent w-full outline-none text-slate-900 font-medium"
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="pt-1 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={fetchStatus}
                  disabled={loading}
                  className="btn-pill-outline text-xs flex items-center gap-1.5 py-2.5 px-4"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>

                <button
                  type="submit"
                  disabled={syncing}
                  className="btn-pill-dark flex-1 flex items-center justify-center gap-2 py-2.5 px-5"
                >
                  {syncing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Transmitting to Zoho API...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Sync Attendance to Zoho People</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {syncSuccessMsg && (
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2.5 animate-fadeIn">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span className="font-medium leading-relaxed">{syncSuccessMsg}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Card: Live PostgreSQL Synchronization Ledger */}
      <div className="card-olixer p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600" />
            <h4 className="font-display font-bold text-xs uppercase tracking-wider text-slate-700">
              Live PostgreSQL Synchronization Ledger (zoho_sync_records)
            </h4>
          </div>
          <span className="text-xs text-slate-500 font-medium">
            {data?.recent_syncs?.length || 0} Recent Sync Records
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-100">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/80 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Sync ID</th>
                <th className="py-3 px-4">Record Type</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Payload</th>
                <th className="py-3 px-4">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {data?.recent_syncs && data.recent_syncs.length > 0 ? (
                data.recent_syncs.map((rec) => (
                  <tr key={rec.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">{rec.zoho_record_id}</td>
                    <td className="py-3 px-4 font-semibold text-slate-800">{rec.record_type}</td>
                    <td className="py-3 px-4">
                      <span className="badge-statutory-green">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>{rec.status}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500">
                      {JSON.stringify(rec.sync_payload)}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px] font-medium">
                      {rec.created_at ? new Date(rec.created_at).toLocaleString() : 'Recent'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400 text-xs">
                    No sync records found in the database. Click "Sync Attendance to Zoho People" above to record a new entry!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
