import { describe, expect, it } from 'vitest';

import { commandesDuMois } from './ratesMonthlyControls';

const etat = { enabled: true, showRun: true, showRestart: true };

describe('commandesDuMois', () => {
  it('un RH voit l’état du mois sans interrupteur actif ni bouton', () => {
    expect(commandesDuMois(etat, { isSyncing: false, isMonthlySyncRunning: false, peutGerer: false })).toEqual({
      lancer: false,
      recommencer: false,
      interrupteurActif: false,
    });
  });

  it('un admin plateforme lance, recommence et coupe le lot', () => {
    expect(commandesDuMois(etat, { isSyncing: false, isMonthlySyncRunning: false, peutGerer: true })).toEqual({
      lancer: true,
      recommencer: true,
      interrupteurActif: true,
    });
  });

  it('pendant une mise à jour, rien ne se relance', () => {
    expect(commandesDuMois(etat, { isSyncing: true, isMonthlySyncRunning: true, peutGerer: true })).toEqual({
      lancer: false,
      recommencer: false,
      interrupteurActif: false,
    });
  });
});
