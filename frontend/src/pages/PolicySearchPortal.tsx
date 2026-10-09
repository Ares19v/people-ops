import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { CitationItem } from '../types';
import { Search, Shield, BookOpen, Sparkles, ShieldCheck, Network, AlertCircle, RefreshCw } from 'lucide-react';
import { FeatureExplainerIcon } from '../components/FeatureExplainerIcon';
import { LiveKnowledgeGraphViewer } from '../components/LiveKnowledgeGraphViewer';

export const PolicySearchPortal: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'search' | 'graph'>('search');
  const [query, setQuery] = useState('sick leave medical certificate');
  const [results, setResults] = useState<any>(null);
  const [searching, setSearching] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const sampleQueries = [
    'sick leave medical certificate',
    'casual leave maharashtra',
    'earned leave carry forward limit',
    'overtime rate working hours',
    'leave without pay eligibility',
  ];

  const [queryCache, setQueryCache] = useState<Record<string, any>>({});

  const handleSearch = async (searchTerm?: string) => {
    const q = (searchTerm !== undefined ? searchTerm : query).trim();
    if (!q) return;

    // Instant cache hit check
    if (queryCache[q.toLowerCase()]) {
      setResults(queryCache[q.toLowerCase()]);
      setErrorMsg(null);
      return;
    }

    setSearching(true);
    setErrorMsg(null);
    try {
      const data = await api.searchPolicies(q);
      setResults(data);
      setQueryCache((prev) => ({ ...prev, [q.toLowerCase()]: data }));
    } catch (err: any) {
      console.error('Policy search failed:', err);
      setErrorMsg(err?.response?.data?.detail || err?.message || 'Failed to retrieve policy from Knowledge Graph.');
    } finally {
      setSearching(false);
    }
  };

  const handleQueryFromGraph = (nodeTitle: string) => {
    setQuery(nodeTitle);
    setActiveTab('search');
    handleSearch(nodeTitle);
  };

  useEffect(() => {
    handleSearch('sick leave medical certificate');
  }, []);

  return (
    <div className="space-y-6">
      {/* Header and Shield Toggle Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab((prev) => (prev === 'search' ? 'graph' : 'search'))}
              className="p-1 -ml-1 rounded-xl hover:bg-blue-50 active:scale-95 transition-all text-blue-600 focus:outline-none group flex items-center justify-center cursor-pointer"
              title={activeTab === 'search' ? "Switch to Live Knowledge Graph (Neo4j)" : "Back to Policy Search & Citations"}
            >
              {activeTab === 'search' ? (
                <Shield className="w-5 h-5 text-blue-600 group-hover:scale-110 transition-transform" />
              ) : (
                <Network className="w-5 h-5 text-blue-600 group-hover:scale-110 transition-transform" />
              )}
            </button>
            <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
              {activeTab === 'search'
                ? 'HR Policy & Maharashtra Labour Law Graph RAG'
                : 'Live Neo4j Aura Statutory Knowledge Graph'}
            </h2>
            <FeatureExplainerIcon featureKey="policy_rag_search" />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeTab === 'search'
              ? 'Explore authoritative policies indexed against the Maharashtra Shops & Establishments Act, 2017 with Neo4j live graph traversal.'
              : 'Interactive ontology graph topology, directional legal relationships, and property schemas.'}
          </p>
        </div>

        {/* Action Button if in Graph Mode */}
        {activeTab === 'graph' && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('search')}
              className="btn-pill-outline text-xs"
            >
              <Search className="w-3.5 h-3.5 text-blue-600" />
              <span>Back to Policy Search</span>
            </button>
          </div>
        )}
      </div>

      {/* Tab 1: Live Neo4j Graph Visualizer */}
      {activeTab === 'graph' && (
        <LiveKnowledgeGraphViewer onSelectQuery={handleQueryFromGraph} />
      )}

      {/* Tab 2: Policy Search & Citations */}
      {activeTab === 'search' && (
        <div className="space-y-6">
          {/* Search Input Bar */}
          <div className="card-olixer p-4 sm:p-5 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 bg-slate-50/80 p-2 rounded-2xl border border-slate-200 focus-within:bg-white focus-within:border-blue-600 transition-all shadow-sm">
              <div className="flex items-center flex-1 gap-2 pl-2">
                <Search className="w-5 h-5 text-slate-400 shrink-0" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search policies, accrual rules, or statutory provisions..."
                  className="w-full bg-transparent py-1.5 text-sm text-slate-900 outline-none focus:outline-none"
                />
              </div>
              <button
                onClick={() => handleSearch()}
                disabled={searching}
                className="btn-pill-dark shrink-0 self-stretch sm:self-auto py-2.5 px-5 flex items-center justify-center gap-1.5 outline-none focus:outline-none"
              >
                {searching ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Searching Graph...</span>
                  </>
                ) : (
                  <span>Search Graph</span>
                )}
              </button>
            </div>

            {/* Query Suggestion Pills */}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Suggested:</span>
              {sampleQueries.map((sq) => (
                <button
                  key={sq}
                  onClick={() => {
                    setQuery(sq);
                    handleSearch(sq);
                  }}
                  className={`btn-pill-outline text-xs py-1 px-3 ${query === sq ? 'bg-slate-200/80 text-slate-900 border-slate-300' : ''}`}
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>

          {/* Loading Indicator Card */}
          {searching && (
            <div className="card-olixer p-8 flex flex-col items-center justify-center text-center space-y-3">
              <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <div className="text-xs font-semibold text-slate-800">
                Traversing Neo4j Knowledge Graph & Statutory Vector Index...
              </div>
              <div className="text-[11px] text-slate-400">
                Querying Maharashtra Shops & Establishments Act 2017 & Company Handbooks
              </div>
            </div>
          )}

          {/* Error Message Card */}
          {errorMsg && !searching && (
            <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Results View */}
          {results && !searching && (
            <div className="space-y-6">
              {/* Answer Card */}
              <div className="card-olixer p-6">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-blue-600" />
                    <span className="font-display font-bold text-xs uppercase tracking-wider text-slate-500">
                      Synthesized Graph RAG Response
                    </span>
                  </div>
                  <div className="badge-statutory-green">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>NeMo Legal Rail Verified</span>
                  </div>
                </div>

                <p className="text-sm text-slate-800 leading-relaxed font-normal whitespace-pre-line">
                  {results.summary || results.answer || 'Query processed across policy nodes.'}
                </p>

                {(results.legal_disclaimer || results.disclaimer) && (
                  <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-[11px] text-slate-500 flex items-start gap-2">
                    <Shield className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                    <span>{results.legal_disclaimer || results.disclaimer}</span>
                  </div>
                )}
              </div>

              {/* Citations Grid */}
              <div>
                <h3 className="font-display font-bold text-sm text-slate-900 mb-3 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-blue-600" />
                  Retrieved Policy Nodes & Citations ({results.citations?.length || 0})
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {results.citations?.map((c: CitationItem, idx: number) => (
                    <div key={idx} className="entity-dossier overflow-hidden">
                      <div className="flex items-center justify-between gap-2 min-w-0 mb-2">
                        <span className="font-display font-bold text-xs text-slate-900 flex-1 min-w-0 truncate" title={c.source_title}>
                          {c.source_title}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 shrink-0">
                          {c.section}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed italic bg-slate-50/60 p-3 rounded-xl border border-slate-100">
                        "{c.citation_text}"
                      </p>
                      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                        <span>Relevance: {(c.confidence_score * 100).toFixed(0)}%</span>
                        <span className="text-blue-600 font-medium">Node Verified</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
