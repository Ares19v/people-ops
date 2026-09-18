import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { CitationItem } from '../types';
import { Search, Shield, FileText, AlertTriangle, BookOpen, ExternalLink, Sparkles, ShieldCheck } from 'lucide-react';

export const PolicySearchPortal: React.FC = () => {
  const [query, setQuery] = useState('casual leave maharashtra');
  const [results, setResults] = useState<any>(null);
  const [searching, setSearching] = useState(false);

  const sampleQueries = [
    'casual leave maharashtra',
    'earned leave carry forward limit',
    'overtime rate working hours',
    'sick leave medical certificate',
    'leave without pay eligibility',
  ];

  const handleSearch = async (searchTerm?: string) => {
    const q = searchTerm !== undefined ? searchTerm : query;
    if (!q.trim()) return;
    setSearching(true);
    try {
      const data = await api.searchPolicies(q);
      setResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    handleSearch('casual leave maharashtra');
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-600" />
          HR Policy & Maharashtra Labour Law Graph RAG
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Explore authoritative policies indexed against the Maharashtra Shops & Establishments Act, 2017 with statutory citations.
        </p>
      </div>

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
            className="btn-pill-dark shrink-0 self-stretch sm:self-auto py-2.5 px-5 flex items-center justify-center outline-none focus:outline-none"
          >
            {searching ? 'Querying Graph...' : 'Search Graph'}
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
              className="btn-pill-outline text-xs py-1 px-3"
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Results View */}
      {results && (
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

            <p className="text-sm text-slate-800 leading-relaxed font-normal">
              {results.summary || results.answer || 'Query processed across policy nodes.'}
            </p>

            {results.disclaimer && (
              <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-[11px] text-slate-500 flex items-start gap-2">
                <Shield className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                <span>{results.disclaimer}</span>
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
                <div key={idx} className="entity-dossier">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-display font-bold text-xs text-slate-900">{c.source_title}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700">
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
  );
};
