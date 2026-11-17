import { describe, expect, it } from 'vitest';

import { editableTypeOptionsFor, typesDeSaisie } from './calendarTypes';

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
