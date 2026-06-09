import type { EmployeeDetailDocumentsRhEmployee } from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';

const DOC_TYPE_BY_CONTRACT: Record<string, string> = {
  cdi: 'cdi',
  cdd: 'cdd',
  stage: 'convention_stage',
  alternance: 'contrat_alternance',
  apprentissage: 'contrat_alternance',
};

export function resolveGeneratedContractDocType(contractType?: string | null): string {
  if (!contractType) return '';
  const normalized = contractType.trim().toLowerCase();
  if (normalized.includes('cdd')) return 'cdd';
  if (normalized.includes('stage')) return 'convention_stage';
  if (normalized.includes('altern') || normalized.includes('apprent')) {
    return 'contrat_alternance';
  }
  if (normalized.includes('cdi')) return 'cdi';
  return DOC_TYPE_BY_CONTRACT[normalized] ?? '';
}

function hasSalaryValue(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'number') return Number.isFinite(value) && value > 0;
  if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>;
    const raw = record.valeur ?? record.montant ?? record.amount;
    if (typeof raw === 'number') return Number.isFinite(raw) && raw > 0;
    if (typeof raw === 'string') {
      const parsed = Number(raw.replace(',', '.'));
      return Number.isFinite(parsed) && parsed > 0;
    }
  }
  return false;
}

function hasWeeklyHours(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'number') return Number.isFinite(value) && value > 0;
  if (typeof value === 'string') {
    const parsed = Number(value.replace(',', '.'));
    return Number.isFinite(parsed) && parsed > 0;
  }
  return false;
}

export function getMissingContractGenerationFields(
  employee: EmployeeDetailDocumentsRhEmployee,
): string[] {
  const missing: string[] = [];
  if (!employee.job_title?.trim() && !employee.poste?.trim()) {
    missing.push('poste');
  }
  if (!employee.contract_type?.trim()) {
    missing.push('type de contrat');
  }
  if (!employee.hire_date?.trim()) {
    missing.push("date d'entrée");
  }
  if (!hasSalaryValue(employee.salaire_de_base)) {
    missing.push('salaire de base');
  }
  if (!hasWeeklyHours(employee.duree_hebdomadaire ?? employee.weekly_hours)) {
    missing.push('durée hebdomadaire');
  }
  return missing;
}
