import { describe, expect, it } from 'vitest';

import {
  libelleMontantSaisie,
  libellePersonnesACharge,
  libelleResteDu,
  libelleStatutSaisie,
  modificationDesMontants,
  montantSaisi,
  personnesACharge,
} from './seizureFormat';

describe('libelleMontantSaisie', () => {
  it('formate un montant fixe reçu en texte (les décimaux arrivent en chaîne de Supabase)', () => {
    // Morande, 12/09 : la page plantait en écran blanc sur "46.49".toFixed.
    expect(
      libelleMontantSaisie({ calculation_mode: 'fixe', amount: '46.49' as unknown as number })
    ).toBe('46.49€');
  });

  it('formate un montant fixe numérique', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'fixe', amount: 120 })).toBe('120.00€');
  });

  it('affiche le pourcentage', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'pourcentage', percentage: 10 })).toBe('10%');
  });

  it('retombe sur le barème légal', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'barème_legal' })).toBe('Barème légal');
    expect(libelleMontantSaisie({ calculation_mode: 'fixe', amount: undefined })).toBe(
      'Barème légal'
    );
  });
});

describe('personnesACharge', () => {
  // Le barème légal relève chaque seuil par personne à charge (R3252-3) : un
  // nombre entier, jamais négatif ; un champ vide vaut aucune.
  it('lit un entier positif', () => {
    expect(personnesACharge('2')).toBe(2);
  });

  it('vide, négatif ou illisible : aucune', () => {
    expect(personnesACharge('')).toBe(0);
    expect(personnesACharge('-1')).toBe(0);
    expect(personnesACharge('abc')).toBe(0);
  });

  it('arrondit à l’entier inférieur', () => {
    expect(personnesACharge('1.7')).toBe(1);
  });
});

describe('libellePersonnesACharge', () => {
  it('dit le nombre en clair', () => {
    expect(libellePersonnesACharge(0)).toBe('Aucune');
    expect(libellePersonnesACharge(undefined)).toBe('Aucune');
    expect(libellePersonnesACharge(1)).toBe('1 personne');
    expect(libellePersonnesACharge(3)).toBe('3 personnes');
  });
});

describe('montantSaisi', () => {
  it('lit un montant en euros, virgule ou point, espaces compris', () => {
    expect(montantSaisi('1 200,50')).toBe(1200.5);
    expect(montantSaisi('300.25')).toBe(300.25);
  });

  it('vide : aucun montant', () => {
    expect(montantSaisi('')).toBeNull();
    expect(montantSaisi('  ')).toBeNull();
  });

  it('négatif ou illisible : refusé', () => {
    expect(montantSaisi('-5')).toBeUndefined();
    expect(montantSaisi('abc')).toBeUndefined();
  });
});

describe('libelleResteDu', () => {
  it('dit le reste dû sur le total (décimaux reçus en texte compris)', () => {
    expect(
      libelleResteDu({ montant_total: '1000' as unknown as number, reste_du: 600 })
    ).toBe('Reste dû : 600,00 € sur 1 000,00 €');
  });

  it('dit la dette soldée', () => {
    expect(libelleResteDu({ montant_total: 1000, reste_du: 0 })).toBe('Soldée (1 000,00 €)');
  });

  it('sans montant total : rien', () => {
    expect(libelleResteDu({ montant_total: null, reste_du: null })).toBeNull();
    expect(libelleResteDu({})).toBeNull();
  });
});

describe('libelleStatutSaisie', () => {
  it('une saisie à reste dû nul est « Soldée » (le statut n’est pas touché)', () => {
    expect(libelleStatutSaisie({ status: 'active', montant_total: 1000, reste_du: 0 })).toBe('Soldée');
    expect(libelleStatutSaisie({ status: 'closed', montant_total: 1000, reste_du: 0 })).toBe('Soldée');
  });

  it('sinon le statut habituel', () => {
    expect(libelleStatutSaisie({ status: 'closed' })).toBe('Clôturée');
    expect(libelleStatutSaisie({ status: 'active', montant_total: 1000, reste_du: 600 })).toBe('Active');
    expect(libelleStatutSaisie({ status: 'suspended', montant_total: 1000, reste_du: 0 })).toBe('Suspendue');
  });
});

describe('modificationDesMontants', () => {
  const saisie = { calculation_mode: 'fixe' as const, amount: 300, montant_total: 1000 };

  it('envoie la mensualité et le total modifiés', () => {
    expect(modificationDesMontants(saisie, { mensualite: '250', total: '1 200' })).toEqual({
      amount: 250,
      montant_total: 1200,
    });
  });

  it('n’envoie que ce qui change', () => {
    expect(modificationDesMontants(saisie, { mensualite: '250', total: '1000' })).toEqual({
      amount: 250,
    });
    expect(modificationDesMontants(saisie, { mensualite: '300', total: '1000' })).toEqual({});
  });

  it('au barème légal, la mensualité vidée est effacée (quotité du mois)', () => {
    expect(
      modificationDesMontants(
        { calculation_mode: 'barème_legal', amount: 300, montant_total: null },
        { mensualite: '', total: '' }
      )
    ).toEqual({ amount: null });
  });

  it('un total vidé est effacé (la saisie court sans fin)', () => {
    expect(modificationDesMontants(saisie, { mensualite: '300', total: '' })).toEqual({
      montant_total: null,
    });
  });

  it('refuse un montant illisible ou une mensualité vide en montant fixe', () => {
    expect(modificationDesMontants(saisie, { mensualite: 'abc', total: '1000' })).toBe(
      'Mensualité illisible : un montant en euros, positif.'
    );
    expect(modificationDesMontants(saisie, { mensualite: '', total: '1000' })).toBe(
      'Une saisie à montant fixe a besoin d’une mensualité.'
    );
    expect(modificationDesMontants(saisie, { mensualite: '300', total: '-1' })).toBe(
      'Montant total illisible : un montant en euros, positif.'
    );
  });
});
