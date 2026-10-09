import { describe, expect, it } from 'vitest';

import { champsManquants, messageAucunSelectionnable } from './ficheIncomplete';

const emp = (surcharge: Record<string, unknown> = {}) => ({
  id: 'e1',
  first_name: 'A',
  last_name: 'B',
  payroll_eligible: true,
  missing_payroll_fields: [] as string[],
  ...surcharge,
});

describe('champsManquants', () => {
  it('rend ce que le serveur a renvoyé', () => {
    expect(champsManquants(emp({ missing_payroll_fields: ['RIB', 'Adresse'] }))).toEqual(['RIB', 'Adresse']);
  });

  it('sans champ renvoyé, n’invente pas les cinq champs requis', () => {
    expect(champsManquants(emp())).toEqual([]);
    expect(champsManquants(emp({ missing_payroll_fields: undefined }))).toEqual([]);
  });
});

describe('messageAucunSelectionnable', () => {
  it('des fiches à compléter quand le serveur signale des champs manquants', () => {
    const m = messageAucunSelectionnable([emp({ payroll_eligible: false, missing_payroll_fields: ['RIB'] })]);
    expect(m.titre).toBe('1 collaborateur — fiche à compléter');
  });

  it('des fiches complètes ne sont pas « à compléter » : ils sont hors période du mois', () => {
    const m = messageAucunSelectionnable([emp(), emp({ id: 'e2' })]);
    expect(m.titre).toBe('2 collaborateurs — aucun présent sur le mois choisi');
    expect(m.description).toContain('autre mois');
    expect(m.fichesACompleter).toBe(false);
  });
});
