import { describe, expect, it } from 'vitest';

import { CONTRACT_TYPES } from '@/constants/contracts';
import { TYPES_CONTRAT, periodesPasseesVisibles } from './EmployeeContractPeriodsCard';
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

describe('types de contrat de la carte Contrats', () => {
  it('reprend la liste de référence de la fiche, sans « Alternance » ni « Autre »', () => {
    expect([...TYPES_CONTRAT]).toEqual([...CONTRACT_TYPES]);
  });
});
