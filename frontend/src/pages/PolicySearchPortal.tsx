import React, { useState } from 'react';
import { api } from '../api';
import { CitationItem } from '../types';
import { Search, Shield, FileText, AlertTriangle, BookOpen, ExternalLink, Sparkles } from 'lucide-react';

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
    const q = searchTerm || query;
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">HR Policy & Maharashtra Labour Law Graph RAG</h2>
        <p className="text-xs text-slate-500 mt-1">
          Explore authoritative policies indexed against the Maharashtra Shops & Establishments Act, 2017.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-3">
        <div className="flex items-center gap-2 bg-slate-50 p-2 rounded-xl border border-slate-200 focus-within:bg-white focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all">
          <Search className="w-5 h-5 text-slate-400 ml-2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search policies, accrual rules, or statutory provisions..."
            className="flex-1 bg-transparent px-2 py-1 text-sm text-slate-900 focus:outline-none"
          />
          <button
            onClick={() => handleSearch()}
            disabled={searching}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
          >
            {searching ? 'Querying Graph...' : 'Search'}
          </button>
        </div>

        {/* Suggestion Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium">Try asking:</span>
          {sampleQueries.map((sq) => (
            <button
              key={sq}
              onClick={() => {
                setQuery(sq);
                handleSearch(sq);
              }}
              className="px-2.5 py-1 bg-slate-100 hover:bg-emerald-50 hover:text-emerald-700 text-slate-600 rounded-lg transition-colors"
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Search Results Display */}
      {results && (
        <div className="space-y-4">
          {/* Statutory Disclaimer Alert */}
          {results.legal_disclaimer && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 text-xs flex items-start gap-3">
              <Shield className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Statutory Guidance Notice:</span>
                <p className="mt-0.5 text-blue-800">{results.legal_disclaimer}</p>
              </div>
            </div>
          )}

          {/* Citations Grid */}
          {results.citations && results.citations.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Authoritative Graph Citations ({results.citations.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {results.citations.map((cit: CitationItem, idx: number) => (
                  <div
                    key={idx}
                    className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-emerald-200 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-slate-900">{cit.source_title}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          cit.document_type === 'STATUTORY_LAW'
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {cit.document_type}
                      </span>
                    </div>
                    <div className="text-xs text-slate-600 mt-2 font-medium">{cit.section}</div>
                    <div className="text-xs text-slate-500 mt-1">{cit.citation_text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Retrieved Synthesis Card */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-emerald-600" />
              Synthesized Knowledge Context
            </h3>
            <div className="whitespace-pre-wrap text-xs text-slate-700 leading-relaxed font-sans bg-slate-50 p-4 rounded-xl border border-slate-100">
              {results.context}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
