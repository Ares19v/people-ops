import React from 'react';
import { useDemoMode } from '../context/DemoModeContext';

interface FeatureExplainerIconProps {
  featureKey: string;
  className?: string;
  inline?: boolean;
}

export const FeatureExplainerIcon: React.FC<FeatureExplainerIconProps> = ({
  featureKey,
  className = '',
  inline = true,
}) => {
  const { isDemoMode, openExplainer } = useDemoMode();

  // If Demo Mode is OFF, all 'i' buttons are completely hidden
  if (!isDemoMode) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        openExplainer(featureKey);
      }}
      title="Feature Details (Demo Mode)"
      aria-label={`Feature explanation for ${featureKey}`}
      className={`group relative ${
        inline ? 'inline-flex' : 'flex'
      } items-center justify-center w-3.5 h-3.5 rounded-full border border-slate-300/40 hover:border-slate-500/70 bg-slate-100/25 hover:bg-slate-100 text-slate-400/50 hover:text-slate-700 transition-all duration-150 cursor-pointer select-none shrink-0 align-middle ml-1.5 focus:outline-none focus:ring-1 focus:ring-slate-300 ${className}`}
    >
      <span className="text-[9.5px] font-serif italic leading-none transform -translate-y-[0.5px]">
        i
      </span>
      {/* Subtle indicator dot on hover */}
      <span className="absolute -top-0.5 -right-0.5 w-1 h-1 rounded-full bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
    </button>
  );
};
