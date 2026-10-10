import { describe, expect, it } from 'vitest';
import { aideCodeDsn } from './aideCodesDsn';

describe('aide des champs à code DSN', () => {
  it("le motif de recours dit qu'il coupe la prime de précarité pour certains motifs", () => {
    const aide = aideCodeDsn('specificites_paie.dsn_reprise.motif_recours');
    expect(aide).toContain('prime de précarité');
    expect(aide).toContain('saisonnier');
    expect(aide).not.toContain('sans effet');
  });

  it("le niveau de diplôme reste une information déclarée en DSN", () => {
    expect(aideCodeDsn('specificites_paie.dsn_reprise.niveau_diplome_prepare')).toBe(
      'Déclaré en DSN, sans effet sur le bulletin.'
    );
  });
});
