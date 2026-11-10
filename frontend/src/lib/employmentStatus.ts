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
 * au 24/07 doit rester visible sur juillet — retour Gaëlle 07/09, salarié 086).
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

type SalarieAvecSortie = {
  employment_status?: string | null;
  exit_last_working_day?: string | null;
  hire_date?: string | null;
};

/**
 * Dernier jour travaillé d'une sortie qui vaut encore : `null` sans sortie, ou
 * quand le salarié a été réembauché après (embauche postérieure à la sortie).
 */
export function sortieEnVigueur(employee: SalarieAvecSortie): string | null {
  const lwd = employee.exit_last_working_day?.slice(0, 10);
  if (!lwd) return null;
  const embauche = employee.hire_date?.slice(0, 10);
  if (embauche && embauche > lwd) return null;
  return lwd;
}

/**
 * Salarié à proposer dans les écrans de SAISIE d'un mois (calendrier, congés).
 * Après le mois de sa sortie, il n'y figure plus, même si son dossier de
 * départ n'est pas encore archivé (retour du 10/11) ; il reste dans les
 * bulletins et l'historique, qui ne passent pas par ici.
 */
export function estSaisissableLeMois(
  employee: SalarieAvecSortie,
  year: number,
  month: number,
): boolean {
  if (!isPresentDuringMonth(employee, year, month)) return false;
  const sortie = sortieEnVigueur(employee);
  if (!sortie) return true;
  const firstOfMonth = `${year}-${String(month).padStart(2, '0')}-01`;
  return sortie >= firstOfMonth;
}

export function filterEmployeesSaisissables<T extends SalarieAvecSortie>(
  employees: T[],
  year: number,
  month: number,
): T[] {
  return employees.filter((employee) => estSaisissableLeMois(employee, year, month));
}

/**
 * Dernier jour du contrat dans le mois : le jour de sortie s'il tombe dans le
 * mois, 0 si la sortie est passée, `null` sans sortie ou si elle est plus tard.
 */
export function dernierJourDuContratDansLeMois(
  employee: SalarieAvecSortie,
  year: number,
  month: number,
): number | null {
  const sortie = sortieEnVigueur(employee);
  if (!sortie) return null;
  const prefixe = `${year}-${String(month).padStart(2, '0')}`;
  if (sortie.startsWith(prefixe)) return Number(sortie.slice(8, 10));
  return sortie < `${prefixe}-01` ? 0 : null;
}

/** Infobulle d'une case après la sortie. */
export function libelleApresSortie(dernierJour: number, month: number): string {
  const jj = `${String(dernierJour).padStart(2, '0')}/${String(month).padStart(2, '0')}`;
  return dernierJour > 0
    ? `Après la sortie le ${jj} : rien à saisir, ce jour compte 0.`
    : 'Salarié sorti : rien à saisir ce mois-ci.';
}
