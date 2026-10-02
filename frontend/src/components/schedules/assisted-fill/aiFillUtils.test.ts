import { describe, expect, it } from 'vitest';

import { messageDeLErreur } from './aiFillUtils';

describe('messageDeLErreur', () => {
  it('donne la phrase du serveur plutôt que « Request failed with status code 409 »', () => {
    const erreur = Object.assign(new Error('Request failed with status code 409'), {
      response: { data: { detail: 'Ce fichier a déjà été importé.' } },
    });
    expect(messageDeLErreur(erreur)).toBe('Ce fichier a déjà été importé.');
  });

  it('garde le message d’une erreur locale', () => {
    expect(messageDeLErreur(new Error('Import annulé'))).toBe('Import annulé');
  });

  it('sans rien de lisible, une phrase claire', () => {
    expect(messageDeLErreur({})).toBe("L'analyse a échoué. Réessayez.");
  });
});
