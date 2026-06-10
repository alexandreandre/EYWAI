import type { NavigateFunction } from 'react-router-dom';

export const JEI_COMPANY_PAYROLL_PATH = '/company?tab=paie&section=jei';

export function buildJeiCompanyPayrollPath(): string {
  return JEI_COMPANY_PAYROLL_PATH;
}

export function openJeiSettingsForCompany(
  navigate: NavigateFunction,
  setActiveCompany: (companyId: string) => void,
  companyId: string,
): void {
  setActiveCompany(companyId);
  navigate(buildJeiCompanyPayrollPath());
}
