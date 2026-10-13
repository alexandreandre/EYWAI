import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  INFOBULLE_EN_VERIFICATION,
  MESSAGE_EN_VERIFICATION,
  delaiAvantRelecture,
  enVerification,
  intervalleDeRelecture,
} from './validesEnVerification';

/**
 * Lot 42 : une donnée d'un bulletin validé change (le calendrier du mois suivant
 * est posé). Martine le recalcule au bac à sable HORS de la requête : la Paie
 * s'affiche tout de suite, le bulletin dit « Vérification… » le temps du calcul
 * (ni « À recalculer », ni à jour : on ne le sait pas encore), puis l'écran se
 * relit tout seul jusqu'au verdict.
 */
describe('un validé en vérification', () => {
  it('se reconnaît au drapeau du serveur, jamais sur un bulletin repris', () => {
    expect(enVerification({ a_verifier: true })).toBe(true);
    expect(enVerification({ a_verifier: false })).toBe(false);
    expect(enVerification({})).toBe(false);
    expect(enVerification(null)).toBe(false);
    expect(enVerification({ a_verifier: true, origine: 'importe' })).toBe(false);
  });

  it('dit ce qui se passe, sans annoncer de résultat', () => {
    expect(INFOBULLE_EN_VERIFICATION).toBe(
      'Une donnée de ce bulletin validé a changé depuis sa validation. Martine le recalcule sans rien enregistrer pour savoir si un montant change : le résultat s’affiche dans quelques secondes.'
    );
    expect(MESSAGE_EN_VERIFICATION).toContain('Martine le recalcule sans rien enregistrer');
  });

  it('la liste se relit toute seule tant qu’un bulletin est en vérification', () => {
    expect(intervalleDeRelecture([{ a_verifier: false }, { a_verifier: true }])).toBe(5000);
    expect(intervalleDeRelecture([{ a_verifier: false }])).toBe(false);
    expect(intervalleDeRelecture(undefined)).toBe(false);
  });

  it('l’écran du bulletin se relit seulement sans correction en cours', () => {
    expect(delaiAvantRelecture({ a_verifier: true }, false)).toBe(5000);
    // Relire effacerait les corrections en cours : on attend qu'elles soient enregistrées.
    expect(delaiAvantRelecture({ a_verifier: true }, true)).toBeNull();
    expect(delaiAvantRelecture({ a_verifier: false }, false)).toBeNull();
  });
});

describe('les écrans passent par ces règles', () => {
  it.each([
    ['../components/PayrollPayslipRow.tsx', 'enVerification('],
    ['../../../pages/rh/Payroll.tsx', 'intervalleDeRelecture('],
    ['../../../pages/rh/PayslipEdit.tsx', 'delaiAvantRelecture('],
    ['../../../pages/rh/PayslipEdit.tsx', 'MESSAGE_EN_VERIFICATION'],
  ])('%s utilise %s', (fichier, appel) => {
    const source = fs.readFileSync(path.resolve(__dirname, fichier), 'utf8');
    expect(source).toContain(appel);
  });
});
