import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';

import { extractDetail, getUserErrorMessage } from './errorMessages';

function erreur409(detail: unknown): AxiosError {
  const err = new AxiosError('Request failed with status code 409');
  err.response = {
    status: 409,
    data: { detail },
    statusText: 'Conflict',
    headers: {},
    config: {} as never,
  };
  return err;
}

describe('lecture du détail d’une erreur serveur', () => {
  it('lit le message d’un détail objet {code, message}', () => {
    const e = erreur409({
      code: 'bulletin_valide',
      message: 'Ce bulletin est validé : sa suppression directe est refusée.',
    });
    expect(extractDetail(e)).toBe('Ce bulletin est validé : sa suppression directe est refusée.');
  });

  it('affiche ce message plutôt que le repli vague', () => {
    const e = erreur409({ code: 'bulletin_valide', message: 'Ce bulletin est validé.' });
    expect(getUserErrorMessage(e, 'La suppression du bulletin a échoué.')).toBe(
      'Ce bulletin est validé.'
    );
  });

  it('un objet sans message lisible reste ignoré', () => {
    expect(extractDetail(erreur409({ code: 'x', alertes: [] }))).toBeNull();
  });

  it('les détails texte et de validation restent lus', () => {
    expect(extractDetail(erreur409('Refusé'))).toBe('Refusé');
    expect(extractDetail(erreur409([{ msg: 'Champ requis' }]))).toBe('Champ requis');
  });
});
