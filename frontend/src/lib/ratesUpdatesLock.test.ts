import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { RATES_UPDATES_LOCKED, RATES_UPDATES_LOCK_REASON } from './ratesUpdatesLock';

/**
 * `updatesLocked` était déjà accepté par tous les composants de la page « Suivi
 * des taux » — et la page ne le passait à aucun. Le verrou existait donc sans
 * jamais rien verrouiller. Ce test vérifie le câblage, pas la constante : sans
 * lui, retirer une prop réactive les boutons sans que rien ne le signale.
 */
const RACINE = path.resolve(__dirname, '..');

function lire(relatif: string): string {
  return fs.readFileSync(path.join(RACINE, relatif), 'utf-8');
}

describe('verrou des mises à jour de taux', () => {
  const page = lire('pages/rh/Rates.tsx');

  it('la page importe le verrou', () => {
    expect(page).toContain("from '@/lib/ratesUpdatesLock'");
  });

  for (const composant of [
    'RatesKeyParamsSection',
    'RatesCotisationsSection',
    'RatesBaremesSection',
  ]) {
    it(`${composant} reçoit updatesLocked`, () => {
      const debut = page.indexOf(`<${composant}`);
      expect(debut, `${composant} absent de la page`).toBeGreaterThan(-1);
      const bloc = page.slice(debut, page.indexOf('/>', debut));
      expect(bloc).toContain('updatesLocked={RATES_UPDATES_LOCKED}');
    });
  }

  it('la barre de commandes reçoit le verrou', () => {
    expect(page).toContain('updatesLocked: RATES_UPDATES_LOCKED');
  });

  for (const [fichier, boutons] of [
    ['components/rates/RatesPageToolbar.tsx', 1],
    ['components/rates/RatesMonthlyAutoPanel.tsx', 2],
  ] as const) {
    it(`${fichier} désactive ses ${boutons} bouton(s) de lancement`, () => {
      const source = lire(fichier);
      expect(source).toContain('disabled={updatesLocked}');
      const occurrences = source.split('disabled={updatesLocked}').length - 1;
      expect(occurrences).toBe(boutons);
    });
  }

  it('le motif affiché reste non vide', () => {
    expect(RATES_UPDATES_LOCK_REASON.trim().length).toBeGreaterThan(0);
    expect(typeof RATES_UPDATES_LOCKED).toBe('boolean');
  });
});
