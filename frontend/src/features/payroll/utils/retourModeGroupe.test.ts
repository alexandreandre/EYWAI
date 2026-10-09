import { describe, expect, it } from 'vitest';

import { destinationDeFermeture, etatPourModeGroupe } from './retourModeGroupe';

describe('fermer le Mode Groupé ramène d’où l’on vient', () => {
  it('depuis la page Paie, retour à la page Paie (mois compris)', () => {
    const etat = etatPourModeGroupe({ pathname: '/payroll', search: '?view=month&month=2026-10' });
    expect(destinationDeFermeture(etat)).toBe('/payroll?view=month&month=2026-10');
  });

  it('depuis le tableau de bord, retour au tableau de bord', () => {
    expect(destinationDeFermeture(etatPourModeGroupe({ pathname: '/', search: '' }))).toBe('/');
  });

  it('adresse ouverte directement ou rechargée : la page Paie, pas le tableau de bord', () => {
    expect(destinationDeFermeture(undefined)).toBe('/payroll');
    expect(destinationDeFermeture(null)).toBe('/payroll');
    expect(destinationDeFermeture({})).toBe('/payroll');
  });

  it('une origine qui n’est pas une page de l’application est ignorée', () => {
    expect(destinationDeFermeture({ depuis: 'https://exemple.fr/x' })).toBe('/payroll');
    expect(destinationDeFermeture({ depuis: '//exemple.fr' })).toBe('/payroll');
    expect(destinationDeFermeture({ depuis: 42 })).toBe('/payroll');
  });

  it('ne revient jamais sur le Mode Groupé lui-même', () => {
    expect(destinationDeFermeture({ depuis: '/payroll/generate' })).toBe('/payroll');
  });
});
