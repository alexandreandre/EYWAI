import type { CompanySetupStatus } from '@/api/adminImport';

export type CompanySetupTab =
  | 'dsn'
  | 'seniority'
  | 'payroll-export'
  | 'cp'
  | 'params'
  | 'planning';

export type CompanySetupStepDef = {
  id: string;
  tab: CompanySetupTab;
  label: string;
  shortLabel: string;
  description: string;
};

export const COMPANY_SETUP_STEPS: CompanySetupStepDef[] = [
  {
    id: 'dsn',
    tab: 'dsn',
    label: 'Import DSN',
    shortLabel: 'DSN',
    description: 'Structure entreprise, salariés, cumuls et historique',
  },
  {
    id: 'seniority',
    tab: 'seniority',
    label: 'Dates d\'ancienneté',
    shortLabel: 'Ancienneté',
    description:
      'Import Excel des dates de reprise (prime d\'ancienneté, rachat d\'entreprise)',
  },
  {
    id: 'payroll-export',
    tab: 'payroll-export',
    label: 'Enrichissement salariés',
    shortLabel: 'Salariés',
    description:
      'Export paie Quadra/Cegid : contacts, RIB, temps partiel, moyen de paiement, BOETH',
  },
  {
    id: 'cp',
    tab: 'cp',
    label: 'Soldes CP',
    shortLabel: 'CP',
    description: 'Soldes d’ouverture depuis bulletins PDF',
  },
  {
    id: 'params',
    tab: 'params',
    label: 'Paramètres',
    shortLabel: 'Paramètres',
    description: 'Congés, RTT, JEI, OETH et paie',
  },
  {
    id: 'planning',
    tab: 'planning',
    label: 'Import Calendrier',
    shortLabel: 'Calendrier',
    description: 'Calendriers prévus — mois, année ou plage (optionnel)',
  },
];

const EMPLOYEE_DEPENDENT_STEPS = new Set(['seniority', 'payroll-export', 'cp', 'planning']);

export function isCompanySetupEmployeesEmpty(
  status: CompanySetupStatus | undefined,
): boolean {
  return (status?.blocks.employees.total ?? 0) === 0;
}

export function isCompanySetupStepBlocked(
  stepId: string,
  status: CompanySetupStatus | undefined,
): boolean {
  return isCompanySetupEmployeesEmpty(status) && EMPLOYEE_DEPENDENT_STEPS.has(stepId);
}

export function formatEmployeesSetupSummary(
  employees: CompanySetupStatus['blocks']['employees'],
): string {
  if (employees.total === 0) return 'Aucun salarié';
  return `${employees.profile_complete_pct}% fiches complètes`;
}

export function isCompanySetupStepDone(
  stepId: string,
  status: CompanySetupStatus | undefined,
): boolean {
  if (!status || isCompanySetupStepBlocked(stepId, status)) return false;
  const b = status.blocks;
  switch (stepId) {
    case 'dsn':
      return b.dsn.complete && b.employees.total > 0;
    case 'payroll-export':
      return (
        b.employees.total > 0
        && b.employees.profile_complete_pct >= 95
        && b.employees.missing_rib_count === 0
      );
    case 'cp':
      return b.cp.adjusted_count > 0 && b.employees.total > 0;
    case 'params':
      return b.leave_settings.configured && b.payroll_params.taux_at_mp != null;
    case 'planning':
      return b.planning.months_with_calendar >= 6;
    default:
      return false;
  }
}

export type CompanySetupStepState = 'done' | 'blocked' | 'pending';

export function getCompanySetupStepState(
  stepId: string,
  status: CompanySetupStatus | undefined,
): CompanySetupStepState {
  if (isCompanySetupStepBlocked(stepId, status)) return 'blocked';
  return isCompanySetupStepDone(stepId, status) ? 'done' : 'pending';
}

export function getCompanySetupStepSummaryLine(
  stepId: string,
  status: CompanySetupStatus,
): string {
  const b = status.blocks;
  switch (stepId) {
    case 'dsn': {
      if (b.employees.total === 0) {
        return b.dsn.covered_months > 0
          ? `${b.dsn.covered_months} mois importé(s) — aucun salarié actif`
          : 'Aucun import DSN';
      }
      const gaps = b.dsn.gaps?.length ?? 0;
      const base = `${b.dsn.applicable_covered_months}/${b.dsn.applicable_months} mois couverts · ${b.employees.total} salarié(s)`;
      return gaps > 0 ? `${base} · ${gaps} mois manquant(s)` : base;
    }
    case 'seniority':
      if (b.employees.total === 0) return 'En attente de l’import DSN';
      return 'Import Excel NOM / PRENOM / Date ancienneté (reprise / prime)';
    case 'payroll-export':
      if (b.employees.total === 0) return 'En attente de l’import DSN';
      return `${b.employees.profile_complete_pct}% fiches complètes · ${b.employees.missing_rib_count} RIB manquant(s)`;
    case 'cp':
      if (b.employees.total === 0) return 'En attente de l’import DSN';
      return `${b.cp.adjusted_count} solde(s) CP sur ${b.cp.total_active} salarié(s) actif(s)`;
    case 'params': {
      const items: string[] = [];
      items.push(b.leave_settings.configured ? 'Congés / RTT' : 'Congés / RTT à configurer');
      items.push(b.payroll_params.taux_at_mp != null ? 'AT/MP renseigné' : 'AT/MP manquant');
      items.push(
        b.payroll_params.paie_jour_de_fin != null ? 'Calendrier paie OK' : 'Calendrier paie manquant',
      );
      if (b.modulation.configured) items.push('Modulation');
      if (b.jei.configured) items.push('JEI');
      if (b.oeth.configured) items.push('OETH');
      return items.join(' · ');
    }
    case 'planning':
      if (b.employees.total === 0) return 'En attente de l’import DSN';
      return `${b.planning.months_with_calendar} mois avec calendrier importé (optionnel)`;
    default:
      return '';
  }
}
