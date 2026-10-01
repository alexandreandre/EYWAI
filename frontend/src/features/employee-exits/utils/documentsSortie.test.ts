import { describe, expect, it } from 'vitest';

import {
  MESSAGE_GENERER_DABORD_BULLETIN,
  documentsDeSortieGrises,
} from './documentsSortie';

describe('documents de sortie tant que le bulletin manque', () => {
  it('sans bulletin du mois de sortie : grisés, avec la mention', () => {
    expect(documentsDeSortieGrises(null)).toBe(true);
    expect(documentsDeSortieGrises(undefined)).toBe(true);
    expect(MESSAGE_GENERER_DABORD_BULLETIN).toBe('Générez d\'abord le bulletin de sortie');
  });

  it('dès que le bulletin du mois de sortie existe : plus grisés', () => {
    expect(documentsDeSortieGrises({ mois: '09/2026' })).toBe(false);
  });
});
