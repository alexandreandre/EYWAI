/** Étapes réelles émises par le backend lors de la purge des salariés. */
export const PURGE_EMPLOYEE_STEPS = [
  'preparation',
  'storage',
  'data',
  'account',
  'finalize',
] as const;

export type PurgeEmployeeStep = (typeof PURGE_EMPLOYEE_STEPS)[number];

export type PurgeEmployeesStreamEvent =
  | {
      event: 'started';
      company_id: string;
      company_name: string;
      total: number;
    }
  | {
      event: 'employee_started' | 'employee_done' | 'employee_failed';
      index: number;
      total: number;
      employee_id: string;
      employee_name: string;
      error?: string;
    }
  | {
      event: 'step';
      step: PurgeEmployeeStep;
      label: string;
      index: number;
      total: number;
      employee_id: string;
      employee_name: string;
    }
  | {
      event: 'completed';
      result: import('@/api/adminCompanies').DeleteAllCompanyEmployeesResult;
    }
  | { event: 'error'; message: string };

const STEPS_PER_EMPLOYEE = PURGE_EMPLOYEE_STEPS.length;

function stepIndex(step: PurgeEmployeeStep): number {
  const idx = PURGE_EMPLOYEE_STEPS.indexOf(step);
  return idx >= 0 ? idx : 0;
}

/** Progression 0–100 alignée sur salariés × étapes réelles. */
export function purgeEmployeesProgressPercent(
  totalEmployees: number,
  employeeIndex: number,
  step?: PurgeEmployeeStep,
  employeeDone = false,
): number {
  if (totalEmployees <= 0) return 100;
  const totalUnits = totalEmployees * STEPS_PER_EMPLOYEE;
  let completedUnits = (employeeIndex - 1) * STEPS_PER_EMPLOYEE;
  if (employeeDone) {
    completedUnits = employeeIndex * STEPS_PER_EMPLOYEE;
  } else if (step) {
    completedUnits += stepIndex(step) + 1;
  }
  return Math.min(100, Math.round((completedUnits / totalUnits) * 100));
}

export function purgeEmployeesEventLabel(event: PurgeEmployeesStreamEvent): string | null {
  switch (event.event) {
    case 'started':
      return `${event.total} salarié${event.total !== 1 ? 's' : ''} à traiter`;
    case 'employee_started':
      return `Salarié ${event.index}/${event.total} — ${event.employee_name}`;
    case 'step':
      return event.label;
    case 'employee_done':
      return `${event.employee_name} — supprimé`;
    case 'employee_failed':
      return `${event.employee_name} — échec : ${event.error ?? 'erreur inconnue'}`;
    case 'completed':
      return 'Purge terminée';
    case 'error':
      return event.message;
    default:
      return null;
  }
}
