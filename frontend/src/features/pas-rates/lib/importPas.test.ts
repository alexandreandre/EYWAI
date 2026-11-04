import { describe, expect, it } from 'vitest';

import { INTRO_IMPORT_PAS, SOURCES_IMPORT_PAS, bilanImportPas } from '@/features/pas-rates/lib/importPas';

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

describe('bilanImportPas — les échecs restent à l’écran, avec leur raison', () => {
  it('tout appliqué : pas de bilan à garder', () => {
    expect(bilanImportPas({ periode: '2026-10', appliques: 12, historique: 0, echecs: [] })).toBeNull();
  });

  it('des échecs : combien, qui, et pourquoi', () => {
    expect(
      bilanImportPas({
        periode: '2026-10',
        appliques: 10,
        historique: 0,
        echecs: [
          { employee_id: 'e1', salarie: 'Lovelace Ada', erreur: 'Taux hors bornes (45 %).' },
          { employee_id: 'e2', salarie: 'Turing Alan', erreur: 'Traceback (most recent call last)' },
        ],
      }),
    ).toEqual({
      titre: '10 taux mis à jour, 2 salariés en échec',
      lignes: [
        { salarie: 'Lovelace Ada', raison: 'Taux hors bornes (45 %).' },
        { salarie: 'Turing Alan', raison: 'Raison non précisée par le serveur.' },
      ],
      aide: 'Période 2026-10. Corrigez ces taux à la main dans la liste, ou redéposez un fichier corrigé.',
    });
  });
});
