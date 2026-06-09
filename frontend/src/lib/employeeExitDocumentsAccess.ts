export interface EmployeeExitDocumentsContext {
  employment_status?: string | null;
  exit_last_working_day?: string | null;
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const parsed = new Date(value.slice(0, 10));
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function rhCanViewEmployeeDocuments(
  employee: EmployeeExitDocumentsContext,
  referenceDate: Date = new Date(),
): boolean {
  const status = (employee.employment_status || 'actif').toLowerCase();
  if (status !== 'en_sortie' && status !== 'parti') {
    return true;
  }

  const lastDay = parseDate(employee.exit_last_working_day);
  if (!lastDay) {
    return true;
  }

  return startOfDay(referenceDate) <= startOfDay(lastDay);
}

export function rhEmployeeDocumentsAccessMessage(
  employee: EmployeeExitDocumentsContext,
): string | null {
  const status = (employee.employment_status || 'actif').toLowerCase();
  if (status !== 'en_sortie' && status !== 'parti') {
    return null;
  }

  const lastDay = parseDate(employee.exit_last_working_day);
  if (!lastDay) {
    return (
      'Ce collaborateur est en cours de départ. ' +
      'Vous pouvez consulter l’ensemble de son dossier documents.'
    );
  }

  const formatted = lastDay.toLocaleDateString('fr-FR');
  if (rhCanViewEmployeeDocuments(employee)) {
    return (
      `Ce collaborateur est en cours de départ. ` +
      `Vous pouvez consulter son dossier documents jusqu’au ${formatted} inclus.`
    );
  }

  return (
    `Le dernier jour travaillé de ce collaborateur était le ${formatted}. ` +
    'Le dossier reste consultable à des fins d’archivage RH.'
  );
}

export function employeeDocumentsPath(employeeId: string): string {
  return `/employees/${employeeId}?tab=documents`;
}
