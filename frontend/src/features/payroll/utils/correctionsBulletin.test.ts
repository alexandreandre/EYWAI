import { describe, expect, it } from 'vitest';
import {
  aDesModifications,
  etatInitial,
  heuresDeclarees,
  quantitesHeuresSup,
  recalculAttendu,
  requeteDeCorrection,
  type EtatCorrections,
} from './correctionsBulletin';

const base = { libelle: 'Salaire de base', quantite: 151.67, taux: 14.28, gain: 2165.85 };
const structurelles = { libelle: 'Heures suppl. structurelles majorées à 25%', quantite: 17.33, taux: 17.85, gain: 309.34 };
const hs25 = { libelle: 'Heures suppl. majorées à 25%', quantite: 6, taux: 17.85, gain: 107.1 };
const hs50 = { libelle: 'Heures suppl. majorées à 50%', quantite: 3.5, taux: 21.42, gain: 74.97 };
const prime = { libelle: 'Prime de chantier', gain: 100, saisie_id: 's-1' };
const panier = { libelle: 'Panier', montant: 7.5, saisie_id: 's-2' };

const bulletin = {
  calcul_du_brut: [base, structurelles, hs25, hs50, prime],
  primes_non_soumises: [panier],
};

function avec(etat: EtatCorrections, changement: Partial<EtatCorrections>): EtatCorrections {
  return { ...etat, ...changement };
}

describe('lecture du bulletin', () => {
  it('lit les deux paliers, sans les structurelles', () => {
    expect(quantitesHeuresSup(bulletin)).toEqual([6, 3.5]);
  });
  it('un seul palier se lit sur son libellé', () => {
    expect(quantitesHeuresSup({ calcul_du_brut: [base, hs50] })).toEqual([0, 3.5]);
    expect(quantitesHeuresSup({ calcul_du_brut: [base, hs25] })).toEqual([6, 0]);
  });
  it('les primes saisies, avec leur régime', () => {
    expect(etatInitial(bulletin, null).primes).toEqual([
      { saisieId: 's-1', libelle: 'Prime de chantier', montant: 100, soumise: true },
      { saisieId: 's-2', libelle: 'Panier', montant: 7.5, soumise: false },
    ]);
  });
  it('les heures déclarées au bulletin', () => {
    expect(heuresDeclarees({ heures_sup_declarees: { hs25: 4, hs50: 0, planning: 6 } })).toEqual({
      hs25: 4,
      hs50: 0,
      planning: 6,
    });
    expect(heuresDeclarees(bulletin)).toBeNull();
  });
});

describe('requête de correction', () => {
  const initial = etatInitial(bulletin, 'Note');

  it('rien ne change : rien à enregistrer', () => {
    expect(aDesModifications(initial, { ...initial })).toBe(false);
    expect(requeteDeCorrection(initial, initial, '2026-09-28T09:00:00Z')).toEqual({
      corrections: {},
      base_updated_at: '2026-09-28T09:00:00Z',
    });
  });

  it('les heures corrigées partent par palier, même à zéro', () => {
    expect(requeteDeCorrection(initial, avec(initial, { hs25: 4 }), null).corrections).toEqual({
      heures_sup: { hs25: 4, hs50: 3.5 },
    });
    expect(requeteDeCorrection(initial, avec(initial, { hs25: 0, hs50: 0 }), null).corrections).toEqual({
      heures_sup: { hs25: 0, hs50: 0 },
    });
  });

  it('déplacer une heure d’un palier à l’autre est une correction', () => {
    const courant = avec(initial, { hs25: 7, hs50: 2.5 });
    expect(recalculAttendu(initial, courant)).toBe(true);
  });

  it('revenir au planning prime sur les heures saisies', () => {
    const courant = avec(initial, { hs25: 1, revenirAuPlanning: true });
    expect(requeteDeCorrection(initial, courant, null).corrections).toEqual({ revenir_au_planning: true });
  });

  it('primes corrigées, retirées et ajoutées', () => {
    const courant = avec(initial, {
      primes: [
        { saisieId: 's-1', libelle: 'Prime de chantier', montant: 150, soumise: true },
        { saisieId: 's-2', libelle: 'Panier', montant: 7.5, soumise: false },
      ],
      primesRetirees: ['s-2'],
      primesAjoutees: [
        { name: 'Prime de fin d’année', amount: 200.004, is_socially_taxed: true, is_taxable: true, catalog_prime_id: null },
      ],
    });
    expect(requeteDeCorrection(initial, courant, null).corrections).toEqual({
      primes_corrigees: [{ saisie_id: 's-1', amount: 150 }],
      primes_retirees: ['s-2'],
      primes_ajoutees: [
        { name: 'Prime de fin d’année', amount: 200, is_socially_taxed: true, is_taxable: true, catalog_prime_id: null },
      ],
    });
  });

  it('une prime corrigée puis retirée ne part que retirée', () => {
    const courant = avec(initial, {
      primes: [{ saisieId: 's-1', libelle: 'Prime de chantier', montant: 150, soumise: true }],
      primesRetirees: ['s-1'],
    });
    expect(requeteDeCorrection(initial, courant, null).corrections).toEqual({ primes_retirees: ['s-1'] });
  });

  it('les notes seules : enregistrées sans recalcul', () => {
    const courant = avec(initial, { pdfNotes: 'Nouvelle note', noteInterne: '  Vu avec la salariée ' });
    const requete = requeteDeCorrection(initial, courant, null);
    expect(requete).toEqual({
      corrections: {},
      pdf_notes: 'Nouvelle note',
      internal_note: 'Vu avec la salariée',
    });
    expect(aDesModifications(initial, courant)).toBe(true);
    expect(recalculAttendu(initial, courant)).toBe(false);
  });

  it('effacer la note du PDF envoie une chaîne vide', () => {
    expect(requeteDeCorrection(initial, avec(initial, { pdfNotes: '' }), null).pdf_notes).toBe('');
  });

  it('le résumé seul ne suffit pas à enregistrer', () => {
    expect(aDesModifications(initial, avec(initial, { resume: 'Rien' }))).toBe(false);
  });
});

describe('primeDepuisSaisie', () => {
  it('reprend nom, montant et régime de la prime choisie', async () => {
    const { primeDepuisSaisie } = await import('./correctionsBulletin');
    expect(
      primeDepuisSaisie({
        employee_id: 'emp-1',
        year: 2026,
        month: 8,
        name: 'Prime de fin de chantier',
        amount: 100,
        is_socially_taxed: false,
        is_taxable: true,
      })
    ).toEqual({
      name: 'Prime de fin de chantier',
      amount: 100,
      is_socially_taxed: false,
      is_taxable: true,
      catalog_prime_id: null,
      sur_le_net: false,
    });
  });

  it('garde « sur le net » : une retenue ne devient pas une prime négative', async () => {
    const { primeDepuisSaisie } = await import('./correctionsBulletin');
    const prime = primeDepuisSaisie({
      employee_id: 'emp-1',
      year: 2026,
      month: 8,
      name: 'Acompte',
      amount: -200,
      sur_le_net: true,
      is_socially_taxed: false,
      is_taxable: false,
    });
    expect(prime.sur_le_net).toBe(true);
    expect(prime.amount).toBe(-200);
  });
});
