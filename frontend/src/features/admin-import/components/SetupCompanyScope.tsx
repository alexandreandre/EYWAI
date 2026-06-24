import { useEffect, type ReactNode } from 'react';
import { useCompany } from '@/contexts/CompanyContext';

/**
 * Aligne le contexte entreprise active (header API) sur la filiale paramétrée,
 * sans rechargement de page.
 */
export function SetupCompanyScope({
  companyId,
  children,
}: {
  companyId: string;
  children: ReactNode;
}) {
  const { setActiveCompanyInSession } = useCompany();

  useEffect(() => {
    if (!companyId) return;
    setActiveCompanyInSession(companyId);
  }, [companyId, setActiveCompanyInSession]);

  return <>{children}</>;
}
