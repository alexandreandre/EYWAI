import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type BootContextType = {
  /** Libellé affiché sous la barre de progression */
  stepLabel: string;
  /** 0–100, progression visuelle */
  progress: number;
  /** Met à jour l'étape et avance la progression */
  markStep: (label: string, progress?: number) => void;
  /** Le splash boot est-il encore visible ? */
  isBooting: boolean;
  /** Termine le boot (appelé par BootGate) */
  finishBoot: () => void;
};

const BootContext = createContext<BootContextType | null>(null);

const DEFAULT_LABEL = 'Chargement…';

export function BootProvider({ children }: { children: ReactNode }) {
  const [stepLabel, setStepLabel] = useState(DEFAULT_LABEL);
  const [progress, setProgress] = useState(0);
  const [isBooting, setIsBooting] = useState(true);

  const markStep = useCallback((label: string, nextProgress?: number) => {
    setStepLabel(label);
    if (typeof nextProgress === 'number') {
      setProgress((prev) => Math.max(prev, Math.min(100, nextProgress)));
    }
  }, []);

  const finishBoot = useCallback(() => {
    setProgress(100);
    setIsBooting(false);
  }, []);

  const value = useMemo(
    () => ({ stepLabel, progress, markStep, isBooting, finishBoot }),
    [stepLabel, progress, markStep, isBooting, finishBoot],
  );

  return <BootContext.Provider value={value}>{children}</BootContext.Provider>;
}

export function useBoot() {
  const ctx = useContext(BootContext);
  if (!ctx) {
    throw new Error('useBoot doit être utilisé dans un BootProvider');
  }
  return ctx;
}

/** Hors BootProvider (routes publiques) : no-op */
export function useBootOptional(): BootContextType | null {
  return useContext(BootContext);
}
