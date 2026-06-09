/**
 * CompanyContext : Gestion du contexte d'entreprise active pour multi-entreprises
 *
 * Ce contexte gère :
 * - Les entreprises accessibles par l'utilisateur
 * - L'entreprise active (celle sur laquelle l'utilisateur travaille)
 * - La persistance du choix dans localStorage
 * - Le header X-Active-Company envoyé au backend
 */

import { log } from '@/lib/logger';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from './AuthContext';
import apiClient from '../api/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { isBadgeuseTerminalPath } from '@/lib/sessionKeepAlive';
import { hasTerminalToken } from '@/lib/badgeuseTerminalAuth';

// ===== Types =====

export interface CompanyAccess {
  company_id: string;
  company_name: string;
  role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur';
  is_primary: boolean;
  siret?: string;
  logo_url?: string | null;
  logo_scale?: number;
  group_id?: string;
  group_name?: string;
  group_logo_url?: string | null;
  group_logo_scale?: number;
}

export interface CompanyContextType {
  accessibleCompanies: CompanyAccess[];
  activeCompany: CompanyAccess | null;
  setActiveCompany: (companyId: string) => void;
  refreshCompanies: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

// ===== Context =====

const CompanyContext = createContext<CompanyContextType | null>(null);

// ===== Provider =====

async function fetchMyCompanies(): Promise<CompanyAccess[]> {
  const response = await apiClient.get('/api/users/my-companies');
  return response.data as CompanyAccess[];
}

export const CompanyProvider = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();
  const location = useLocation();
  const queryClient = useQueryClient();
  const skipCompaniesForTerminalKiosk =
    isBadgeuseTerminalPath(location.pathname) && hasTerminalToken();
  const [activeCompany, setActiveCompanyState] = useState<CompanyAccess | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companiesQuery = useQuery({
    queryKey: queryKeys.myCompanies(),
    queryFn: fetchMyCompanies,
    enabled: Boolean(user) && !skipCompaniesForTerminalKiosk,
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const accessibleCompanies = companiesQuery.data ?? [];
  const isLoading =
    Boolean(user) && companiesQuery.isLoading && !companiesQuery.data;

  useEffect(() => {
    if (companiesQuery.isError) {
      const err = companiesQuery.error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      if (import.meta.env.DEV) {
        log.error('[CompanyContext] Erreur chargement entreprises:', companiesQuery.error);
      }
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Erreur lors du chargement des entreprises',
      );
      return;
    }
    setError(null);
  }, [companiesQuery.isError, companiesQuery.error]);

  useEffect(() => {
    if (!user) {
      setActiveCompanyState(null);
      return;
    }

    const companies = companiesQuery.data;
    if (!companies?.length) {
      if (!companiesQuery.isLoading) {
        setActiveCompanyState(null);
      }
      return;
    }

    const savedCompanyId = localStorage.getItem('activeCompanyId');
    let companyToActivate: CompanyAccess | undefined;

    if (savedCompanyId) {
      companyToActivate = companies.find((c) => c.company_id === savedCompanyId);
      if (!companyToActivate) {
        localStorage.removeItem('activeCompanyId');
      }
    }

    if (!companyToActivate) {
      companyToActivate = companies.find((c) => c.is_primary);
    }

    if (!companyToActivate) {
      companyToActivate = companies[0];
    }

    setActiveCompanyState(companyToActivate);
    localStorage.setItem('activeCompanyId', companyToActivate.company_id);
  }, [user, companiesQuery.data, companiesQuery.isLoading]);

  /**
   * Change l'entreprise active
   */
  const setActiveCompany = (companyId: string) => {
    const company = accessibleCompanies.find(c => c.company_id === companyId);

    if (!company) {
      log.error('[CompanyContext] Entreprise non trouvée:', companyId);
      return;
    }

    setActiveCompanyState(company);
    localStorage.setItem('activeCompanyId', companyId);
    queryClient.clear();
    window.location.reload();
  };

  /**
   * Rafraîchir manuellement les entreprises
   */
  const refreshCompanies = async () => {
    await companiesQuery.refetch();
  };

  return (
    <CompanyContext.Provider
      value={{
        accessibleCompanies,
        activeCompany,
        setActiveCompany,
        refreshCompanies,
        isLoading,
        error
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
};

// ===== Hook =====

/**
 * Hook pour accéder au contexte d'entreprise
 *
 * @example
 * const { activeCompany, setActiveCompany, accessibleCompanies } = useCompany();
 */
export const useCompany = () => {
  const context = useContext(CompanyContext);

  if (!context) {
    throw new Error('useCompany doit être utilisé dans un CompanyProvider');
  }

  return context;
};

/** Hors CompanyProvider : null (pas d’exception), pour sidebar / switcher défensifs. */
export const useCompanyOptional = (): CompanyContextType | null => {
  return useContext(CompanyContext);
};

/** Groupements multi-entreprise (même logique que useAccessibleGroups, sans hook). */
export function computeAccessibleGroups(
  accessibleCompanies: CompanyAccess[],
): { groupId: string; groupCompanies: CompanyAccess[] }[] {
  const groupsMap = new Map<string, CompanyAccess[]>();

  accessibleCompanies.forEach((company) => {
    if (company.group_id) {
      const existing = groupsMap.get(company.group_id) || [];
      groupsMap.set(company.group_id, [...existing, company]);
    }
  });

  return Array.from(groupsMap.entries())
    .filter(([, companies]) => companies.length > 1)
    .map(([groupId, groupCompanies]) => ({ groupId, groupCompanies }));
}

// ===== Utilitaires =====

/**
 * Vérifie si l'utilisateur a accès à plusieurs entreprises
 */
export const useHasMultipleCompanies = (): boolean => {
  const { accessibleCompanies } = useCompany();
  return accessibleCompanies.length > 1;
};

/**
 * Retourne le rôle de l'utilisateur dans l'entreprise active
 */
export const useActiveCompanyRole = (): string | null => {
  const { activeCompany } = useCompany();
  return activeCompany?.role || null;
};

/**
 * Vérifie si l'utilisateur est admin dans l'entreprise active
 */
export const useIsActiveCompanyAdmin = (): boolean => {
  const { activeCompany } = useCompany();
  return activeCompany?.role === 'admin';
};

/**
 * Vérifie si l'utilisateur a accès RH dans l'entreprise active
 */
export const useHasActiveCompanyRhAccess = (): boolean => {
  const { activeCompany } = useCompany();
  return activeCompany?.role === 'admin' || activeCompany?.role === 'rh';
};

/**
 * Retourne les groupes auxquels l'utilisateur a accès (avec au moins 2 entreprises)
 * Format: { groupId: string, groupCompanies: CompanyAccess[] }
 */
export const useAccessibleGroups = (): { groupId: string; groupCompanies: CompanyAccess[] }[] => {
  const { accessibleCompanies } = useCompany();
  return computeAccessibleGroups(accessibleCompanies);
};

/**
 * Vérifie si l'utilisateur a accès à plusieurs entreprises d'un même groupe
 */
export const useHasMultiCompanyGroup = (): boolean => {
  const groups = useAccessibleGroups();
  return groups.length > 0;
};
