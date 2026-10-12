import { describe, expect, it } from 'vitest';

import { proposeLeChoixDuFormat } from './exportFileFormats';

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
