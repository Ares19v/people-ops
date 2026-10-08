import React from 'react';
import { useDemoMode } from '../context/DemoModeContext';

export const DemoModeToggleBar: React.FC = () => {
  const { isDemoMode, toggleDemoMode } = useDemoMode();

  return (
    <button
      type="button"
      onClick={toggleDemoMode}
      title={
        isDemoMode
          ? 'Demo Explainer is ON (click to hide)'
          : 'Enable Demo Explainer'
      }
      className="inline-flex items-center gap-1.5 text-slate-400 hover:text-slate-600 transition-colors py-0.5 px-1 rounded cursor-pointer group outline-none focus:outline-none"
    >
      <span className="text-[11px] font-normal tracking-tight text-slate-400 group-hover:text-slate-500 transition-colors select-none">
        Demo Explainer
      </span>

      {/* Subtle Micro-Switch */}
      <span
        role="switch"
        aria-checked={isDemoMode}
        className={`relative inline-flex h-[12px] w-[22px] shrink-0 rounded-full transition-colors duration-200 ease-in-out ${
          isDemoMode ? 'bg-blue-600' : 'bg-slate-300/80 group-hover:bg-slate-400/80'
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-[8px] w-[8px] transform rounded-full bg-white shadow-xs transition duration-200 ease-in-out mt-[2px] ml-[2px] ${
            isDemoMode ? 'translate-x-[10px]' : 'translate-x-0'
          }`}
        />
      </span>
    </button>
  );
};
