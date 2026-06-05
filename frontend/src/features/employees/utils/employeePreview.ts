import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import type { Employee } from '@/features/employee-detail/types';

export type EmployeeDetailLocationState = {
  employeePreview?: EmployeeListItem;
};

/** Données minimales pour afficher l'en-tête pendant le chargement du détail complet. */
export function employeePlaceholderFromList(item: EmployeeListItem): Employee {
  return {
    id: item.id,
    first_name: item.first_name,
    last_name: item.last_name,
    job_title: item.job_title ?? '',
    contract_type: item.contract_type ?? '',
    statut: '',
    hire_date: item.hire_date ?? '',
    employment_status: item.employment_status ?? 'actif',
  };
}
