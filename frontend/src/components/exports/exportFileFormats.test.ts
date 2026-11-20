import { describe, expect, it } from 'vitest';

import {
  formatParDefaut,
  formatsProposes,
  libelleDuTelechargement,
  proposeLeChoixDuFormat,
  proposeLePerimetre,
} from './exportFileFormats';

describe('proposeLeChoixDuFormat', () => {
  it('Quadra et Sage sont des fichiers texte : pas de choix « Excel »', () => {
    expect(proposeLeChoixDuFormat('export_cabinet_quadra')).toBe(false);
    expect(proposeLeChoixDuFormat('export_cabinet_sage')).toBe(false);
  });

  it('le format générique reste un vrai CSV ou un vrai classeur', () => {
    expect(proposeLeChoixDuFormat('export_cabinet_generique')).toBe(true);
    expect(proposeLeChoixDuFormat('journal_paie')).toBe(true);
  });

  it('la DSN et le FEC ont leur format propre', () => {
    expect(proposeLeChoixDuFormat('dsn_mensuelle')).toBe(false);
    expect(proposeLeChoixDuFormat('fec')).toBe(false);
  });
});

describe('formatParDefaut', () => {
  it('journal, OD globale et charges par caisse sortent en PDF d’office (Elsa, 20/11)', () => {
    expect(formatParDefaut('journal_paie')).toBe('pdf');
    expect(formatParDefaut('od_globale')).toBe('pdf');
    expect(formatParDefaut('charges_sociales')).toBe('pdf');
  });

  it('les autres gardent leur format d’office', () => {
    expect(formatParDefaut('conges_absences')).toBe('xlsx');
    expect(formatParDefaut('acomptes')).toBe('xlsx');
    expect(formatParDefaut('od_salaires')).toBe('csv');
    expect(formatParDefaut('virement_salaires')).toBe('csv');
  });
});

describe('formatsProposes', () => {
  it('le format d’office est le premier proposé', () => {
    expect(formatsProposes('journal_paie').map((f) => f.value)).toEqual(['pdf', 'xlsx', 'csv']);
    expect(formatsProposes('conges_absences').map((f) => f.value)).toEqual(['xlsx', 'csv', 'pdf']);
  });

  it('les charges par caisse ne proposent plus le CSV, sans le tableau validé', () => {
    expect(formatsProposes('charges_sociales').map((f) => f.value)).toEqual(['pdf', 'xlsx']);
  });

  it('sans choix de format, aucune option', () => {
    expect(formatsProposes('dsn_mensuelle')).toEqual([]);
    expect(formatsProposes('export_cabinet_quadra')).toEqual([]);
  });

  it('chaque option a un libellé lisible', () => {
    expect(formatsProposes('journal_paie')[0]).toEqual({ value: 'pdf', label: 'PDF (.pdf)' });
  });
});

describe('proposeLePerimetre', () => {
  it('masqué pour les exports du mois entier et la DSN', () => {
    for (const type of ['journal_paie', 'charges_sociales', 'od_globale', 'dsn_mensuelle'] as const) {
      expect(proposeLePerimetre(type)).toBe(false);
    }
  });

  it('gardé là où une sélection a un sens', () => {
    expect(proposeLePerimetre('virement_salaires')).toBe(true);
    expect(proposeLePerimetre('conges_absences')).toBe(true);
  });
});

describe('libelleDuTelechargement', () => {
  it('virement en CSV : le fichier pour la banque et la liste de contrôle', () => {
    expect(
      libelleDuTelechargement('virement_salaires', 'virement_salaires_bancaire_2026_10_1781258400.csv'),
    ).toBe('Fichier pour la banque');
    expect(libelleDuTelechargement('virement_salaires', 'virement_salaires_2026_10_1781258400.csv')).toBe(
      'Liste de contrôle',
    );
  });

  it('virement en SEPA : le XML est le fichier pour la banque', () => {
    expect(
      libelleDuTelechargement('virement_salaires', 'virement_salaires_sepa_2026_10_1781258400.xml'),
    ).toBe('Fichier pour la banque');
    expect(
      libelleDuTelechargement('virement_acomptes', 'virement_acomptes_bancaire_2026_10_1781258400.csv'),
    ).toBe('Fichier pour la banque');
  });

  it('les autres exports gardent le nom du fichier', () => {
    expect(libelleDuTelechargement('journal_paie', 'journal_paie_2026_10_1781258400.pdf')).toBeNull();
  });
});
