// src/contexts/ViewContext.tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Types
type ViewMode = 'rh' | 'collaborateur';

export interface ViewContextType {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  isCollaborateurRh: boolean;
}

// Context
const ViewContext = createContext<ViewContextType | undefined>(undefined);

// Provider
export function ViewProvider({ children, userRole }: { children: ReactNode; userRole?: string }) {
  const isCollaborateurRh = userRole === 'collaborateur_rh';
  
  // Par défaut, vue RH pour collaborateur_rh
  const [viewMode, setViewModeState] = useState<ViewMode>(() => {
    if (isCollaborateurRh) {
      // Récupérer depuis localStorage si disponible, sinon 'rh' par défaut
      const saved = localStorage.getItem('collaborateur_rh_view_mode');
      return (saved === 'collaborateur' ? 'collaborateur' : 'rh') as ViewMode;
    }
    return 'rh';
  });

  // Sauvegarder dans localStorage quand la vue change
  useEffect(() => {
    if (isCollaborateurRh) {
      localStorage.setItem('collaborateur_rh_view_mode', viewMode);
    }
  }, [viewMode, isCollaborateurRh]);

  const setViewMode = (mode: ViewMode) => {
    if (isCollaborateurRh) {
      setViewModeState(mode);
    }
  };

  return (
    <ViewContext.Provider value={{ viewMode, setViewMode, isCollaborateurRh }}>
      {children}
    </ViewContext.Provider>
  );
}

// Hook
export function useView() {
  const context = useContext(ViewContext);
  if (context === undefined) {
    throw new Error('useView must be used within a ViewProvider');
  }
  return context;
}

/** Hors ViewProvider : undefined (pas d’exception), pour composants montés sans provider. */
export function useViewOptional(): ViewContextType | undefined {
  return useContext(ViewContext);
}
