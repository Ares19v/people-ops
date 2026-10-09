import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../api';
import {
  Network,
  RefreshCw,
  Search,
  ShieldCheck,
  ExternalLink,
  Layers,
  BookOpen,
  Info,
  CheckCircle2,
  Cpu,
  ArrowRight,
  ArrowLeft,
  Database,
  Shield,
  FileText
} from 'lucide-react';
import { FeatureExplainerIcon } from './FeatureExplainerIcon';

interface GraphNode {
  id: string;
  key: string;
  title: string;
  label: string;
  category: string;
  labels: string[];
  properties: Record<string, any>;
  x?: number;
  y?: number;
}

interface GraphLink {
  id: string;
  source: string;
  target: string;
  source_key: string;
  target_key: string;
  type: string;
  rule: string;
  properties: Record<string, any>;
}

interface LiveGraphData {
  status: string;
  engine: string;
  database_uri: string;
  nodes_count: number;
  relationships_count: number;
  nodes: GraphNode[];
  links: GraphLink[];
}

interface LiveKnowledgeGraphViewerProps {
  onSelectQuery?: (query: string) => void;
}

export const LiveKnowledgeGraphViewer: React.FC<LiveKnowledgeGraphViewerProps> = ({ onSelectQuery }) => {
  const [graphData, setGraphData] = useState<LiveGraphData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>('');

  const fetchGraph = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getKnowledgeGraph();
      setGraphData(data);
      if (data.nodes && data.nodes.length > 0) {
        // default select Section 14 (Overtime) or first node if not already selected
        setSelectedNode((prev) => {
          if (prev) {
            const found = data.nodes.find((n: GraphNode) => n.id === prev.id || n.key === prev.key);
            if (found) return found;
          }
          return data.nodes.find((n: GraphNode) => n.label?.includes('Section 14') || n.key === 'MH_SEC_14') || data.nodes[0];
        });
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch live graph from Neo4j cluster.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  const countsByCategory = useMemo(() => {
    if (!graphData?.nodes) return { ALL: 0, StatutoryAct: 0, Section: 0, PolicyNode: 0 };
    return {
      ALL: graphData.nodes.length,
      StatutoryAct: graphData.nodes.filter((n) => n.category === 'StatutoryAct').length,
      Section: graphData.nodes.filter((n) => n.category === 'Section').length,
      PolicyNode: graphData.nodes.filter((n) => n.category === 'PolicyNode').length,
    };
  }, [graphData]);

  const filteredNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    return graphData.nodes.filter((node) => {
      const matchCat = selectedCategory === 'ALL' || node.category === selectedCategory;
      const matchSearch =
        !searchFilter ||
        node.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
        node.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
        node.key.toLowerCase().includes(searchFilter.toLowerCase()) ||
        (node.properties?.description && node.properties.description.toLowerCase().includes(searchFilter.toLowerCase())) ||
        (node.properties?.provision && node.properties.provision.toLowerCase().includes(searchFilter.toLowerCase())) ||
        (node.properties?.content && node.properties.content.toLowerCase().includes(searchFilter.toLowerCase()));
      return matchCat && matchSearch;
    });
  }, [graphData, selectedCategory, searchFilter]);

  const selectedNodeRelationships = useMemo(() => {
    if (!selectedNode || !graphData?.links) return { outgoing: [], incoming: [] };
    const outgoing = graphData.links.filter((l) => l.source === selectedNode.id || l.source_key === selectedNode.key);
    const incoming = graphData.links.filter((l) => l.target === selectedNode.id || l.target_key === selectedNode.key);
    return { outgoing, incoming };
  }, [selectedNode, graphData]);

  const handleJumpToNode = (targetKeyOrId: string) => {
    if (!graphData?.nodes) return;
    const target = graphData.nodes.find(
      (n) => n.key === targetKeyOrId || n.id === targetKeyOrId || n.title.toLowerCase() === targetKeyOrId.toLowerCase()
    );
    if (target) {
      setSelectedNode(target);
    }
  };

  const getNodeColor = (category: string) => {
    switch (category) {
      case 'StatutoryAct':
        return {
          bg: 'bg-purple-50/70',
          border: 'border-purple-200',
          badge: 'bg-purple-100/90 text-purple-800 border-purple-200',
          text: 'text-purple-950',
          dot: 'bg-purple-500',
          activeBg: 'bg-purple-50/90 border-purple-400 ring-2 ring-purple-500/20',
        };
      case 'Section':
        return {
          bg: 'bg-emerald-50/70',
          border: 'border-emerald-200',
          badge: 'bg-emerald-100/90 text-emerald-800 border-emerald-200',
          text: 'text-emerald-950',
          dot: 'bg-emerald-500',
          activeBg: 'bg-emerald-50/90 border-emerald-400 ring-2 ring-emerald-500/20',
        };
      case 'PolicyNode':
        return {
          bg: 'bg-blue-50/70',
          border: 'border-blue-200',
          badge: 'bg-blue-100/90 text-blue-800 border-blue-200',
          text: 'text-blue-950',
          dot: 'bg-blue-500',
          activeBg: 'bg-blue-50/90 border-blue-400 ring-2 ring-blue-500/20',
        };
      default:
        return {
          bg: 'bg-slate-50/70',
          border: 'border-slate-200',
          badge: 'bg-slate-100 text-slate-800 border-slate-200',
          text: 'text-slate-950',
          dot: 'bg-slate-500',
          activeBg: 'bg-slate-100 border-slate-400 ring-2 ring-slate-500/20',
        };
    }
  };

  const getRelationBadgeColor = (type: string) => {
    switch (type) {
      case 'MANDATES':
        return 'bg-amber-50 text-amber-900 border-amber-200';
      case 'GOVERNS':
        return 'bg-indigo-50 text-indigo-900 border-indigo-200';
      case 'CONTAINS':
        return 'bg-slate-100 text-slate-800 border-slate-200';
      case 'SUPPORTS':
        return 'bg-emerald-50 text-emerald-900 border-emerald-200';
      case 'PROTECTED_BY':
        return 'bg-rose-50 text-rose-900 border-rose-200';
      default:
        return 'bg-blue-50 text-blue-900 border-blue-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* 4 Olixer Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Entities Card */}
        <div className="card-olixer p-5 bg-gradient-to-b from-white via-slate-50/70 to-purple-50/30 border border-slate-200/90">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-700">Ontology Nodes</span>
            <span className="p-1.5 rounded-lg bg-purple-50 text-purple-700 border border-purple-200/60">
              <Network className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">
              {graphData?.nodes_count ?? 18}
            </span>
            <span className="text-xs font-medium text-slate-500">live entities</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-purple-900 bg-purple-50/70 border border-purple-200/60 rounded-md px-2 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-purple-600" />
              Acts, Sections & Bylaws
            </span>
          </div>
        </div>

        {/* Directional Relationships Card */}
        <div className="card-olixer p-5 bg-gradient-to-b from-white via-slate-50/70 to-indigo-50/30 border border-slate-200/90">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-700">Graph Relationships</span>
            <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200/60">
              <Layers className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-3xl font-extrabold text-slate-900">
              {graphData?.relationships_count ?? 16}
            </span>
            <span className="text-xs font-medium text-slate-500">directional links</span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-indigo-900 bg-indigo-50/70 border border-indigo-200/60 rounded-md px-2 py-0.5">
              <CheckCircle2 className="w-3 h-3 text-indigo-600" />
              Mandates, Governs & Protects
            </span>
          </div>
        </div>

        {/* Neo4j Aura Cluster Card */}
        <div className="card-olixer p-5 bg-gradient-to-b from-white via-slate-50/70 to-emerald-50/30 border border-slate-200/90">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-700">Neo4j Aura Cluster</span>
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200/60">
              <Database className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-xl font-extrabold text-slate-900 truncate">
              {graphData?.status === 'connected' ? 'Connected' : 'Active Graph'}
            </span>
            <span className="text-xs font-medium text-emerald-600 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live Aura
            </span>
          </div>
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-600 bg-slate-100/80 border border-slate-200/80 rounded-md px-2 py-0.5 truncate max-w-full" title={graphData?.database_uri}>
              {graphData?.database_uri?.slice(0, 24) || 'neo4j+s://e4ab5ba2...'}
            </span>
          </div>
        </div>

        {/* Telemetry & Actions Card */}
        <div className="card-olixer p-5 bg-gradient-to-b from-white via-slate-50/70 to-blue-50/30 border border-slate-200/90 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span className="font-display font-semibold text-slate-700">Cloud Sync & Console</span>
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200/60">
              <Cpu className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={fetchGraph}
              disabled={loading}
              className="flex-1 py-1.5 px-3 bg-slate-900 hover:bg-slate-800 active:scale-95 text-white rounded-xl text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Syncing...' : 'Sync Graph'}</span>
            </button>
            <a
              href="https://console.neo4j.io"
              target="_blank"
              rel="noreferrer"
              className="p-2 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold transition-all flex items-center justify-center"
              title="Open Neo4j Aura Cloud Console"
            >
              <ExternalLink className="w-3.5 h-3.5 text-slate-600" />
            </a>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium text-center">
            Synchronized with Render DB ledger & Aura
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card-olixer p-3.5 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white border-slate-200/90">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          <button
            onClick={() => setSelectedCategory('ALL')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 cursor-pointer ${
              selectedCategory === 'ALL'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-slate-100/90 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70'
            }`}
          >
            All Entities ({countsByCategory.ALL})
          </button>
          <button
            onClick={() => setSelectedCategory('StatutoryAct')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
              selectedCategory === 'StatutoryAct'
                ? 'bg-purple-700 text-white shadow-sm'
                : 'bg-purple-50 text-purple-700 border border-purple-200/60 hover:bg-purple-100'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
            Statutory Acts ({countsByCategory.StatutoryAct})
          </button>
          <button
            onClick={() => setSelectedCategory('Section')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
              selectedCategory === 'Section'
                ? 'bg-emerald-700 text-white shadow-sm'
                : 'bg-emerald-50 text-emerald-700 border border-emerald-200/60 hover:bg-emerald-100'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Legal Sections ({countsByCategory.Section})
          </button>
          <button
            onClick={() => setSelectedCategory('PolicyNode')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
              selectedCategory === 'PolicyNode'
                ? 'bg-blue-700 text-white shadow-sm'
                : 'bg-blue-50 text-blue-700 border border-blue-200/60 hover:bg-blue-100'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
            Enterprise Policies ({countsByCategory.PolicyNode})
          </button>
        </div>

        {/* Quick Filter Search */}
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Search nodes or statutory keywords..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl bg-slate-50/80 border border-slate-200 focus:bg-white focus:outline-none focus:border-blue-600 transition-all"
          />
        </div>
      </div>

      {/* Main Grid: Ontology Graph Topology & Entity Dossier */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Interactive Topology Nodes (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="card-olixer p-5 space-y-4 bg-white border border-slate-200/90 shadow-2xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <h4 className="font-display font-bold text-xs uppercase tracking-wider text-slate-800">
                  Ontology Graph Topology ({filteredNodes.length} Nodes)
                </h4>
              </div>
              <span className="text-[11px] text-slate-400">Click any node to inspect dossier</span>
            </div>

            {/* Nodes Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[620px] overflow-y-auto pr-1">
              {filteredNodes.map((node) => {
                const color = getNodeColor(node.category);
                const isSelected = selectedNode?.id === node.id || selectedNode?.key === node.key;
                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`text-left p-4 rounded-2xl border transition-all relative group flex flex-col justify-between cursor-pointer ${
                      isSelected
                        ? color.activeBg
                        : 'bg-white border-slate-200/80 hover:border-blue-300 hover:shadow-xs'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${color.badge}`}>
                          {node.category}
                        </span>
                        {isSelected && (
                          <span className="flex items-center gap-1 text-[10px] font-bold text-blue-700 bg-blue-100/70 px-1.5 py-0.2 rounded">
                            <CheckCircle2 className="w-3 h-3" />
                            Selected
                          </span>
                        )}
                      </div>
                      <h5 className="font-display font-bold text-xs text-slate-900 leading-snug group-hover:text-blue-900 transition-colors">
                        {node.title}
                      </h5>
                      <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                        {node.properties?.provision || node.properties?.content || node.properties?.description || 'Statutory node'}
                      </p>
                    </div>

                    {/* Node Metadata Footer */}
                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400 font-medium">
                      <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">{node.key}</span>
                      {node.properties?.overtime_rate && (
                        <span className="font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200/50">
                          {node.properties.overtime_rate}x Overtime
                        </span>
                      )}
                      {node.properties?.annual_quota && (
                        <span className="font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200/50">
                          {node.properties.annual_quota}d Quota
                        </span>
                      )}
                      {node.properties?.jurisdiction && (
                        <span className="font-semibold text-purple-700">{node.properties.jurisdiction}</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {filteredNodes.length === 0 && (
              <div className="text-center py-12 text-slate-400 text-xs">
                No graph nodes match "{searchFilter}".
              </div>
            )}
          </div>

          {/* Cypher Prompt Reference Dossier */}
          <div className="card-olixer p-4 bg-slate-900 text-slate-200 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-blue-300 font-semibold">
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-blue-400" />
                Live Cypher Traversal Query
              </span>
              <span className="text-[10px] text-slate-400 font-mono bg-slate-800 px-2 py-0.5 rounded">Neo4j Bolt</span>
            </div>
            <div className="text-[11px] text-slate-300 leading-relaxed font-mono bg-slate-950 p-3 rounded-xl border border-slate-800/80 overflow-x-auto">
              MATCH (act:StatutoryAct)-[:CONTAINS]-&gt;(sec:Section)-[r:MANDATES|GOVERNS]-&gt;(pol:PolicyNode)
              <br />
              WHERE toLower(sec.title) CONTAINS $query
              <br />
              RETURN act.name AS act, sec.section_number, type(r), pol.title
            </div>
          </div>
        </div>

        {/* Right Column: Node Inspector & Linked Relationships (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {selectedNode ? (
            <div className="card-olixer p-6 space-y-5 bg-gradient-to-b from-white to-slate-50/50 border border-slate-200/90 shadow-sm">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold border ${
                      getNodeColor(selectedNode.category).badge
                    }`}
                  >
                    {selectedNode.category}
                  </span>
                  <span className="text-[10px] font-mono font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200/60">
                    {selectedNode.key}
                  </span>
                </div>
                <h3 className="font-display text-base font-bold text-slate-900 leading-tight">
                  {selectedNode.title}
                </h3>
              </div>

              {/* Node Properties Dossier */}
              <div className="space-y-3 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
                <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Entity Properties</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                </div>
                {selectedNode.properties?.provision && (
                  <div className="text-xs text-slate-700 leading-relaxed">
                    <span className="font-bold text-slate-900 block mb-0.5">Statutory Provision:</span>
                    <div className="bg-slate-50/80 p-2.5 rounded-xl border border-slate-100 text-slate-700 italic">
                      "{selectedNode.properties.provision}"
                    </div>
                  </div>
                )}
                {selectedNode.properties?.content && (
                  <div className="text-xs text-slate-700 leading-relaxed">
                    <span className="font-bold text-slate-900 block mb-0.5">Policy Content:</span>
                    <div className="bg-slate-50/80 p-2.5 rounded-xl border border-slate-100 text-slate-700">
                      {selectedNode.properties.content}
                    </div>
                  </div>
                )}
                {selectedNode.properties?.description && (
                  <div className="text-xs text-slate-700 leading-relaxed">
                    <span className="font-bold text-slate-900 block mb-0.5">Description:</span>
                    <div className="bg-slate-50/80 p-2.5 rounded-xl border border-slate-100 text-slate-700">
                      {selectedNode.properties.description}
                    </div>
                  </div>
                )}
                {selectedNode.properties?.citation && (
                  <div className="text-[11px] text-blue-900 font-medium bg-blue-50/70 p-2 rounded-lg border border-blue-200/60 flex items-start gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                    <span><strong>Citation:</strong> {selectedNode.properties.citation}</span>
                  </div>
                )}

                {/* Key-Value Chips */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-100 text-xs">
                  {selectedNode.properties?.daily_limit_hours && (
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
                      <div className="text-[10px] text-slate-500 font-bold">Daily Max Hours</div>
                      <div className="font-bold text-slate-900 text-sm mt-0.5">{selectedNode.properties.daily_limit_hours} hrs</div>
                    </div>
                  )}
                  {selectedNode.properties?.overtime_rate && (
                    <div className="p-2.5 rounded-xl bg-emerald-50/80 border border-emerald-200/70">
                      <div className="text-[10px] text-emerald-700 font-bold">Overtime Rate</div>
                      <div className="font-bold text-emerald-900 text-sm mt-0.5">{selectedNode.properties.overtime_rate}x wages</div>
                    </div>
                  )}
                  {selectedNode.properties?.annual_quota && (
                    <div className="p-2.5 rounded-xl bg-blue-50/80 border border-blue-200/70">
                      <div className="text-[10px] text-blue-700 font-bold">Statutory Quota</div>
                      <div className="font-bold text-blue-900 text-sm mt-0.5">{selectedNode.properties.annual_quota} days</div>
                    </div>
                  )}
                  {selectedNode.properties?.max_accumulation_days !== undefined && (
                    <div className="p-2.5 rounded-xl bg-indigo-50/80 border border-indigo-200/70">
                      <div className="text-[10px] text-indigo-700 font-bold">Carry Forward Cap</div>
                      <div className="font-bold text-indigo-900 text-sm mt-0.5">{selectedNode.properties.max_accumulation_days} days</div>
                    </div>
                  )}
                  {selectedNode.properties?.coverage_amount_inr && (
                    <div className="p-2.5 rounded-xl bg-emerald-50/80 border border-emerald-200/70">
                      <div className="text-[10px] text-emerald-700 font-bold">Health Coverage</div>
                      <div className="font-bold text-emerald-900 text-sm mt-0.5">₹{selectedNode.properties.coverage_amount_inr.toLocaleString()}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Linked Relationships */}
              <div className="space-y-3">
                <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Graph Directional Links</span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    {selectedNodeRelationships.outgoing.length + selectedNodeRelationships.incoming.length} Relations
                  </span>
                </div>

                {/* Outgoing Links */}
                {selectedNodeRelationships.outgoing.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-1">
                      <ArrowRight className="w-3 h-3 text-blue-600" />
                      <span>Outgoing Links (Out -&gt;)</span>
                    </div>
                    {selectedNodeRelationships.outgoing.map((l) => (
                      <div
                        key={l.id}
                        onClick={() => handleJumpToNode(l.target_key)}
                        className="p-3 rounded-xl bg-white border border-slate-200/90 hover:border-blue-300 hover:shadow-xs transition-all space-y-1 cursor-pointer group"
                        title={`Click to inspect ${l.target_key}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${getRelationBadgeColor(l.type)}`}>
                            {l.type}
                          </span>
                          <span className="text-[10px] font-mono font-bold text-slate-700 group-hover:text-blue-700 transition-colors flex items-center gap-1">
                            &rarr; {l.target_key}
                          </span>
                        </div>
                        {l.rule && <p className="text-[11px] text-slate-600 italic">"{l.rule}"</p>}
                      </div>
                    ))}
                  </div>
                )}

                {/* Incoming Links */}
                {selectedNodeRelationships.incoming.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-1">
                      <ArrowLeft className="w-3 h-3 text-indigo-600" />
                      <span>Incoming Links (&lt;- In)</span>
                    </div>
                    {selectedNodeRelationships.incoming.map((l) => (
                      <div
                        key={l.id}
                        onClick={() => handleJumpToNode(l.source_key)}
                        className="p-3 rounded-xl bg-white border border-slate-200/90 hover:border-indigo-300 hover:shadow-xs transition-all space-y-1 cursor-pointer group"
                        title={`Click to inspect ${l.source_key}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${getRelationBadgeColor(l.type)}`}>
                            {l.type}
                          </span>
                          <span className="text-[10px] font-mono font-bold text-slate-700 group-hover:text-indigo-700 transition-colors flex items-center gap-1">
                            &larr; {l.source_key}
                          </span>
                        </div>
                        {l.rule && <p className="text-[11px] text-slate-600 italic">"{l.rule}"</p>}
                      </div>
                    ))}
                  </div>
                )}

                {selectedNodeRelationships.outgoing.length === 0 && selectedNodeRelationships.incoming.length === 0 && (
                  <div className="text-xs text-slate-400 italic bg-white p-3 rounded-xl border border-slate-100 text-center">
                    No directional links recorded for this entity.
                  </div>
                )}
              </div>

              {/* Action: Query In Graph RAG */}
              {onSelectQuery && (
                <button
                  onClick={() => onSelectQuery(selectedNode.title)}
                  className="btn-pill-dark w-full justify-center py-2.5 shadow-sm"
                >
                  <Search className="w-3.5 h-3.5" />
                  <span>Execute Policy Search on this Node</span>
                </button>
              )}
            </div>
          ) : (
            <div className="card-olixer p-12 text-center text-slate-400 text-xs bg-white">
              Select a node on the left to inspect properties and graph connections.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
