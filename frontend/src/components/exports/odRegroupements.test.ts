import { describe, expect, it } from 'vitest';

import type { AccountingMapping } from '@/api/exports';

import { regroupementsProposes } from './odRegroupements';

function mapping(champs: Partial<AccountingMapping>): AccountingMapping {
  return {
    id: 'm1',
    rubrique_code: 'salaire_brut',
    rubrique_libelle: 'Salaire brut',
    compte_comptable: '641100',
    journal: 'OD',
    sens: 'debit',
    type_rubrique: 'brut',
    is_active: true,
    is_global_default: false,
    ...champs,
  };
}

describe('regroupementsProposes', () => {
  it('« Global » est toujours proposé ; « Par établissement » ne l’est plus', () => {
    const valeurs = regroupementsProposes([]).map((r) => r.value);
    expect(valeurs).toEqual(['global']);
    expect(regroupementsProposes(undefined).map((r) => r.value)).toEqual(['global']);
  });

  it('« Par analytique » n’agit que si le salaire brut porte un code analytique', () => {
    expect(regroupementsProposes([mapping({ analytique: null })]).map((r) => r.value)).toEqual([
      'global',
    ]);
    expect(regroupementsProposes([mapping({ analytique: '  ' })]).map((r) => r.value)).toEqual([
      'global',
    ]);
    expect(regroupementsProposes([mapping({ analytique: 'PROD' })]).map((r) => r.value)).toEqual([
      'global',
      'par_analytique',
    ]);
  });

  it('un code sur une autre rubrique ne suffit pas', () => {
    const autre = mapping({ rubrique_code: 'net_a_payer', analytique: 'PROD' });
    expect(regroupementsProposes([autre]).map((r) => r.value)).toEqual(['global']);
  });

  it('le réglage de la société prime sur le réglage par défaut', () => {
    const parDefaut = mapping({ analytique: 'PROD', is_global_default: true });
    const societe = mapping({ analytique: null, is_global_default: false });
    expect(regroupementsProposes([parDefaut, societe]).map((r) => r.value)).toEqual(['global']);
  });

  it('un réglage inactif est ignoré', () => {
    expect(
      regroupementsProposes([mapping({ analytique: 'PROD', is_active: false })]).map((r) => r.value),
    ).toEqual(['global']);
  });
});
