type EmploymentPeriod = {
  hire_date?: string | null;
  date_debut_execution?: string | null;
  contract_end_date?: string | null;
};

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
