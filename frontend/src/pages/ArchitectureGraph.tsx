import React, { useState } from 'react';
import { Network, GitBranch, Share2, ExternalLink, FileText, Activity, Layers } from 'lucide-react';

export const ArchitectureGraph: React.FC = () => {
  const [selectedView, setSelectedView] = useState<'network' | 'tree' | 'callflow' | 'report'>('network');

  const views = [
    { id: 'network', label: 'Interactive Force Graph', file: 'graph.html', icon: Network },
    { id: 'tree', label: 'D3 Hierarchy Tree', file: 'GRAPH_TREE.html', icon: GitBranch },
    { id: 'callflow', label: 'Mermaid Call-Flow Architecture', file: 'people-ops-callflow.html', icon: Share2 },
    { id: 'report', label: 'Graphify Health Report', file: 'GRAPH_REPORT.md', icon: FileText },
  ];

  const activeFile = views.find((v) => v.id === selectedView)?.file || 'graph.html';
  const iframeUrl = `http://127.0.0.1:8000/graphify/${activeFile}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Network className="w-6 h-6 text-emerald-600" />
            Codebase Knowledge Graph (Graphify)
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            AST-extracted structural knowledge graph: 466 nodes, 1,240 edges, 19 modular communities.
          </p>
        </div>
        <a
          href={iframeUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-md transition-all flex items-center gap-2 self-start sm:self-auto"
        >
          <ExternalLink className="w-4 h-4" />
          Open Fullscreen Graph
        </a>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-slate-500 font-medium">Total Nodes</div>
          <div className="text-xl font-extrabold text-slate-900 mt-1">466</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Functions, Classes, Modules</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-slate-500 font-medium">Relationships</div>
          <div className="text-xl font-extrabold text-emerald-600 mt-1">1,240</div>
          <div className="text-[10px] text-emerald-600 mt-0.5">Imports, Calls, Inferences</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-slate-500 font-medium">Communities</div>
          <div className="text-xl font-extrabold text-blue-600 mt-1">19</div>
          <div className="text-[10px] text-blue-500 mt-0.5">Modular Clusters</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-slate-500 font-medium">God Node</div>
          <div className="text-xl font-extrabold text-purple-600 mt-1">User</div>
          <div className="text-[10px] text-purple-500 mt-0.5">65 Hub Connections</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-slate-500 font-medium">Import Cycles</div>
          <div className="text-xl font-extrabold text-emerald-600 mt-1">0</div>
          <div className="text-[10px] text-emerald-600 mt-0.5">Clean Architecture</div>
        </div>
      </div>

      {/* View Switcher Pills */}
      <div className="flex flex-wrap items-center gap-2 bg-white p-2 rounded-xl border border-slate-200 shadow-sm">
        {views.map((v) => {
          const Icon = v.icon;
          const isSelected = selectedView === v.id;
          return (
            <button
              key={v.id}
              onClick={() => setSelectedView(v.id as any)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                isSelected
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Icon className="w-4 h-4" />
              {v.label}
            </button>
          );
        })}
      </div>

      {/* Main Interactive Visualizer Frame */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-md overflow-hidden flex flex-col h-[750px]">
        <div className="bg-slate-900 text-slate-300 px-4 py-2.5 text-xs flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-mono text-white">{activeFile}</span>
            <span className="text-slate-400 text-[11px]">&bull; Interactive D3/Canvas View (Zoom, Drag, Filter)</span>
          </div>
          <a
            href={iframeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 text-[11px] font-semibold"
          >
            Open in new window &rarr;
          </a>
        </div>
        <iframe
          src={iframeUrl}
          title="Graphify Architecture Visualization"
          className="w-full flex-1 border-0 bg-slate-950"
        />
      </div>
    </div>
  );
};
