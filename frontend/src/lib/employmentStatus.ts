/** Statuts d'emploi qui ne doivent plus figurer au calendrier ni dans les actions. */
const LEFT_EMPLOYMENT_STATUSES = new Set(['parti', 'inactif', 'sorti']);

/** Salarié encore en poste (actif, onboarding, en sortie). */
export function isPresentEmployee(status?: string | null): boolean {
  const normalized = (status || 'actif').trim().toLowerCase();
  return !LEFT_EMPLOYMENT_STATUSES.has(normalized);
}

export function filterPresentEmployees<T extends { employment_status?: string | null }>(
  employees: T[],
): T[] {
  return employees.filter((employee) => isPresentEmployee(employee.employment_status));
}
