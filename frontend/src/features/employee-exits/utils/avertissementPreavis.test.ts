import { describe, expect, it } from 'vitest';

import { avertissementFinDePreavis } from './preavis';

/**
 * Tournage H.2, scène 6 (20/10/2026, déjà relevé le 12/10) : l'avertissement
 * « Le dernier jour travaillé est antérieur à la fin théorique du préavis… »
 * restait affiché après le choix d'une dispense. Un préavis dispensé ne
 * s'exécute pas : le dernier jour peut tomber avant sa fin théorique.
 */
const base = {
  applicable: true,
  jours: 60,
  dateDeDemande: '2026-10-01',
  dernierJour: '2026-10-15',
};

describe('avertissement du dernier jour avant la fin du préavis', () => {
  it('préavis exécuté et dernier jour trop tôt : l’avertissement dit quoi faire', () => {
    expect(avertissementFinDePreavis({ ...base, execution: 'executed' })).toBe(
      'Le dernier jour travaillé est antérieur à la fin théorique du préavis (60 jours). Vérifiez les dates ou indiquez une dispense.'
    );
  });

  it.each(['paid', 'waived'] as const)('préavis dispensé (%s) : plus d’avertissement', (execution) => {
    expect(avertissementFinDePreavis({ ...base, execution })).toBeNull();
  });

  it('dernier jour après la fin du préavis : rien à dire', () => {
    expect(avertissementFinDePreavis({ ...base, dernierJour: '2026-12-15', execution: 'executed' })).toBeNull();
  });

  it('sans préavis applicable ou sans durée : rien à dire', () => {
    expect(avertissementFinDePreavis({ ...base, applicable: false, execution: 'executed' })).toBeNull();
    expect(avertissementFinDePreavis({ ...base, jours: 0, execution: 'executed' })).toBeNull();
  });
});

describe('champ « Durée du préavis (jours) »', () => {
  it('vide tant qu’aucune durée n’est posée : taper « 60 » donne 60, pas « 060 »', async () => {
    const { dureePreavisAffichee, dureePreavisSaisie } = await import('./preavis');
    expect(dureePreavisAffichee(0)).toBe('');
    expect(dureePreavisAffichee(30)).toBe('30');
    expect(dureePreavisSaisie('60')).toBe(60);
    expect(dureePreavisSaisie('')).toBe(0);
  });

  it('le contenu du champ se sélectionne à la saisie', async () => {
    const { readFileSync } = await import('node:fs');
    const path = await import('node:path');
    const source = readFileSync(
      path.resolve(__dirname, '../../../components/exits/CreateExitDialog.tsx'),
      'utf8'
    ).replace(/\s+/g, ' ');
    expect(source).toMatch(/id="notice_period_days" type="number" min="0" placeholder="0" value=\{dureePreavisAffichee\(noticePeriodDays\)\} onFocus=\{\(e\) => e\.currentTarget\.select\(\)\}/);
  });
});
