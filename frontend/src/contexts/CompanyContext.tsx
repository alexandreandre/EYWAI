/**
 * CompanyContext : Gestion du contexte d'entreprise active pour multi-entreprises
 *
 * Ce contexte gère :
 * - Les entreprises accessibles par l'utilisateur
 * - L'entreprise active (celle sur laquelle l'utilisateur travaille)
 * - La persistance du choix dans localStorage
 * - Le header X-Active-Company envoyé au backend
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import apiClient from '../api/apiClient';

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

interface CompanyContextType {
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

export const CompanyProvider = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();
  const [accessibleCompanies, setAccessibleCompanies] = useState<CompanyAccess[]>([]);
  const [activeCompany, setActiveCompanyState] = useState<CompanyAccess | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Charge les entreprises accessibles depuis l'API
   */
  const loadCompanies = async () => {
    console.log('%c[CompanyContext] 🚀 loadCompanies() appelé', 'background: teal; color: white; font-weight: bold');

    if (!user) {
      console.log('%c[CompanyContext] ❌ Pas d\'utilisateur - Arrêt', 'color: red');
      setIsLoading(false);
      return;
    }

    console.log('%c[CompanyContext] ✅ Utilisateur présent:', 'color: teal', user.email);

    try {
      setIsLoading(true);
      setError(null);

      console.log('%c[CompanyContext] 📡 Appel API /api/users/my-companies...', 'color: teal');

      const response = await apiClient.get('/api/users/my-companies');
      const companies = response.data as CompanyAccess[];

      console.log(`%c[CompanyContext] ✅ ${companies.length} entreprise(s) trouvée(s)`, 'color: green; font-weight: bold');
      console.log('%c[CompanyContext] Détail des entreprises:', 'color: teal', companies);

      setAccessibleCompanies(companies);

      // Déterminer l'entreprise active
      if (companies.length > 0) {
        console.log('%c[CompanyContext] 🔍 Détermination de l\'entreprise active...', 'color: teal');

        // 1. Essayer de récupérer depuis localStorage
        const savedCompanyId = localStorage.getItem('activeCompanyId');
        console.log('%c[CompanyContext] localStorage activeCompanyId:', 'color: teal', savedCompanyId);

        let companyToActivate: CompanyAccess | undefined;

        if (savedCompanyId) {
          companyToActivate = companies.find(c => c.company_id === savedCompanyId);
          if (companyToActivate) {
            console.log('%c[CompanyContext] ✅ Entreprise active restaurée depuis localStorage:', 'color: green', companyToActivate.company_name);
          } else {
            console.log('%c[CompanyContext] ⚠️ ID du localStorage non trouvé dans les entreprises accessibles', 'color: orange');
            console.log('%c[CompanyContext] 🧹 Nettoyage du localStorage (entreprise non accessible)', 'color: orange');
            localStorage.removeItem('activeCompanyId');
          }
        }

        // 2. Sinon, utiliser l'entreprise primaire
        if (!companyToActivate) {
          console.log('%c[CompanyContext] 🔍 Recherche de l\'entreprise primaire...', 'color: teal');
          companyToActivate = companies.find(c => c.is_primary);
          if (companyToActivate) {
            console.log('%c[CompanyContext] ✅ Entreprise primaire utilisée:', 'color: green', companyToActivate.company_name);
          } else {
            console.log('%c[CompanyContext] ⚠️ Aucune entreprise primaire trouvée', 'color: orange');
          }
        }

        // 3. Sinon, utiliser la première de la liste
        if (!companyToActivate) {
          console.log('%c[CompanyContext] 🔍 Utilisation de la première entreprise de la liste...', 'color: teal');
          companyToActivate = companies[0];
          console.log('%c[CompanyContext] ✅ Première entreprise utilisée:', 'color: green', companyToActivate.company_name);
        }

        // Activer l'entreprise
        console.log('%c[CompanyContext] 🎯 Activation de l\'entreprise:', 'color: teal', companyToActivate);
        setActiveCompanyState(companyToActivate);
        localStorage.setItem('activeCompanyId', companyToActivate.company_id);
        console.log('%c[CompanyContext] ✅ Entreprise sauvegardée dans localStorage:', 'color: green', companyToActivate.company_id);
        // NOTE: Le header X-Active-Company sera automatiquement défini par l'intercepteur apiClient
        // en lisant localStorage à chaque requête
      } else {
        console.warn('%c[CompanyContext] ⚠️ Aucune entreprise accessible', 'color: orange');
        setActiveCompanyState(null);
      }

    } catch (err: any) {
      console.error('%c[CompanyContext] 💥 ERREUR lors du chargement des entreprises:', 'background: red; color: white; font-weight: bold', err);
      console.error('%c[CompanyContext] Détail de l\'erreur:', 'color: red', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      });
      setError(err.response?.data?.detail || 'Erreur lors du chargement des entreprises');
    } finally {
      console.log('%c[CompanyContext] 🏁 Fin du chargement (isLoading = false)', 'color: teal');
      setIsLoading(false);
    }
  };

  /**
   * Initialisation au montage ou quand l'utilisateur change
   */
  useEffect(() => {
    console.log('%c[CompanyContext] ⚡ useEffect déclenché', 'background: teal; color: white; font-weight: bold');
    console.log('%c[CompanyContext] user:', 'color: teal', user);

    // Ne charger les entreprises que pour les utilisateurs non-super-admin
    const isSuperAdmin = user?.is_super_admin === true || user?.role === 'super_admin';
    console.log('%c[CompanyContext] isSuperAdmin:', 'color: teal', isSuperAdmin);

    if (user && !isSuperAdmin) {
      console.log('%c[CompanyContext] 🚀 Démarrage du chargement des entreprises...', 'color: teal; font-weight: bold');

      // NOTE: Le header X-Active-Company sera automatiquement défini par l'intercepteur apiClient
      // en lisant localStorage à chaque requête. Pas besoin de le définir ici.

      // Utiliser un timeout pour éviter de bloquer indéfiniment
      const timer = setTimeout(() => {
        if (isLoading) {
          console.warn('%c[CompanyContext] ⏰ TIMEOUT - arrêt forcé du chargement', 'background: orange; color: white; font-weight: bold');
          setIsLoading(false);
          setError('Timeout lors du chargement des entreprises');
        }
      }, 10000); // 10 secondes max

      loadCompanies().finally(() => {
        console.log('%c[CompanyContext] 🏁 loadCompanies() terminé - nettoyage du timer', 'color: teal');
        clearTimeout(timer);
      });

      return () => {
        console.log('%c[CompanyContext] 🧹 Cleanup - annulation du timer', 'color: teal');
        clearTimeout(timer);
      };
    } else if (isSuperAdmin) {
      // Super admins peuvent ne pas avoir d'entreprise par défaut
      console.log('%c[CompanyContext] 👑 Super admin - pas de chargement automatique', 'color: gold');
      setIsLoading(false);
    } else {
      console.log('%c[CompanyContext] ⚠️ Pas d\'utilisateur - pas de chargement', 'color: orange');
      setIsLoading(false);
    }
  }, [user]);

  /**
   * Change l'entreprise active
   */
  const setActiveCompany = (companyId: string) => {
    const company = accessibleCompanies.find(c => c.company_id === companyId);

    if (!company) {
      console.error('[CompanyContext] Entreprise non trouvée:', companyId);
      return;
    }

    console.log('[CompanyContext] Changement d\'entreprise active:', company.company_name);

    // Mettre à jour l'état
    setActiveCompanyState(company);

    // Sauvegarder dans localStorage
    localStorage.setItem('activeCompanyId', companyId);
    console.log('[CompanyContext] ✅ Nouvelle entreprise sauvegardée dans localStorage:', companyId);

    // NOTE: Le header X-Active-Company sera automatiquement mis à jour par l'intercepteur apiClient
    // lors du prochain reload de la page

    // Recharger la page pour rafraîchir toutes les données avec la nouvelle entreprise
    window.location.reload();
  };

  /**
   * Rafraîchir manuellement les entreprises
   */
  const refreshCompanies = async () => {
    await loadCompanies();
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

  // Grouper les entreprises par group_id
  const groupsMap = new Map<string, CompanyAccess[]>();

  accessibleCompanies.forEach(company => {
    if (company.group_id) {
      const existing = groupsMap.get(company.group_id) || [];
      groupsMap.set(company.group_id, [...existing, company]);
    }
  });

  // Retourner uniquement les groupes avec au moins 2 entreprises
  return Array.from(groupsMap.entries())
    .filter(([, companies]) => companies.length > 1)
    .map(([groupId, groupCompanies]) => ({ groupId, groupCompanies }));
};

/**
 * Vérifie si l'utilisateur a accès à plusieurs entreprises d'un même groupe
 */
export const useHasMultiCompanyGroup = (): boolean => {
  const groups = useAccessibleGroups();
  return groups.length > 0;
};
