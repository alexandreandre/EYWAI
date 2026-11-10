import { describe, expect, it } from 'vitest';

import {
  JOURS_MODELE_SEMAINE,
  cleModeleDuJour,
  jourPrevuDuModele,
  semaineDuModele,
  valeurModelePourLeJour,
} from './weekTemplateDays';

describe('modèle de semaine type', () => {
  it('propose les sept jours, du lundi au dimanche', () => {
    expect(JOURS_MODELE_SEMAINE.map((j) => j.label)).toEqual([
      'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche',
    ]);
  });

  it('range le dimanche sous la clé 7 (getDay() = 0)', () => {
    expect(cleModeleDuJour(0)).toBe(7);
    expect(cleModeleDuJour(6)).toBe(6);
    expect(cleModeleDuJour(3)).toBe(3);
  });

  it('laisse le week-end tel quel tant que le modèle y est vide', () => {
    expect(valeurModelePourLeJour({ 1: '7' }, 6)).toBeUndefined();
    expect(valeurModelePourLeJour({ 6: '' }, 6)).toBeUndefined();
    expect(valeurModelePourLeJour({ 6: '4' }, 6)).toBe('4');
    expect(valeurModelePourLeJour({ 7: '3' }, 0)).toBe('3');
  });

  it('applique toujours un jour de semaine, même vide', () => {
    expect(valeurModelePourLeJour({}, 2)).toBe('');
  });
});

describe('jour prévu posé par le modèle (retour du 10/11)', () => {
  it('une case vide vaut 0 h, jour non travaillé', () => {
    expect(jourPrevuDuModele('', false)).toEqual({ type: 'weekend', heures_prevues: 0 });
    expect(jourPrevuDuModele('  ', false)).toEqual({ type: 'weekend', heures_prevues: 0 });
    expect(jourPrevuDuModele('0', false)).toEqual({ type: 'weekend', heures_prevues: 0 });
  });

  it('reprend exactement les heures saisies', () => {
    expect(jourPrevuDuModele('7', false)).toEqual({ type: 'travail', heures_prevues: 7 });
    expect(jourPrevuDuModele('3,5', false)).toEqual({ type: 'travail', heures_prevues: 3.5 });
  });

  it('au forfait jours, un jour coché vaut 1, sinon 0', () => {
    expect(jourPrevuDuModele('1', true)).toEqual({ type: 'travail', heures_prevues: 1 });
    expect(jourPrevuDuModele('', true)).toEqual({ type: 'weekend', heures_prevues: 0 });
  });
});

describe('semaine du modèle enregistré (retour du 10/11)', () => {
  it('un jour absent du modèle vaut 0 h, jamais 8 h', () => {
    // « FEMME MENAGE » (MAJI) : mercredi et samedi 3 h, rien d'autre.
    const semaine = semaineDuModele({ 3: '3', 6: '3' });
    expect(semaine.monday).toEqual({ type: 'weekend', hours: 0 });
    expect(semaine.wednesday).toEqual({ type: 'travail', hours: 3 });
    expect(semaine.saturday).toEqual({ type: 'travail', hours: 3 });
    expect(Object.values(semaine).reduce((s, j) => s + j.hours, 0)).toBe(6);
  });

  it('un modèle à 7 h/jour reste à 7 h', () => {
    const semaine = semaineDuModele({ 1: '7', 2: '7', 3: '7', 4: '7', 5: '7', 6: '0', 7: '0' });
    expect(semaine.friday).toEqual({ type: 'travail', hours: 7 });
    expect(semaine.sunday).toEqual({ type: 'weekend', hours: 0 });
  });
});
