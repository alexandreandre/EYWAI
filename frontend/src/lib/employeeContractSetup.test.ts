import { describe, expect, it } from 'vitest';
import {
  getMissingContractGenerationFields,
  resolveGeneratedContractDocType,
} from '@/lib/employeeContractSetup';

describe('employeeContractSetup', () => {
  it('resolveGeneratedContractDocType maps common contract labels', () => {
    expect(resolveGeneratedContractDocType('CDI')).toBe('cdi');
    expect(resolveGeneratedContractDocType('CDD')).toBe('cdd');
    expect(resolveGeneratedContractDocType('Convention de stage')).toBe('convention_stage');
  });

  it('getMissingContractGenerationFields lists incomplete profile data', () => {
    const missing = getMissingContractGenerationFields({
      id: 'e1',
      first_name: 'Jean',
      last_name: 'Dupont',
      job_title: 'Comptable',
      contract_type: 'CDI',
      hire_date: '2024-01-01',
      salaire_de_base: { valeur: 2800 },
      duree_hebdomadaire: 35,
    });
    expect(missing).toEqual([]);
  });
});
