import { describe, expect, it } from 'vitest';

import { compteEtapeCalendriers } from './etapesPreparation';

describe('étape « Calendrier & temps de travail » de la liste de préparation', () => {
  it('sans lecture du mois choisi, garde le compteur de la barre latérale', () => {
    expect(compteEtapeCalendriers(2, undefined)).toEqual({ statut: 'ok', compte: 2 });
  });

  it('suit le mois choisi : un salarié à saisir en octobre compte, même si le compteur est à 0', () => {
    expect(compteEtapeCalendriers(0, { statut: 'ok', valeur: ['e1'] })).toEqual({
      statut: 'ok',
      compte: 1,
    });
  });

  it('le mois choisi complet vaut 0, quel que soit le compteur général', () => {
    expect(compteEtapeCalendriers(3, { statut: 'ok', valeur: [] })).toEqual({
      statut: 'ok',
      compte: 0,
    });
  });

  it('lecture en cours ou en erreur : jamais un « à jour » par défaut', () => {
    expect(compteEtapeCalendriers(0, { statut: 'chargement' }).statut).toBe('chargement');
    expect(compteEtapeCalendriers(0, { statut: 'erreur' }).statut).toBe('erreur');
  });
});
