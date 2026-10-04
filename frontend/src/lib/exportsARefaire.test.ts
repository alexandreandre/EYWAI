import { describe, expect, it } from 'vitest';

import { bandeauExportsDuMois, LIBELLE_EXPORT_A_REFAIRE } from './exportsARefaire';

const date = (iso: string) => iso.slice(0, 10);

describe('bandeauExportsDuMois', () => {
  it('sans export, pas de bandeau', () => {
    expect(bandeauExportsDuMois([], date)).toBeNull();
  });

  it('exports à jour : le bandeau d’avant, qui rappelle de les refaire après une correction', () => {
    expect(
      bandeauExportsDuMois(
        [{ type: 'journal_paie', libelle: 'Journal de paie', date: '2026-10-03T08:00:00', a_refaire: false }],
        date
      )
    ).toEqual({
      titre: 'Déjà exporté pour ce mois',
      texte: 'Journal de paie (2026-10-03). Après une correction, refaites ces exports.',
      aRefaire: false,
    });
  });

  it('un export fait avant un bulletin recalculé : le bandeau le nomme comme à refaire', () => {
    const bandeau = bandeauExportsDuMois(
      [
        { type: 'virement_salaires', libelle: 'Virement des salaires', date: '2026-10-01T08:00:00', a_refaire: true },
        { type: 'journal_paie', libelle: 'Journal de paie', date: '2026-10-03T08:00:00', a_refaire: true },
        { type: 'conges_absences', libelle: 'Congés', date: '2026-10-03T09:00:00', a_refaire: false },
      ],
      date
    );

    expect(bandeau).toEqual({
      titre: 'Exports à refaire',
      texte:
        'Bulletins modifiés depuis ces exports : Virement des salaires (2026-10-01) · Journal de paie (2026-10-03). ' +
        'Refaites-les. À jour : Congés (2026-10-03).',
      aRefaire: true,
    });
  });

  it('un serveur qui ne dit rien de « à refaire » garde le bandeau d’avant', () => {
    expect(
      bandeauExportsDuMois([{ type: 'fec', libelle: 'FEC', date: '2026-10-03T08:00:00' }], date)?.aRefaire
    ).toBe(false);
  });
});

describe('LIBELLE_EXPORT_A_REFAIRE', () => {
  it('dit sur la ligne de l’export pourquoi il est à refaire', () => {
    expect(LIBELLE_EXPORT_A_REFAIRE).toBe('Bulletins modifiés depuis cet export : à refaire');
  });
});
