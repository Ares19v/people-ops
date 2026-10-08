import React, { useEffect } from 'react';
import { useDemoMode } from '../context/DemoModeContext';
import { X, Sparkles, Shield, BookOpen, Mic, CheckCircle2 } from 'lucide-react';

export const FeatureExplainerModal: React.FC = () => {
  const { activeExplainer, closeExplainer } = useDemoMode();

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeExplainer();
      }
    };
    if (activeExplainer) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeExplainer, closeExplainer]);

  if (!activeExplainer) return null;

  return (
    <>
      {/* 25% Blurred Background Backdrop */}
      <div
        className="fixed inset-0 z-50 popup-screen-blur transition-opacity duration-200"
        onClick={closeExplainer}
      />

      {/* Modal Dialog Content */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 pointer-events-none">
        <div
          role="dialog"
          aria-modal="true"
          className="pointer-events-auto w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200/90 overflow-hidden transform transition-all duration-200 animate-in fade-in zoom-in-95 flex flex-col max-h-[90vh]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 bg-gradient-to-r from-slate-900 via-slate-850 to-blue-950 text-white flex items-center justify-between border-b border-slate-800 shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-blue-600/30 text-blue-400 flex items-center justify-center border border-blue-500/40 shadow-inner">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-blue-300 font-semibold px-2 py-0.5 rounded-full bg-blue-900/50 border border-blue-700/50">
                  {activeExplainer.category}
                </span>
                <h3 className="font-display font-bold text-base tracking-tight text-white mt-1">
                  {activeExplainer.title}
                </h3>
              </div>
            </div>
            <button
              onClick={closeExplainer}
              aria-label="Close feature explainer"
              className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scrollable Content Body */}
          <div className="p-6 overflow-y-auto space-y-5 text-xs text-slate-700 leading-relaxed">
            {/* Overview Section */}
            <div>
              <div className="flex items-center gap-1.5 text-slate-900 font-display font-bold text-xs uppercase tracking-wider mb-1.5">
                <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                <span>Feature Overview</span>
              </div>
              <p className="bg-slate-50/80 border border-slate-100 rounded-xl p-3 text-slate-700 text-xs leading-relaxed">
                {activeExplainer.overview}
              </p>
            </div>

            {/* How It Works Section */}
            <div>
              <div className="flex items-center gap-1.5 text-slate-900 font-display font-bold text-xs uppercase tracking-wider mb-1.5">
                <Shield className="w-3.5 h-3.5 text-indigo-600" />
                <span>Under The Hood & Enforcement</span>
              </div>
              <p className="bg-indigo-50/40 border border-indigo-100/60 rounded-xl p-3 text-indigo-950 text-xs leading-relaxed">
                {activeExplainer.howItWorks}
              </p>
            </div>

            {/* Demo Talk Track (What to say during a presentation) */}
            {activeExplainer.demoTalkTrack && activeExplainer.demoTalkTrack.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 text-slate-900 font-display font-bold text-xs uppercase tracking-wider mb-1.5">
                  <Mic className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Presenter Talk Track (Say This to Your Audience)</span>
                </div>
                <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-3 space-y-2">
                  {activeExplainer.demoTalkTrack.map((point: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-emerald-950 text-xs">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{point}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Statutory Citation Badge */}
            {activeExplainer.statutoryOrTechCitation && (
              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span className="font-semibold text-slate-600">Governing Statute / Spec:</span>
                <span className="font-mono text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-100 font-medium">
                  {activeExplainer.statutoryOrTechCitation}
                </span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between shrink-0">
            <span className="text-[11px] text-slate-500 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              Demo Mode Active &bull; Press <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono shadow-2xs">ESC</kbd> to close
            </span>
            <button
              onClick={closeExplainer}
              className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </>
  );
};
