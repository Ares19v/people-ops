import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { 
  Database, 
  Search, 
  RefreshCw, 
  Download, 
  Table as TableIcon, 
  Users, 
  Calendar, 
  Clock, 
  MessageSquare, 
  Terminal, 
  PieChart, 
  CheckCircle2,
  XCircle,
  CloudUpload,
  Edit3,
  Save,
  X,
} from 'lucide-react';

interface ViewMeta {
  key: string;
  title: string;
  description: string;
  icon: string;
  category: string;
  rowCount: number;
}

interface ViewData {
  view_name: string;
  meta: { title: string; description: string; category: string; icon: string };
  columns: string[];
  rows: Array<Record<string, any>>;
  total_returned: number;
}

export const DatabaseInspector: React.FC = () => {
  const [views, setViews] = useState<ViewMeta[]>([]);
  const [selectedViewKey, setSelectedViewKey] = useState<string>('v_employees_overview');
  const [viewData, setViewData] = useState<ViewData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [isSyncingLangfuse, setIsSyncingLangfuse] = useState<boolean>(false);
  const [syncingPromptKey, setSyncingPromptKey] = useState<string | null>(null);
  const [syncStatusMsg, setSyncStatusMsg] = useState<{ text: string; isError?: boolean } | null>(null);
  const [editingPrompt, setEditingPrompt] = useState<{ key: string; template: string } | null>(null);
  const [isSavingPrompt, setIsSavingPrompt] = useState<boolean>(false);

  const handleSyncLangfuse = async () => {
    setIsSyncingLangfuse(true);
    setSyncStatusMsg(null);
    try {
      const res = await api.syncPromptsToCloud();
      const count = res.prompts_cloud_sync?.pushed_count ?? 8;
      setSyncStatusMsg({
        text: `Successfully synced ${count} prompts from PostgreSQL to Langfuse Cloud under 'live' & 'production' labels!`,
      });
      await loadViewData(selectedViewKey, searchQuery);
    } catch (err: any) {
      setSyncStatusMsg({
        text: `Sync failed: ${err.response?.data?.detail || err.message}`,
        isError: true,
      });
    } finally {
      setIsSyncingLangfuse(false);
    }
  };

  const handleSyncSinglePrompt = async (promptKey: string) => {
    setSyncingPromptKey(promptKey);
    setSyncStatusMsg(null);
    try {
      const res = await api.syncSinglePromptToCloud(promptKey);
      setSyncStatusMsg({
        text: `Prompt '${promptKey}' synced to Langfuse Cloud as Version ${res.version ?? 'latest'} under 'live' & 'production' labels!`,
      });
      await loadViewData(selectedViewKey, searchQuery);
    } catch (err: any) {
      setSyncStatusMsg({
        text: `Sync failed for '${promptKey}': ${err.response?.data?.detail || err.message}`,
        isError: true,
      });
    } finally {
      setSyncingPromptKey(null);
    }
  };

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'Users': return <Users className="w-4 h-4" />;
      case 'Calendar': return <Calendar className="w-4 h-4" />;
      case 'PieChart': return <PieChart className="w-4 h-4" />;
      case 'Clock': return <Clock className="w-4 h-4" />;
      case 'MessageSquare': return <MessageSquare className="w-4 h-4" />;
      case 'Terminal': return <Terminal className="w-4 h-4" />;
      case 'RefreshCw': return <RefreshCw className="w-4 h-4" />;
      default: return <TableIcon className="w-4 h-4" />;
    }
  };

  const loadViews = async () => {
    try {
      const vList = await api.getDatabaseViews();
      setViews(vList);
      if (vList.length > 0 && !selectedViewKey) {
        setSelectedViewKey(vList[0].key);
      }
    } catch (err) {
      console.error('Failed to load DB views:', err);
    }
  };

  const loadViewData = async (viewKey: string, search?: string) => {
    setIsLoading(true);
    setViewData(null);
    try {
      const data = await api.getDatabaseViewData(viewKey, search);
      setViewData(data);
    } catch (err) {
      console.error('Failed to fetch view records:', err);
      setViewData(null);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadViews();
  }, []);

  useEffect(() => {
    if (selectedViewKey) {
      loadViewData(selectedViewKey, searchQuery);
    }
  }, [selectedViewKey]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedViewKey) {
      loadViewData(selectedViewKey, searchQuery);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadViews();
    if (selectedViewKey) {
      await loadViewData(selectedViewKey, searchQuery);
    }
  };

  const handleExportCSV = () => {
    if (!viewData || !viewData.rows.length) return;
    const cols = viewData.columns;
    const headerRow = cols.join(',');
    const dataRows = viewData.rows.map(row => 
      cols.map(c => {
        let val = row[c] ?? '';
        if (typeof val === 'object') val = JSON.stringify(val);
        val = String(val).replace(/"/g, '""');
        return `"${val}"`;
      }).join(',')
    );
    const csvContent = [headerRow, ...dataRows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${selectedViewKey}_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  const handleOpenEdit = async (promptKey: string) => {
    try {
      const data = await api.getPrompts();
      const p = data.prompts?.[promptKey] || data.db_records?.[promptKey];
      if (p?.template) {
        setEditingPrompt({ key: promptKey, template: p.template });
        return;
      }
      const single = await api.getSinglePrompt(promptKey);
      if (single?.template) {
        setEditingPrompt({ key: promptKey, template: single.template });
        return;
      }
      alert(`Prompt '${promptKey}' template could not be loaded.`);
    } catch (err: any) {
      alert(`Failed to fetch prompt: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleSavePrompt = async () => {
    if (!editingPrompt) return;
    setIsSavingPrompt(true);
    try {
      await api.updatePrompt(editingPrompt.key, editingPrompt.template, 'live');
      setSyncStatusMsg({
        text: `Prompt '${editingPrompt.key}' updated in PostgreSQL, reloaded in ADK fleet, and synced live to Langfuse Cloud!`,
      });
      setEditingPrompt(null);
      await loadViewData(selectedViewKey, searchQuery);
    } catch (err: any) {
      alert(`Failed to save prompt: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const categories = ['All', ...Array.from(new Set(views.map(v => v.category)))];
  const filteredViews = selectedCategory === 'All' 
    ? views 
    : views.filter(v => v.category === selectedCategory);

  const formatColumnHeader = (col: string) => {
    return col
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  const renderCellValue = (column: string, val: any) => {
    if (val === null || val === undefined) {
      return <span className="text-slate-300 italic font-mono text-xs">null</span>;
    }
    if (typeof val === 'boolean') {
      return val ? (
        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-[11px] font-semibold">
          <CheckCircle2 className="w-3 h-3" /> True
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full text-[11px] font-medium">
          <XCircle className="w-3 h-3" /> False
        </span>
      );
    }

    const strVal = String(val);

    // Badges for roles & statuses
    if (column === 'role') {
      const colorMap: Record<string, string> = {
        ADMIN: 'bg-slate-900 text-white border-slate-900',
        HR_MANAGER: 'bg-slate-100 text-slate-800 border-slate-300',
        HR_ASSOCIATE: 'bg-slate-100 text-slate-700 border-slate-200',
        EMPLOYEE: 'bg-slate-50 text-slate-700 border-slate-200',
      };
      return (
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide border ${colorMap[strVal] || 'bg-slate-100 text-slate-700'}`}>
          {strVal}
        </span>
      );
    }

    if (column === 'status') {
      const statusMap: Record<string, string> = {
        APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        SUCCESS: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        SUBMITTED: 'bg-amber-50 text-amber-700 border-amber-200',
        PENDING: 'bg-amber-50 text-amber-700 border-amber-200',
        REJECTED: 'bg-rose-50 text-rose-700 border-rose-200',
      };
      return (
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide border ${statusMap[strVal] || 'bg-slate-100 text-slate-700'}`}>
          {strVal}
        </span>
      );
    }

    if (column.includes('id') || column === 'project_code') {
      return (
        <span className="font-mono text-[11px] font-semibold text-slate-700 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">
          {strVal}
        </span>
      );
    }

    if (strVal.length > 60) {
      return (
        <span className="text-xs text-slate-700" title={strVal}>
          {strVal.slice(0, 58)}...
        </span>
      );
    }

    return <span className="text-xs text-slate-800 font-medium">{strVal}</span>;
  };

  const activeMeta = views.find(v => v.key === selectedViewKey);

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Formal Controls Toolbar */}
      <div className="card-olixer p-4 bg-white border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Category Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-bold text-slate-400 mr-1 uppercase tracking-wider">Categories:</span>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                selectedCategory === cat
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {selectedViewKey === 'v_agent_prompts' && (
            <button
              onClick={handleSyncLangfuse}
              disabled={isSyncingLangfuse}
              className="px-3.5 py-1.5 rounded-xl border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-xs font-semibold text-indigo-700 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              title="Push all database prompts to Langfuse Cloud under live label"
            >
              <CloudUpload className={`w-3.5 h-3.5 ${isSyncingLangfuse ? 'animate-bounce' : ''}`} />
              <span>{isSyncingLangfuse ? 'Syncing to Cloud...' : 'Push to Langfuse Cloud'}</span>
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Refresh SQL Views"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleExportCSV}
            disabled={!viewData || !viewData.rows.length}
            className="btn-pill-dark text-xs py-1.5 px-3.5 flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Left Views List, Right Table Data */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Left Views Sidebar */}
        <div className="lg:col-span-1 space-y-2">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider px-1">
            Available SQL Views ({filteredViews.length})
          </div>
          <div className="space-y-1.5">
            {filteredViews.map((v) => {
              const isSelected = selectedViewKey === v.key;
              return (
                <button
                  key={v.key}
                  onClick={() => {
                    if (selectedViewKey !== v.key) {
                      setSelectedViewKey(v.key);
                      setSearchQuery('');
                    }
                  }}
                  className={`w-full text-left p-3 rounded-2xl transition-all duration-150 flex items-center justify-between group cursor-pointer border ${
                    isSelected
                      ? 'bg-slate-900 text-white shadow-sm border-slate-900'
                      : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-200/80'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={`p-1.5 rounded-lg ${isSelected ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      {getIcon(v.icon)}
                    </div>
                    <div className="truncate">
                      <div className={`text-xs font-bold truncate ${isSelected ? 'text-white' : 'text-slate-800'}`}>
                        {v.title}
                      </div>
                      <div className={`text-[10px] truncate ${isSelected ? 'text-slate-300' : 'text-slate-400'}`}>
                        {v.key}
                      </div>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold font-mono ${
                    isSelected ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {v.rowCount}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Table Container */}
        <div className="lg:col-span-3 space-y-4">
          {/* Active View Info & Search Card */}
          <div className="card-olixer p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white border border-slate-200">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-slate-900 text-base">
                  {activeMeta?.title || selectedViewKey}
                </h3>
                <span className="font-mono text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                  {selectedViewKey}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {activeMeta?.description}
              </p>
            </div>

            <form onSubmit={handleSearch} className="flex items-center gap-2">
              <div className="relative w-full sm:w-64">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search in view..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50/50 text-xs font-medium focus:outline-none focus:border-slate-400 focus:bg-white transition-all"
                />
              </div>
              <button
                type="submit"
                className="btn-pill-dark text-xs py-1.5 px-3.5 cursor-pointer shrink-0"
              >
                Search
              </button>
            </form>
          </div>

          {/* Sync Status Banner */}
          {syncStatusMsg && (
            <div className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
              syncStatusMsg.isError 
                ? 'bg-rose-50 border-rose-200 text-rose-800' 
                : 'bg-emerald-50 border-emerald-200 text-emerald-800'
            }`}>
              <span>{syncStatusMsg.text}</span>
              <button 
                onClick={() => setSyncStatusMsg(null)} 
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Table Card */}
          <div className="card-olixer overflow-hidden border border-slate-200 bg-white">
            {isLoading ? (
              <div className="p-12 flex flex-col items-center justify-center text-center space-y-3">
                <RefreshCw className="w-6 h-6 text-slate-700 animate-spin" />
                <p className="text-xs font-semibold text-slate-600">Querying PostgreSQL schema...</p>
              </div>
            ) : !viewData || viewData.rows.length === 0 ? (
              <div className="p-12 flex flex-col items-center justify-center text-center space-y-2">
                <TableIcon className="w-8 h-8 text-slate-300" />
                <h4 className="text-sm font-bold text-slate-700">No records found</h4>
                <p className="text-xs text-slate-400 max-w-sm">
                  {searchQuery ? `No rows matched query "${searchQuery}"` : 'This view currently has 0 rows.'}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50/90 border-b border-slate-200 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      <th className="py-3 px-4 w-12 text-slate-400">#</th>
                      {viewData.columns.map((col) => (
                        <th key={col} className="py-3 px-4 whitespace-nowrap">
                          {formatColumnHeader(col)}
                        </th>
                      ))}
                      {selectedViewKey === 'v_agent_prompts' && (
                        <th className="py-3 px-4 whitespace-nowrap text-right">Actions</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {viewData.rows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-2.5 px-4 font-mono text-[10px] text-slate-400">
                          {idx + 1}
                        </td>
                        {viewData.columns.map((col) => (
                          <td key={col} className="py-2.5 px-4 whitespace-nowrap">
                            {renderCellValue(col, row[col])}
                          </td>
                        ))}
                        {selectedViewKey === 'v_agent_prompts' && (
                          <td className="py-2.5 px-4 whitespace-nowrap text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleSyncSinglePrompt(row['prompt_key'])}
                                disabled={syncingPromptKey === row['prompt_key']}
                                className="px-2.5 py-1 rounded-lg border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-[11px] font-semibold text-indigo-700 transition-all flex items-center gap-1 cursor-pointer disabled:opacity-50"
                                title="Sync this prompt directly from PostgreSQL to Langfuse Cloud"
                              >
                                <CloudUpload className={`w-3 h-3 ${syncingPromptKey === row['prompt_key'] ? 'animate-bounce' : ''}`} />
                                <span>{syncingPromptKey === row['prompt_key'] ? 'Syncing...' : 'Sync to Cloud'}</span>
                              </button>
                              <button
                                onClick={() => handleOpenEdit(row['prompt_key'])}
                                className="px-2.5 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-[11px] font-semibold text-slate-700 transition-all flex items-center gap-1 cursor-pointer"
                                title="Edit prompt in PostgreSQL"
                              >
                                <Edit3 className="w-3 h-3 text-slate-500" />
                                <span>Edit in DB</span>
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Footer Status */}
            {viewData && (
              <div className="p-3 bg-slate-50/60 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
                <div className="flex items-center gap-1.5 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                  <span>Showing {viewData.total_returned} rows from <strong className="text-slate-700">{selectedViewKey}</strong></span>
                </div>
                <div className="font-mono text-[11px] text-slate-400">
                  PostgreSQL 16 Engine
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit Prompt Modal */}
      {editingPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-slate-800" />
                <div>
                  <h3 className="font-display font-bold text-slate-900 text-sm">
                    Edit Agent Prompt: <span className="font-mono text-blue-600">{editingPrompt.key}</span>
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Saves directly to PostgreSQL table <code className="font-mono">agent_prompts</code> and hot-reloads the ADK fleet instructions immediately.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setEditingPrompt(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Prompt Template (System Instructions)
              </label>
              <textarea
                value={editingPrompt.template}
                onChange={(e) => setEditingPrompt({ ...editingPrompt, template: e.target.value })}
                rows={12}
                className="w-full font-mono text-xs p-3 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-none focus:border-slate-400 resize-y"
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-[11px] text-slate-400">
                Saving increments DB version, updates fleet memory, and syncs live to Langfuse Cloud.
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEditingPrompt(null)}
                  className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-600 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSavePrompt}
                  disabled={isSavingPrompt}
                  className="btn-pill-dark text-xs py-1.5 px-4 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{isSavingPrompt ? 'Saving & Syncing...' : 'Save & Sync Live'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
