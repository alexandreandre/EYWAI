import { describe, expect, it } from 'vitest';

import {
  TITRE_ECHEC_PLANNING,
  estTypeDeConvention,
  libelleConventionPlanning,
  messageListeVide,
} from './typesDePoste';

describe('types de poste par société', () => {
  it('un type de convention est signalé, celui de la société non', () => {
    expect(estTypeDeConvention({ origine: 'convention' })).toBe(true);
    expect(estTypeDeConvention({ origine: 'societe' })).toBe(false);
    // Réponse d'un serveur plus ancien : le type est traité comme celui de la société.
    expect(estTypeDeConvention({})).toBe(false);
  });

  it('libellé de la convention du planning, IDCC quand il existe', () => {
    expect(libelleConventionPlanning({ label: 'Convention 35h hebdomadaire', idcc: null })).toBe(
      'Convention 35h hebdomadaire',
    );
    expect(libelleConventionPlanning({ label: 'Plasturgie', idcc: '0292' })).toBe(
      'Plasturgie (IDCC 0292)',
    );
  });

  it('la liste vide ne demande plus de convention', () => {
    expect(messageListeVide()).not.toMatch(/CC|convention/i);
  });

  it('titres d’échec nommés par action', () => {
    expect(TITRE_ECHEC_PLANNING.parametres).toBe('Paramètres du planning non enregistrés');
    expect(TITRE_ECHEC_PLANNING.creation).toBe('Type de poste non créé');
    expect(TITRE_ECHEC_PLANNING.modification).toBe('Type de poste non enregistré');
    expect(TITRE_ECHEC_PLANNING.desactivation).toBe('Type de poste non désactivé');
  });
});
