import { describe, expect, it } from 'vitest';

import type { Employee } from '@/features/employee-detail/types';

import { employeeProfileEditSchema } from './employeeProfileEditSchema';
import { buildDefaultValues } from './employeeProfileFormUtils';

function fiche(champs: Record<string, unknown>): Employee {
  return {
    id: 'e1',
    first_name: 'Jeanne',
    last_name: 'Essai',
    statut: 'Non-Cadre',
    contract_type: 'CDI',
    salaire_de_base: { valeur: 1990 },
    salary_payment_method: 'cheque',
    specificites_paie: {},
    ...champs,
  } as unknown as Employee;
}

function erreursClassification(valeurs: unknown): string[] {
  const r = employeeProfileEditSchema.safeParse(valeurs);
  return r.success
    ? []
    : r.error.issues
        .filter((i) => i.path[0] === 'classification_conventionnelle')
        .map((i) => `${i.path.join('.')}: ${i.message}`);
}

describe('modifier une fiche sans classification (retour du 03/11)', () => {
  it('sans convention : la fiche s’enregistre, aucune classification demandée', () => {
    expect(erreursClassification(buildDefaultValues(fiche({ collective_agreement_id: null })))).toEqual([]);
  });

  it('avec une convention : la liste reste vide sans bloquer l’enregistrement des autres champs', () => {
    expect(
      erreursClassification(buildDefaultValues(fiche({ collective_agreement_id: 'cc-plasturgie' }))),
    ).toEqual([]);
  });

  it('une classification choisie dans la grille passe', () => {
    const valeurs = buildDefaultValues(fiche({ collective_agreement_id: 'cc-plasturgie' }));
    valeurs.classification_conventionnelle = { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 700 };
    expect(erreursClassification(valeurs)).toEqual([]);
  });
});
