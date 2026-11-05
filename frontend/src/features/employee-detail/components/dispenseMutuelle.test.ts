import { describe, expect, it } from 'vitest';

import {
  DISPENSE_VIDE,
  MOTIFS_DISPENSE_MUTUELLE,
  dispenseVersFiche,
  dispenseVersFormulaire,
  problemesDispense,
} from '@/features/employee-detail/components/dispenseMutuelle';

describe('dispense de mutuelle (05/11/2026)', () => {
  it('propose les 7 motifs de D911-2 et R242-1-6', () => {
    expect(MOTIFS_DISPENSE_MUTUELLE.map((m) => m.code)).toEqual([
      'couverture_collective',
      'css',
      'assurance_individuelle',
      'cdd_moins_12_mois',
      'cdd_12_mois_et_plus',
      'temps_partiel_10_pourcent',
      'anterieur_decision_unilaterale',
    ]);
    // Les quatre motifs de R242-1-6 seuls ne valent que si l'acte les prévoit.
    expect(MOTIFS_DISPENSE_MUTUELLE.filter((m) => m.selonActe).map((m) => m.code)).toEqual([
      'cdd_moins_12_mois',
      'cdd_12_mois_et_plus',
      'temps_partiel_10_pourcent',
      'anterieur_decision_unilaterale',
    ]);
  });

  it('une fiche sans dispense donne un formulaire vide', () => {
    expect(dispenseVersFormulaire(undefined)).toEqual(DISPENSE_VIDE);
    expect(dispenseVersFormulaire(null)).toEqual(DISPENSE_VIDE);
  });

  it('aller-retour fiche → formulaire → fiche', () => {
    const fiche = {
      motif: 'couverture_collective',
      demande_recue_le: '2026-08-01',
      justificatif_recu_le: '2026-08-01',
      fin_le: null,
    };
    const formulaire = dispenseVersFormulaire(fiche);
    expect(formulaire.active).toBe(true);
    expect(dispenseVersFiche(formulaire, false)).toEqual(fiche);
  });

  it('ne garde que la date utile au motif', () => {
    const formulaire = {
      active: true,
      motif: 'css',
      demande_recue_le: '2026-08-01',
      justificatif_recu_le: '2026-08-01',
      fin_le: '2027-01-31',
    };
    expect(dispenseVersFiche(formulaire, false)).toEqual({
      motif: 'css',
      demande_recue_le: '2026-08-01',
      justificatif_recu_le: null,
      fin_le: '2027-01-31',
    });
  });

  it('le justificatif vaut la date de la demande quand il est vide', () => {
    const formulaire = {
      ...DISPENSE_VIDE,
      active: true,
      motif: 'couverture_collective',
      demande_recue_le: '2026-08-01',
    };
    expect(dispenseVersFiche(formulaire, false)?.justificatif_recu_le).toBe('2026-08-01');
  });

  it('une formule choisie ou la case décochée effacent la dispense', () => {
    const formulaire = { ...DISPENSE_VIDE, active: true, motif: 'css', demande_recue_le: '2026-08-01' };
    expect(dispenseVersFiche(formulaire, true)).toBeNull();
    expect(dispenseVersFiche({ ...formulaire, active: false }, false)).toBeNull();
  });

  it('dit ce qui manque, champ par champ', () => {
    expect(problemesDispense({ ...DISPENSE_VIDE, active: true }).map((p) => p.champ)).toEqual([
      'motif',
      'demande_recue_le',
    ]);
    expect(
      problemesDispense({
        ...DISPENSE_VIDE,
        active: true,
        motif: 'assurance_individuelle',
        demande_recue_le: '2026-08-01',
      }).map((p) => p.champ),
    ).toEqual(['fin_le']);
    expect(
      problemesDispense({
        ...DISPENSE_VIDE,
        active: true,
        motif: 'couverture_collective',
        demande_recue_le: '2026-08-01',
      }),
    ).toEqual([]);
    expect(problemesDispense(DISPENSE_VIDE)).toEqual([]);
  });

  it('reprend une dispense du 25/10 (motif en toutes lettres) et garde ses notes', () => {
    const ancienne = {
      motif: 'CDD de moins de douze mois',
      depuis: '2026-09-14',
      fondement: 'Code de la sécurité sociale, art. R242-1-6, 2° b',
      decidee_le: '2026-10-25',
    };
    const formulaire = dispenseVersFormulaire(ancienne);
    expect(formulaire).toMatchObject({ active: true, motif: 'cdd_moins_12_mois', demande_recue_le: '' });
    expect(problemesDispense(formulaire).map((p) => p.champ)).toEqual(['demande_recue_le']);
    const fiche = dispenseVersFiche({ ...formulaire, demande_recue_le: '2026-09-14' }, false, ancienne);
    expect(fiche).toEqual({
      depuis: '2026-09-14',
      fondement: 'Code de la sécurité sociale, art. R242-1-6, 2° b',
      decidee_le: '2026-10-25',
      motif: 'cdd_moins_12_mois',
      demande_recue_le: '2026-09-14',
      justificatif_recu_le: null,
      fin_le: null,
    });
  });
});
