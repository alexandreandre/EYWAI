import { describe, expect, it } from 'vitest';

import { fenetreDeSuppression, messageDeSuppression } from './suppressionBulletin';

describe('messageDeSuppression', () => {
  it('une suppression faite le dit simplement', () => {
    expect(messageDeSuppression({ dejaSupprime: false })).toEqual({ title: 'Bulletin supprimé' });
  });

  it('un bulletin déjà supprimé le dit, sans parler d’échec, et dit qu’il n’y a rien à refaire', () => {
    const message = messageDeSuppression({ dejaSupprime: true });

    expect(message.title).toBe('Bulletin déjà supprimé');
    expect(message.description).toMatch(/autre écran ou un autre onglet/);
    expect(message.description).toMatch(/rien à refaire/i);
    expect(`${message.title} ${message.description}`).not.toMatch(/erreur|échec|impossible/i);
  });
});

describe('fenetreDeSuppression', () => {
  it('un bulletin en brouillon : la confirmation habituelle, avec le bouton Supprimer', () => {
    expect(fenetreDeSuppression(false)).toEqual({ titre: 'Supprimer ce bulletin ?', peutSupprimer: true });
  });

  it('un bulletin validé : dit d’emblée qu’il ne se supprime pas, et le geste à faire, sans bouton Supprimer', () => {
    const fenetre = fenetreDeSuppression(true);
    expect(fenetre.peutSupprimer).toBe(false);
    expect(fenetre.titre).toBe('Ce bulletin est validé');
    expect(fenetre.explication).toBe(
      'Un bulletin validé ne se supprime pas. Pour le refaire, ouvrez-le et cliquez sur « Régénérer » : l’ancienne version est archivée, la nouvelle est à valider de nouveau.'
    );
  });
});
