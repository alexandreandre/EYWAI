import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { getCompanySetupStatus } from '@/api/adminImport';
import { companySetupStatusQueryKey } from '@/features/admin-import/hooks/useCompanySetupStatus';

export type CompanyImportTab =
  | 'dsn'
  | 'seniority'
  | 'payroll-export'
  | 'cp'
  | 'params'
  | 'planning';

type CompanyImportContextValue = {
  companyId: string;
  setCompanyId: (id: string) => void;
  activeTab: CompanyImportTab | string;
  setActiveTab: (tab: string) => void;
  wizardOpen: boolean;
  openWizard: (step?: string) => void;
  closeWizard: () => void;
  wizardStep: string;
  setWizardStep: (step: string) => void;
};

const CompanyImportContext = createContext<CompanyImportContextValue | null>(null);

const VALID_TABS: CompanyImportTab[] = [
  'dsn',
  'seniority',
  'payroll-export',
  'cp',
  'params',
  'planning',
];

function normalizeTab(tab: string): CompanyImportTab {
  if (tab === 'rib') return 'payroll-export';
  return VALID_TABS.includes(tab as CompanyImportTab) ? (tab as CompanyImportTab) : 'dsn';
}

function normalizeWizardStep(step: string): string {
  return step === 'rib' ? 'payroll-export' : step;
}

export function CompanyImportProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const urlCompanyId = searchParams.get('companyId') ?? '';
  const urlTab = searchParams.get('tab') ?? 'dsn';

  const [wizardOpen, setWizardOpen] = useState(() => searchParams.get('wizard') === '1');
  const [wizardStep, setWizardStepState] = useState(() =>
    normalizeWizardStep(searchParams.get('wizardStep') ?? 'intro'),
  );

  const companyId = urlCompanyId;
  const activeTab = normalizeTab(urlTab);

  const syncParams = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(patch).forEach(([key, value]) => {
        if (value === null || value === '') next.delete(key);
        else next.set(key, value);
      });
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setCompanyId = useCallback(
    (id: string) => {
      syncParams({ companyId: id || null });
      if (id) {
        void queryClient.prefetchQuery({
          queryKey: companySetupStatusQueryKey(id),
          queryFn: () => getCompanySetupStatus(id),
        });
      }
    },
    [syncParams, queryClient],
  );

  const setActiveTab = useCallback(
    (tab: string) => {
      syncParams({ tab });
    },
    [syncParams],
  );

  const openWizard = useCallback(
    (step = 'intro') => {
      const normalized = normalizeWizardStep(step);
      setWizardOpen(true);
      setWizardStepState(normalized);
      syncParams({ wizard: '1', wizardStep: normalized });
    },
    [syncParams],
  );

  const closeWizard = useCallback(() => {
    setWizardOpen(false);
    syncParams({ wizard: null, wizardStep: null });
  }, [syncParams]);

  /** Navigation interne — état local uniquement (pas de re-render page entière). */
  const setWizardStep = useCallback((step: string) => {
    setWizardStepState(normalizeWizardStep(step));
  }, []);

  const value = useMemo(
    () => ({
      companyId,
      setCompanyId,
      activeTab,
      setActiveTab,
      wizardOpen,
      openWizard,
      closeWizard,
      wizardStep,
      setWizardStep,
    }),
    [
      companyId,
      setCompanyId,
      activeTab,
      setActiveTab,
      wizardOpen,
      openWizard,
      closeWizard,
      wizardStep,
      setWizardStep,
    ],
  );

  return <CompanyImportContext.Provider value={value}>{children}</CompanyImportContext.Provider>;
}

export function useCompanyImport() {
  const ctx = useContext(CompanyImportContext);
  if (!ctx) {
    throw new Error('useCompanyImport doit être utilisé dans CompanyImportProvider');
  }
  return ctx;
}

export function useCompanyImportOptional() {
  return useContext(CompanyImportContext);
}
