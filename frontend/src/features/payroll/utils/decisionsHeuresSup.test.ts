import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';

import { libelleStatutDecision, messageEchecDecision } from './decisionsHeuresSup';

describe('décisions d’heures supplémentaires', () => {
  it('le statut est dit en français', () => {
    expect(libelleStatutDecision('pending')).toBe('À valider');
    expect(libelleStatutDecision('validated')).toBe('Validée');
  });

  it('un statut inconnu n’est jamais montré brut', () => {
    expect(libelleStatutDecision('weird_status')).toBe('—');
    expect(libelleStatutDecision(undefined)).toBe('—');
  });

  it('un échec réseau donne un message lisible, pas celui d’Axios', () => {
    const e = new AxiosError('Request failed with status code 500');
    expect(messageEchecDecision(e)).not.toMatch(/Request failed|status code/);
    expect(messageEchecDecision(new Error('Network Error'))).toBe(
      'La décision n’a pas été enregistrée. Réessayez dans un instant.',
    );
  });
});
