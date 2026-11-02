import { describe, expect, it } from 'vitest';

import { ligneVide, lignesDeLaSaisie, saisieDesLignes } from '@/features/company/lib/formulesPrevoyanceSaisie';

describe('saisie d’une formule de prévoyance', () => {
  it('affiche les taux en % et la base, Tranche A par défaut', () => {
    const [a, b] = saisieDesLignes([
      { libelle: 'TA', salarial: 0.0078, patronal: 0.0124, forfait_social: 0.08 },
      { libelle: 'TB', salarial: 0.01, patronal: 0, forfait_social: 0, base: 'tranche_2', organisme: 'X' },
    ]);
    expect(a).toMatchObject({ libelle: 'TA', salarial: '0,78', patronal: '1,24', base: 'brut_plafonne' });
    // Le forfait social suit la loi (effectif), pas la ligne : il n'est plus
    // un champ de la fenêtre, la valeur ancienne passe telle quelle.
    expect(a).not.toHaveProperty('forfait_social');
    expect(a.autres).toEqual({ forfait_social: 0.08 });
    expect(b).toMatchObject({ base: 'tranche_2', autres: { organisme: 'X', forfait_social: 0 } });
  });

  it('revient en fractions, avec les autres clés', () => {
    const { lignes, erreur } = lignesDeLaSaisie([
      { libelle: ' TA ', salarial: '0,78', patronal: '1,24', base: 'brut_plafonne', autres: {} },
      { libelle: 'TB', salarial: '1', patronal: '', base: 'tranche_2', autres: { organisme: 'X', forfait_social: 0.08 } },
    ]);
    expect(erreur).toBeNull();
    expect(lignes[0]).toEqual({ libelle: 'TA', salarial: 0.0078, patronal: 0.0124, base: 'brut_plafonne' });
    expect(lignes[1]).toEqual({ libelle: 'TB', salarial: 0.01, patronal: 0, base: 'tranche_2', organisme: 'X', forfait_social: 0.08 });
  });

  it('refuse un libellé vide ou un taux qui n’est pas un nombre', () => {
    expect(lignesDeLaSaisie([{ ...ligneVide(), libelle: '' }]).erreur).toBe('Ligne 1 : libellé requis.');
    expect(lignesDeLaSaisie([{ ...ligneVide(), libelle: 'TA', salarial: 'abc' }]).erreur).toBe(
      'Ligne 1 : saisissez un taux en %, par exemple 0,78.',
    );
  });

  it('refuse une formule sans ligne', () => {
    expect(lignesDeLaSaisie([]).erreur).toBe('Ajoutez au moins une ligne.');
  });
});
