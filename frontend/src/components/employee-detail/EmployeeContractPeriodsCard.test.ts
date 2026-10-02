import { describe, expect, it } from 'vitest';

import { periodesPasseesVisibles } from './EmployeeContractPeriodsCard';
import type { ContractPeriod } from '@/api/contractPeriods';

const periode = (debut: string, fin: string): ContractPeriod => ({
  id: debut,
  employee_id: 'e',
  company_id: 'c',
  contract_type: 'CDD',
  date_debut: debut,
  date_fin: fin,
});

describe('periodesPasseesVisibles', () => {
  it('masque la ligne qui répète le contrat de la fiche', () => {
    const lignes = periodesPasseesVisibles(
      [periode('2026-09-01', '2026-12-31'), periode('2026-01-01', '2026-05-31')],
      '2026-09-01',
      '2026-12-31',
    );
    expect(lignes.map((l) => l.date_debut)).toEqual(['2026-01-01']);
  });
});
