import { describe, expect, it } from 'vitest';

import { editableTypeOptionsFor, reelApresChangementDeType, typesDeSaisie } from './calendarTypes';

const valeurs = (o: { value: string }[]) => o.map((x) => x.value);

describe('editableTypeOptionsFor', () => {
  it('un jour déjà en activité partielle ne boucle pas et garde son choix', () => {
    for (const actif of [true, false]) {
      const v = valeurs(editableTypeOptionsFor('activite_partielle', actif));
      expect(v.filter((x) => x === 'activite_partielle')).toHaveLength(1);
      expect(v).toContain('travail');
    }
  });

  it('activité partielle proposée seulement si la société l’a activée', () => {
    expect(valeurs(editableTypeOptionsFor('travail', false))).not.toContain('activite_partielle');
    expect(valeurs(editableTypeOptionsFor('travail', true))).toContain('activite_partielle');
    expect(valeurs(typesDeSaisie(true))).toContain('activite_partielle');
    expect(valeurs(typesDeSaisie(false))).not.toContain('activite_partielle');
  });

  it('congé hors paie et arrêt restent proposés quand le jour les porte', () => {
    expect(valeurs(editableTypeOptionsFor('conge', true))).toEqual(expect.arrayContaining(['conge', 'activite_partielle']));
    expect(valeurs(editableTypeOptionsFor('arret_maladie'))).toContain('arret_maladie');
  });
});

describe('reelApresChangementDeType (Lyon, 17/11)', () => {
  it('un type non travaillé remet le réel à 0', () => {
    for (const t of ['activite_partielle', 'conges_payes', 'repos', 'ferie', 'absence_non_remuneree']) {
      expect(reelApresChangementDeType(t, 'travail')).toBe(0);
    }
  });
  it('le même type ne touche pas au réel ; « Travail » sans ancien type non plus', () => {
    expect(reelApresChangementDeType('activite_partielle', 'activite_partielle')).toBeUndefined();
    expect(reelApresChangementDeType('travail', 'travail')).toBeUndefined();
    expect(reelApresChangementDeType('travail', null)).toBeUndefined();
  });
  it('retour à « Travail » : le réel redevient à saisir, pas 0 (sinon absence retenue)', () => {
    expect(reelApresChangementDeType('travail', 'activite_partielle')).toBeNull();
    expect(reelApresChangementDeType('travail', 'conges_payes')).toBeNull();
  });
  it('« École » garde ses heures : temps de travail effectif', () => {
    expect(reelApresChangementDeType('ecole', 'travail')).toBeUndefined();
  });
  it('le réel saisi en même temps l’emporte (demi-journée)', () => {
    expect(reelApresChangementDeType('activite_partielle', 'travail', 3.5)).toBe(3.5);
  });
});

describe('editableTypeOptionsFor : la liste de la saisie rapide', () => {
  it('propose l’activité partielle, le repos et l’école, pas l’arrêt', () => {
    const valeurs = editableTypeOptionsFor('travail', true).map((o) => o.value);
    expect(valeurs).toEqual(expect.arrayContaining(['activite_partielle', 'repos', 'ecole']));
    expect(valeurs).not.toContain('arret_maladie');
  });
});

describe('typesDUnModeleDeSemaine', () => {
  it('un modèle de semaine ne propose que travail, week-end et repos', async () => {
    const { typesDUnModeleDeSemaine } = await import('./calendarTypes');
    expect(typesDUnModeleDeSemaine().map((o) => o.value)).toEqual(['travail', 'weekend', 'repos']);
  });

  it('un type ancien porté par un modèle reste affiché, à son libellé', async () => {
    const { typesDUnModeleDeSemaine } = await import('./calendarTypes');
    const options = typesDUnModeleDeSemaine('arret_maladie');
    expect(options.map((o) => o.value)).toContain('arret_maladie');
    expect(options.find((o) => o.value === 'arret_maladie')?.label).not.toBe('arret_maladie');
    expect(typesDUnModeleDeSemaine('travail')).toHaveLength(3);
  });
});
