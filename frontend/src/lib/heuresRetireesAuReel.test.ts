import { describe, expect, it } from 'vitest';

import { avecLeReelEnregistre, joursAuxHeuresRetirees, messageHeuresRetirees } from './heuresRetireesAuReel';

const envoye = [
  { jour: 7, type: 'arret_maladie', heures_faites: 7 },
  { jour: 8, type: 'arret_maladie', heures_faites: 7 },
  { jour: 9, type: 'travail', heures_faites: 7 },
];
const relu = [
  { jour: 7, type: 'arret_maladie', heures_faites: 0 },
  { jour: 8, type: 'arret_maladie', heures_faites: 0 },
  { jour: 9, type: 'travail', heures_faites: 7 },
];

describe('heures réelles retirées par le serveur', () => {
  it('nomme les jours où des heures saisies ne sont pas gardées', () => {
    expect(joursAuxHeuresRetirees(envoye, relu)).toEqual([7, 8]);
  });

  it('l’écran reprend ce que le serveur a gardé', () => {
    expect(avecLeReelEnregistre(envoye, relu).map((j) => j.heures_faites)).toEqual([0, 0, 7]);
  });

  it('dit pourquoi et quoi faire', () => {
    expect(messageHeuresRetirees([7, 8])).toBe(
      'Les 7 et 8 sont des jours d’arrêt ou d’absence : les heures saisies n’ont pas été gardées. ' +
        'Si la personne a travaillé, changez d’abord le type du jour.'
    );
    expect(messageHeuresRetirees([7])).toBe(
      'Le 7 est un jour d’arrêt ou d’absence : les heures saisies n’ont pas été gardées. ' +
        'Si la personne a travaillé, changez d’abord le type du jour.'
    );
  });

  it('rien de retiré, rien à dire', () => {
    expect(joursAuxHeuresRetirees(relu, relu)).toEqual([]);
  });
});
