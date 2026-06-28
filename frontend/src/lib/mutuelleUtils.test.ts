import { describe, expect, it } from 'vitest';

import {
  cleanMutuelleLibelle,
  formatMutuelleOptionTitle,
  isEmployeeCadre,
  normalizeEmployeeStatut,
  resolveOrganismeLabel,
  sortMutuellesForSelection,
} from '@/lib/mutuelleUtils';
import type { MutuelleType } from '@/api/mutuelleTypes';

describe('mutuelleUtils statut cadre', () => {
  it('isEmployeeCadre reconnaît cadre et forfait jour cadre', () => {
    expect(isEmployeeCadre('Cadre')).toBe(true);
    expect(isEmployeeCadre('Cadre au forfait jour')).toBe(true);
  });

  it('isEmployeeCadre exclut non-cadre', () => {
    expect(isEmployeeCadre('Non-Cadre')).toBe(false);
    expect(isEmployeeCadre('Non-Cadre au forfait jour')).toBe(false);
  });

  it('normalizeEmployeeStatut délègue à isEmployeeCadre', () => {
    expect(normalizeEmployeeStatut('Cadre au forfait jour')).toBe('cadre');
    expect(normalizeEmployeeStatut('Non-Cadre')).toBe('non_cadre');
  });
});

describe('mutuelleUtils libellés', () => {
  it('cleanMutuelleLibelle retire les montants DSN redondants', () => {
    expect(cleanMutuelleLibelle('Mutuelle (Cadre) 60.02€ / 0.00€')).toBe('(Cadre)');
  });

  it('resolveOrganismeLabel priorise la formule puis entreprise', () => {
    expect(resolveOrganismeLabel({ organisme_label: 'APICIL' }, 'Generali')).toBe('APICIL');
    expect(resolveOrganismeLabel({ organisme_label: null }, 'APICIL')).toBe('APICIL');
  });

  it('formatMutuelleOptionTitle inclut l organisme', () => {
    const m = {
      id: '1',
      libelle: 'Famille · Cadre',
      montant_salarial: 60,
      montant_patronal: 0,
      pack_couverture: 'famille',
      statut_categoriel: 'cadre',
    } as MutuelleType;
    expect(formatMutuelleOptionTitle(m, 'APICIL')).toContain('APICIL');
  });

  it('sortMutuellesForSelection trie par pack puis montant', () => {
    const items = [
      { id: 'b', libelle: 'B', montant_salarial: 50, pack_couverture: 'famille' },
      { id: 'a', libelle: 'A', montant_salarial: 10, pack_couverture: 'isole' },
    ] as MutuelleType[];
    expect(sortMutuellesForSelection(items).map((m) => m.id)).toEqual(['a', 'b']);
  });
});
