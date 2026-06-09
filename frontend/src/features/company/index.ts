export { CompanyPageHeader } from './components/CompanyPageHeader';
export { CompanyComplianceBand } from './components/CompanyComplianceBand';
export { CompanyOverviewAlerts, CC_EMPLOYEES_CODE } from './components/CompanyOverviewAlerts';
export { CompanyRhStatsBand } from './components/CompanyRhStatsBand';
export { CompanyPilotageSection } from './components/CompanyPilotageSection';
export { CompanyIdentityTab } from './components/CompanyIdentityTab';
export { CompanyPayrollTab } from './components/CompanyPayrollTab';
export { CompanyGroupPositionBand } from './components/CompanyGroupPositionBand';
export { default as MutuelleManagementTab } from './components/MutuelleManagementTab';
export { default as DocumentLibraryTab } from './components/DocumentLibraryTab';
export { useCompanyPeriod } from './hooks/useCompanyPeriod';
export {
  computePeriodPayroll,
  type PeriodPayrollSnapshot,
} from './lib/companyPeriodKpis';
export {
  COMPANY_PAGE_TABS,
  DEFAULT_COMPANY_PAGE_TAB,
  type CompanyPageTab,
  tabFromHash,
  tabFromSearchParam,
  formatCollectiveAgreementLabel,
} from './lib/companyPageTabs';
