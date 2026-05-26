import { useCompanyOptional } from '@/contexts/CompanyContext';

/** ID entreprise active pour les queryKey (undefined si super-admin sans entreprise). */
export function useActiveCompanyId(): string | undefined {
  return useCompanyOptional()?.activeCompany?.company_id;
}
