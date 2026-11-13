import type { SeniorityImportRosterEmployee, SeniorityImportRowPreview } from '@/api/adminImport';

export type EditableSeniorityRow = SeniorityImportRowPreview & {
  manuallyConfirmed: boolean;
};

export function isSavableSeniorityRow(row: EditableSeniorityRow): boolean {
  return Boolean(
    row.manuallyConfirmed && row.employee_id && row.seniority_date && !row.unchanged &&
    row.seniority_date !== row.current_seniority_date,
  );
}

export function associateSeniorityRow(
  row: EditableSeniorityRow,
  employeeId: string | null,
  roster: SeniorityImportRosterEmployee[],
): EditableSeniorityRow {
  const matched = roster.find((e) => e.id === employeeId);
  const currentDate = matched?.current_seniority_date ?? null;
  const unchanged = Boolean(row.seniority_date && row.seniority_date === currentDate);
  return {
    ...row,
    employee_id: matched?.id ?? null,
    matched_name: matched ? `${matched.first_name} ${matched.last_name}`.trim() : null,
    current_seniority_date: currentDate,
    current_hire_date: matched?.current_hire_date ?? null,
    unchanged,
    manuallyConfirmed: false,
    review_status: matched && row.seniority_date ? 'warning' : 'error',
    warnings: [unchanged
      ? 'Date identique à la fiche — aucune modification nécessaire.'
      : 'Association manuelle : vérifiez l’identité et la date avant de confirmer.'],
  };
}
