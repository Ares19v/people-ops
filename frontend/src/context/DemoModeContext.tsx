import React, { createContext, useContext, useState, ReactNode } from 'react';
import { ExplainerFeature, FEATURE_EXPLAINERS } from '../data/featureExplainers';

export type { ExplainerFeature };

interface DemoModeContextType {
  isDemoMode: boolean;
  toggleDemoMode: () => void;
  setDemoMode: (enabled: boolean) => void;
  activeExplainer: ExplainerFeature | null;
  openExplainer: (key: string) => void;
  closeExplainer: () => void;
}

const DemoModeContext = createContext<DemoModeContextType | undefined>(undefined);

export const DemoModeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Starts with toggle OFF by default as requested
  const [isDemoMode, setIsDemoMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('demo_mode_enabled');
    return saved === 'true'; // Defaults to false if not set
  });

  const [activeExplainer, setActiveExplainer] = useState<ExplainerFeature | null>(null);

  const toggleDemoMode = () => {
    setIsDemoMode((prev) => {
      const next = !prev;
      localStorage.setItem('demo_mode_enabled', String(next));
      return next;
    });
  };

  const setDemoMode = (enabled: boolean) => {
    setIsDemoMode(enabled);
    localStorage.setItem('demo_mode_enabled', String(enabled));
  };

  const openExplainer = (key: string) => {
    const feature = FEATURE_EXPLAINERS[key];
    if (feature) {
      setActiveExplainer(feature);
    } else {
      // Fallback for custom keys
      setActiveExplainer({
        key,
        title: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        category: 'FEATURE HIGHLIGHT',
        overview: 'Specialized People Operations enterprise capability enforcing labor law compliance.',
        howItWorks: 'Operates deterministically within the statutory validation pipeline and multi-agent harness.',
        demoTalkTrack: [
          'Highlight this capability to demonstrate organizational efficiency and compliance accuracy.'
        ],
        statutoryOrTechCitation: 'Maharashtra Shops & Establishments Act, 2017'
      });
    }
  };

  const closeExplainer = () => {
    setActiveExplainer(null);
  };

  return (
    <DemoModeContext.Provider
      value={{
        isDemoMode,
        toggleDemoMode,
        setDemoMode,
        activeExplainer,
        openExplainer,
        closeExplainer,
      }}
    >
      {children}
    </DemoModeContext.Provider>
  );
};

export const useDemoMode = (): DemoModeContextType => {
  const context = useContext(DemoModeContext);
  if (!context) {
    return {
      isDemoMode: false,
      toggleDemoMode: () => {},
      setDemoMode: () => {},
      activeExplainer: null,
      openExplainer: () => {},
      closeExplainer: () => {},
    };
  }
  return context;
};
