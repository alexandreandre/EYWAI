import { describe, expect, it } from 'vitest';

import {
  getEmployeeListDateDisplay,
} from '@/features/employees/components/EmployeesTableRow';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';

const baseEmployee: EmployeeListItem = {
  id: 'emp-1',
  first_name: 'Damien',
  last_name: 'BASTER',
};

describe('getEmployeeListDateDisplay', () => {
  it('affiche la date danciennete quand elle differe de la date dentree', () => {
    expect(
      getEmployeeListDateDisplay({
        ...baseEmployee,
        hire_date: '2025-09-22',
        seniority_reference_date: '2021-04-15',
      }),
    ).toEqual({ label: 'Ancienneté', value: '15/04/2021' });
  });

  it('garde la date dentree quand aucune date danciennete distincte nexiste', () => {
    expect(
      getEmployeeListDateDisplay({
        ...baseEmployee,
        hire_date: '2025-09-22',
        seniority_reference_date: null,
      }),
    ).toEqual({ label: 'Entrée', value: '22/09/2025' });
  });
});
