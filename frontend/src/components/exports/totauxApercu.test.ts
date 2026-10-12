import { describe, expect, it } from 'vitest';

import { lignesTotauxDeControle, montantDeLApercu } from './totauxApercu';

const sansInsecables = (texte: string) => texte.replace(/\s/g, ' ');

// Aperçu d'octobre (relevé I.1) : chaque OD a son total d'écritures, le
// journal et le virement leur net ; l'écran affichait le net partout.
const bulletins = {
  employees_count: 2,
  total_brut: 4550,
  total_cotisations_salariales: 952.26,
  total_cotisations_patronales: 715.58,
  total_net_a_payer: 3552.53,
};

describe('montantDeLApercu : le montant propre à chaque export', () => {
  it('une OD ou le FEC : le total de ses écritures, pas le net', () => {
    const od = montantDeLApercu('od_globale', { ...bulletins, total_amount: 5265.58 });
    expect(od?.libelle).toBe('Total des écritures (débit)');
    expect(sansInsecables(od!.texte)).toBe('5 265,58 €');
    expect(sansInsecables(montantDeLApercu('od_pas', { ...bulletins, total_amount: 45.21 })!.texte)).toBe(
      '45,21 €'
    );
    expect(montantDeLApercu('fec', { employees_count: 2, total_amount: 5265.58 })?.libelle).toBe(
      'Total des écritures (débit)'
    );
  });

  it('le journal de paie : le net à payer', () => {
    const journal = montantDeLApercu('journal_paie', bulletins);
    expect(journal?.libelle).toBe('Total net à payer');
    expect(sansInsecables(journal!.texte)).toBe('3 552,53 €');
  });

  it('un virement : le montant à virer', () => {
    const virement = montantDeLApercu('virement_salaires', { employees_count: 2, total_amount: 3552.53 });
    expect(virement?.libelle).toBe('Montant à virer');
  });

  it('les absences se comptent en jours, pas en euros', () => {
    expect(montantDeLApercu('conges_absences', { employees_count: 3, total_amount: 12.5 })).toEqual({
      libelle: 'Jours d’absence',
      texte: '12,5 jours',
    });
  });

  it('sans montant, rien n’est inventé', () => {
    expect(montantDeLApercu('journal_paie', { employees_count: 0 })).toBeNull();
  });
});

describe('lignesTotauxDeControle : jamais un cadre vide', () => {
  it('les bulletins : brut, cotisations et net', () => {
    expect(lignesTotauxDeControle('journal_paie', bulletins).map((l) => l.libelle)).toEqual([
      'Total brut',
      'Total cotisations',
      'Total net',
    ]);
  });

  it('le virement des salaires n’a pas ces totaux : aucune ligne, le cadre ne s’affiche pas', () => {
    expect(lignesTotauxDeControle('virement_salaires', { employees_count: 2, total_amount: 3552.53 })).toEqual(
      []
    );
  });

  it('les acomptes : versements, remboursements et opérations', () => {
    const lignes = lignesTotauxDeControle('acomptes', {
      employees_count: 1,
      total_versements: 300,
      total_remboursements: 100,
      operations_count: 3,
    });
    expect(lignes.map((l) => [l.libelle, sansInsecables(l.texte)])).toEqual([
      ['Total versements', '300,00 €'],
      ['Total remboursements', '100,00 €'],
      ['Opérations', '3'],
    ]);
  });
});
