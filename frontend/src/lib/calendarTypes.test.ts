import { describe, expect, it } from 'vitest';

import {
  editableTypeOptionsFor,
  reelApresChangementDeType,
  saisieGroupeeDuJour,
  saisieGroupeeLaisseLeJour,
  typesDeSaisie,
} from './calendarTypes';

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

describe('saisieGroupeeDuJour : la saisie groupée suit la règle de la case du jour', () => {
  it('un jour d\'activité partielle repassé en Travail : réel à saisir', () => {
    expect(saisieGroupeeDuJour({ type: 'travail' }, 'activite_partielle')).toEqual({
      type: 'travail',
      heures_faites: null,
    });
  });
  it('un jour déjà en Travail : réel inchangé', () => {
    expect(saisieGroupeeDuJour({ type: 'travail' }, 'travail')).toEqual({ type: 'travail' });
  });
  it('un jour passé en congé : réel à 0', () => {
    expect(saisieGroupeeDuJour({ type: 'conges_payes' }, 'travail')).toEqual({
      type: 'conges_payes',
      heures_faites: 0,
    });
  });
  it('le réel saisi dans le panneau l\'emporte', () => {
    expect(saisieGroupeeDuJour({ type: 'travail', heures_faites: 3.5 }, 'activite_partielle')).toEqual({
      type: 'travail',
      heures_faites: 3.5,
    });
  });
  it('sans type, rien ne change', () => {
    expect(saisieGroupeeDuJour({ heures_prevues: 7 } as { type?: string; heures_prevues: number }, 'repos')).toEqual({
      heures_prevues: 7,
    });
  });
  it('réappliquer Activité partielle garde le réel d\'une demi-journée', () => {
    expect(saisieGroupeeDuJour({ type: 'activite_partielle' }, 'activite_partielle')).toEqual({
      type: 'activite_partielle',
    });
  });
  it('des heures sans type font un jour Travail', () => {
    expect(saisieGroupeeDuJour({ heures_prevues: 7, type_par_defaut: 'travail' }, 'repos')).toEqual({
      heures_prevues: 7,
      type: 'travail',
      heures_faites: null,
    });
  });
  it('sauf un jour d\'activité partielle : il reste chômé avec ses heures faites', () => {
    expect(
      saisieGroupeeDuJour({ heures_faites: 3.5, type_par_defaut: 'travail' }, 'activite_partielle'),
    ).toEqual({ heures_faites: 3.5 });
  });
});

describe('saisieGroupeeLaisseLeJour : des heures sans type ne retypent pas un congé (A5, 18/11)', () => {
  const heuresSansType = { heures_faites: 7, type_par_defaut: 'travail' };
  it.each(['conges_payes', 'ferie', 'ecole', 'rtt', 'arret_maladie', 'absence_non_remuneree'])(
    'un jour %s garde son type',
    (ancien) => {
      expect(saisieGroupeeLaisseLeJour(heuresSansType, ancien)).toBe(true);
    },
  );
  it.each([null, undefined, '', 'travail', 'weekend', 'repos', 'activite_partielle'])(
    'un jour %s reçoit les heures',
    (ancien) => {
      expect(saisieGroupeeLaisseLeJour(heuresSansType, ancien)).toBe(false);
    },
  );
  it('un type choisi dans la saisie s\'applique à tous les jours', () => {
    expect(saisieGroupeeLaisseLeJour({ type: 'travail', heures_faites: 7 }, 'conges_payes')).toBe(false);
  });
});
