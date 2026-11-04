import { describe, expect, it } from 'vitest';

import { versionDuSite } from './versionDuSite';

describe('versionDuSite', () => {
  it("affiche l'étiquette du déploiement et le début du commit", () => {
    expect(
      versionDuSite({ VITE_APP_VERSION: 'paie-2026-11-03.2', VITE_APP_BUILD_ID: '0123456789abcdef' }),
    ).toEqual({
      libelle: 'Version paie-2026-11-03.2 · 0123456',
      detail: 'paie-2026-11-03.2 (commit 0123456789abcdef)',
    });
  });

  it('dit « non étiquetée » quand seul le commit est connu', () => {
    expect(versionDuSite({ VITE_APP_BUILD_ID: '0123456789abcdef' }).libelle).toBe(
      'Version non étiquetée · 0123456',
    );
  });

  it('dit « locale » hors déploiement', () => {
    expect(versionDuSite({}).libelle).toBe('Version locale');
  });
});
