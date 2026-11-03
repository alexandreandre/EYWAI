import { describe, expect, it } from 'vitest';

import { INTRO_IMPORT_PAS, SOURCES_IMPORT_PAS } from '@/features/pas-rates/lib/importPas';

describe('fenêtre « Mettre à jour les taux » (promesse de la vidéo B, 02/11)', () => {
  it('propose la DSN du mois en premier, comme la vidéo B.5', () => {
    expect(SOURCES_IMPORT_PAS[0].value).toBe('dsn');
    expect(INTRO_IMPORT_PAS).toMatch(/^Déposez la DSN du mois/);
    expect(INTRO_IMPORT_PAS).toContain("Rien n'est écrit tant que vous n'avez pas confirmé.");
  });

  it('ne fait jamais croire que le compte rendu se télécharge sur net-entreprises', () => {
    const textes = [INTRO_IMPORT_PAS, ...SOURCES_IMPORT_PAS.map((s) => s.aide)].join(' ');
    expect(textes).not.toMatch(/téléchargé/i);
    const crm = SOURCES_IMPORT_PAS.find((s) => s.value === 'crm');
    expect(crm?.aide).toContain("affiche à l'écran");
  });
});
