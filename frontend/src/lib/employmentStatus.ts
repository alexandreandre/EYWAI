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

/**
 * Salarié à afficher pour un MOIS donné : encore en poste, ou parti mais
 * présent sur ce mois (dernier jour travaillé dans ou après le mois affiché).
 * Sert au calendrier et à la paie du dernier mois d'un sorti (ex. un départ
 * au 24/07 doit rester visible sur juillet — retour Gaëlle 07/09, Demory).
 */
export function isPresentDuringMonth(
  employee: {
    employment_status?: string | null;
    exit_last_working_day?: string | null;
  },
  year: number,
  month: number,
): boolean {
  if (isPresentEmployee(employee.employment_status)) return true;
  const lwd = employee.exit_last_working_day;
  if (!lwd) return false;
  const firstOfMonth = `${year}-${String(month).padStart(2, '0')}-01`;
  // Dates ISO : la comparaison lexicographique est correcte.
  return lwd.slice(0, 10) >= firstOfMonth;
}

export function filterEmployeesForMonth<
  T extends {
    employment_status?: string | null;
    exit_last_working_day?: string | null;
  },
>(employees: T[], year: number, month: number): T[] {
  return employees.filter((employee) => isPresentDuringMonth(employee, year, month));
}
