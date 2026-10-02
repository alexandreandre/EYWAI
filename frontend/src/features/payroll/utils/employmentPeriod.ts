type EmploymentPeriod = {
  hire_date?: string | null;
  date_debut_execution?: string | null;
  contract_end_date?: string | null;
};

type PayrollFiche = EmploymentPeriod & {
  employment_status?: string | null;
  missing_payroll_fields?: string[] | null;
};

const STATUTS_DE_DEPART = ['parti', 'sorti', 'inactif'];
const FICHE_A_COMPLETER = 'Fiche à compléter';

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function payrollEmploymentBlockReason(
  employee: EmploymentPeriod,
  year: number,
  month: number
): string | null {
  const start = parseDate(employee.date_debut_execution ?? employee.hire_date);
  if (!start) {
    return "Date d'entrée non renseignée";
  }

  const periodStart = new Date(year, month - 1, 1);
  const periodEnd = new Date(year, month, 0);
  if (periodEnd < start) {
    return `Entrée dans l'entreprise le ${start.toLocaleDateString('fr-FR')}`;
  }

  const end = parseDate(employee.contract_end_date);
  if (end && periodStart > end) {
    return `Sortie de l'entreprise le ${end.toLocaleDateString('fr-FR')}`;
  }
  return null;
}

export function isEmployeePresentForPayrollMonth(
  employee: EmploymentPeriod,
  year: number,
  month: number
): boolean {
  return payrollEmploymentBlockReason(employee, year, month) === null;
}

/**
 * Pourquoi le bulletin du mois ne peut pas être généré : hors de la période
 * d'emploi, ou fiche incomplète (nouveau salarié créé sans son numéro de
 * sécurité sociale, sa date de naissance, son adresse ou son RIB). Même règle
 * que le serveur, dite avant de lancer la génération plutôt qu'après son échec.
 */
export function payrollGenerationBlockReason(
  employee: PayrollFiche,
  year: number,
  month: number
): string | null {
  const periode = payrollEmploymentBlockReason(employee, year, month);
  if (periode) return periode;
  const statut = (employee.employment_status || 'actif').toLowerCase();
  const manque = employee.missing_payroll_fields ?? [];
  if (manque.length > 0 && !STATUTS_DE_DEPART.includes(statut)) {
    return `${FICHE_A_COMPLETER} : ${manque.join(', ')}`;
  }
  return null;
}

/** Badge de la ligne bloquée : la cause, pas « hors période » pour une fiche incomplète. */
export function libelleDuBlocage(raison: string): string {
  return raison.startsWith(FICHE_A_COMPLETER) ? FICHE_A_COMPLETER : 'Hors période d’emploi';
}
