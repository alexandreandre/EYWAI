import { describe, expect, it } from 'vitest';

import { toastDeGeneration } from './alertesDuRecu';

describe('génération d’un document de sortie : les alertes du reçu (décision du 12/10)', () => {
  it('sans alerte, le succès habituel', () => {
    expect(toastDeGeneration({ success: true })).toEqual({
      title: 'Succès',
      description: 'Document généré avec succès',
    });
  });

  it('avec une alerte, le document est généré et l’alerte est dite', () => {
    const toast = toastDeGeneration({
      success: true,
      alertes: ['Départ : 3 j de RTT non pris restent « Néant ». À vérifier selon l’accord.'],
    });
    expect(toast.title).toBe('Document généré, à vérifier');
    expect(toast.description).toContain('3 j de RTT');
  });
});
