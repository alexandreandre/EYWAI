import { describe, expect, it } from 'vitest';

import { messageDeSuppression } from './suppressionBulletin';

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
