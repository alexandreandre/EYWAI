import { describe, expect, it } from 'vitest';
import {
  AIDE_PRECARITE_NON_DUE,
  LIBELLE_PRECARITE_NON_DUE,
  MESSAGE_MOTIF_PRECARITE_MANQUANT,
  OPTIONS_MOTIF_PRECARITE_NON_DUE,
  motifPrecariteNonDue,
} from './precariteNonDue';

// Fiche service-public F40 « Fin d'un contrat à durée déterminée (CDD) » (ouverte
// le 12/10/2026) : les cas où l'indemnité de fin de contrat n'est pas due ; et
// Code du travail L1243-10, 4° : rupture anticipée à l'initiative du salarié.
// Mêmes codes que le serveur (payroll/engine/precarite_non_due.py).
describe('fin de CDD : prime de précarité non due', () => {
  it('la case dit de quoi il s’agit', () => {
    expect(LIBELLE_PRECARITE_NON_DUE).toBe('Prime de précarité non due');
  });

  it('propose les motifs de la fiche F40 et la rupture anticipée par le salarié', () => {
    expect(OPTIONS_MOTIF_PRECARITE_NON_DUE).toEqual([
      { value: 'embauche_cdi', label: "Embauche en CDI à l'issue du CDD" },
      {
        value: 'refus_cdi',
        label:
          "Refus d'un CDI proposé pour le même emploi ou un emploi similaire, avec une rémunération au moins équivalente",
      },
      { value: 'rupture_anticipee_salarie', label: "Rupture anticipée du CDD à l'initiative du salarié" },
      { value: 'faute_grave', label: 'Faute grave' },
      { value: 'force_majeure', label: 'Force majeure' },
      { value: 'cdd_usage', label: "CDD d'usage" },
      {
        value: 'contrat_aide',
        label: "Contrat aidé (CUI-PEC, contrat de professionnalisation, contrat d'apprentissage)",
      },
      {
        value: 'complement_formation',
        label: "Contrat avec un complément de formation professionnelle assuré par l'employeur",
      },
      {
        value: 'jeune_vacances',
        label: 'Contrat conclu avec un jeune pendant ses vacances scolaires ou universitaires',
      },
      { value: 'saisonnier', label: 'Contrat saisonnier' },
    ]);
  });

  it('l’aide dit ce que la case change', () => {
    expect(AIDE_PRECARITE_NON_DUE).toContain('bulletin de sortie');
    expect(AIDE_PRECARITE_NON_DUE).toContain('solde de tout compte');
    expect(AIDE_PRECARITE_NON_DUE).toContain('attestation France Travail');
    expect(MESSAGE_MOTIF_PRECARITE_MANQUANT).toBe(
      "Indiquez pourquoi la prime de précarité n'est pas due : le solde de tout compte et l'attestation France Travail le disent."
    );
  });

  it('lit le motif rangé dans le départ, et rien d’autre', () => {
    expect(motifPrecariteNonDue({ precarite_non_due: 'refus_cdi' })).toBe('refus_cdi');
    expect(motifPrecariteNonDue({ precarite_non_due: 'inconnu' })).toBeNull();
    expect(motifPrecariteNonDue({})).toBeNull();
    expect(motifPrecariteNonDue(null)).toBeNull();
  });
});
