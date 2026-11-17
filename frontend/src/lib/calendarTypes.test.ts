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
    for (const t of ['activite_partielle', 'conges_payes', 'repos', 'ferie', 'absence_non_remuneree', 'ecole']) {
      expect(reelApresChangementDeType(t, 'travail')).toBe(0);
    }
  });
  it('« Travail » et le même type ne touchent pas au réel', () => {
    expect(reelApresChangementDeType('travail', 'activite_partielle')).toBeUndefined();
    expect(reelApresChangementDeType('activite_partielle', 'activite_partielle')).toBeUndefined();
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
