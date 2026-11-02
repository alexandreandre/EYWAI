import { describe, expect, it } from 'vitest';

import type { FormulePrevoyance } from '@/api/prevoyanceFormules';
import {
  formulesPourLeStatut,
  libelleCategorie,
  lignesDeLaFormule,
  lignesModifiees,
  messageFichesAMettreAJour,
  messageFichesMisesAJour,
} from '@/features/employees/utils/formulesPrevoyance';

const TA = { libelle: 'Prévoyance TA', salarial: 0.005, patronal: 0.007, forfait_social: 0.08 };
const TB = { ...TA, libelle: 'Prévoyance TB', base: 'tranche_2' as const };
const formule = (id: string, statut_categoriel: FormulePrevoyance['statut_categoriel'], is_active = true): FormulePrevoyance => ({
  id,
  company_id: 'c1',
  libelle: id,
  statut_categoriel,
  lignes: [TA, TB],
  is_active,
});

describe('formules de prévoyance sur la fiche', () => {
  it('propose les formules de la catégorie du salarié, actives', () => {
    const toutes = [formule('cadres', 'cadre'), formule('non-cadres', 'non_cadre'), formule('tous', 'tous'), formule('vieille', 'tous', false)];
    expect(formulesPourLeStatut(toutes, true).map((f) => f.id)).toEqual(['cadres', 'tous']);
    expect(formulesPourLeStatut(toutes, false).map((f) => f.id)).toEqual(['non-cadres', 'tous']);
  });

  it('copie les lignes, numérotées, avec leur base', () => {
    const lignes = lignesDeLaFormule(formule('f1', 'cadre'));
    expect(lignes.map((l) => l.id)).toEqual(['prevoyance_1', 'prevoyance_2']);
    expect(lignes[1]).toMatchObject({ base: 'tranche_2', salarial: 0.005 });
    lignes[0].salarial = 1;
    expect(formule('f1', 'cadre').lignes[0].salarial).toBe(0.005);
  });

  it('voit des lignes modifiées depuis la formule', () => {
    const f = formule('f1', 'cadre');
    expect(lignesModifiees(lignesDeLaFormule(f), f)).toBe(false);
    expect(lignesModifiees([{ ...TA, id: 'x', base: 'brut_plafonne' }, { ...TB, id: 'y' }], f)).toBe(false);
    expect(lignesModifiees([{ ...TA, id: 'x', patronal: 0.008 }, { ...TB, id: 'y' }], f)).toBe(true);
    expect(lignesModifiees([{ ...TA, id: 'x' }], f)).toBe(true);
  });

  it('accorde les messages au nombre de fiches', () => {
    expect(messageFichesAMettreAJour(1)).toBe('1 fiche a encore les anciennes lignes de cette formule.');
    expect(messageFichesAMettreAJour(3)).toBe('3 fiches ont encore les anciennes lignes de cette formule.');
    expect(messageFichesMisesAJour(0)).toBe('Aucune fiche à mettre à jour.');
    expect(messageFichesMisesAJour(1)).toBe('1 fiche mise à jour : ses brouillons sont à recalculer.');
    expect(messageFichesMisesAJour(4)).toBe('4 fiches mises à jour : leurs brouillons sont à recalculer.');
  });

  it('nomme la catégorie', () => {
    expect(libelleCategorie('cadre')).toBe('Cadres');
    expect(libelleCategorie('non_cadre')).toBe('Non-cadres');
    expect(libelleCategorie('tous')).toBe('Tous les salariés');
  });
});
