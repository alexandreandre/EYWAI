import { describe, expect, it } from 'vitest';

import { MOTIFS_RECOURS_CDD, NIVEAUX_DIPLOME_PREPARE } from '@/constants/dsnFiche';
import { employeeProfileEditSchema } from '@/features/employee-detail/components/employeeProfileEditSchema';
import {
  buildDefaultValues,
  buildUpdatePayload,
} from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { Employee } from '@/features/employee-detail/types';

/** Reprise posée par le chargeur DSN : rien ne doit s'en perdre à l'enregistrement. */
const repriseChargee = {
  pas_type: '01',
  pas_identifiant: '123456789',
  smic_retenu: '1801.80',
};
const affiliations = [{ id_affiliation: '1', id_contrat: '2', option: 'ISO', population: '00' }];

function fiche(surcharges: Partial<Employee> & Record<string, unknown> = {}): Employee {
  return {
    id: 'e-fictif',
    first_name: 'Lucie',
    last_name: 'Imaginaire',
    contract_type: 'CDD',
    contract_end_date: '2027-02-28',
    statut: 'Non-Cadre',
    hire_date: '2026-09-01',
    specificites_paie: {
      mutuelle: { adhesion: true, mutuelle_type_ids: ['m1'] },
      prevoyance: { adhesion: false },
      affiliations_psc: affiliations,
      dsn_reprise: repriseChargee,
    },
    ...surcharges,
  } as Employee;
}

describe('motif de recours et niveau de diplôme sur la fiche', () => {
  it('relit ce que la fiche porte déjà', () => {
    const valeurs = buildDefaultValues(
      fiche({
        specificites_paie: { dsn_reprise: { motif_recours: '02', niveau_diplome_prepare: '05' } },
      }),
    );
    expect(valeurs.specificites_paie.dsn_reprise).toEqual({
      motif_recours: '02',
      niveau_diplome_prepare: '05',
    });
  });

  it('un CDD enregistre son motif sans rien perdre de la reprise ni des affiliations', () => {
    const employe = fiche();
    const valeurs = buildDefaultValues(employe);
    valeurs.specificites_paie.dsn_reprise = { motif_recours: '02', niveau_diplome_prepare: '' };
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.specificites_paie?.dsn_reprise).toEqual({ ...repriseChargee, motif_recours: '02' });
    expect(payload.specificites_paie?.affiliations_psc).toEqual(affiliations);
  });

  it('un apprenti enregistre son niveau de diplôme préparé', () => {
    const employe = fiche({ contract_type: 'Apprentissage' });
    const valeurs = buildDefaultValues(employe);
    valeurs.specificites_paie.dsn_reprise = { motif_recours: '', niveau_diplome_prepare: '05' };
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.specificites_paie?.dsn_reprise).toEqual({
      ...repriseChargee,
      niveau_diplome_prepare: '05',
    });
  });

  it('un champ masqué (CDI) ne touche pas la reprise', () => {
    const employe = fiche({
      contract_type: 'CDI',
      specificites_paie: { dsn_reprise: { ...repriseChargee, motif_recours: '01' } },
    });
    const valeurs = buildDefaultValues(employe);
    valeurs.specificites_paie.dsn_reprise = { motif_recours: '', niveau_diplome_prepare: '06' };
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.specificites_paie?.dsn_reprise).toEqual({ ...repriseChargee, motif_recours: '01' });
  });

  it('vider le motif d’un CDD l’efface (null, le serveur fusionne)', () => {
    const employe = fiche({
      specificites_paie: { dsn_reprise: { ...repriseChargee, motif_recours: '01' } },
    });
    const valeurs = buildDefaultValues(employe);
    valeurs.specificites_paie.dsn_reprise = { motif_recours: '', niveau_diplome_prepare: '' };
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.specificites_paie?.dsn_reprise).toEqual({ ...repriseChargee, motif_recours: null });
  });

  it('une fiche sans reprise ni saisie ne reçoit pas de reprise vide', () => {
    const employe = fiche({ specificites_paie: { mutuelle: { adhesion: false } } });
    const payload = buildUpdatePayload(buildDefaultValues(employe), employe);
    expect(payload.specificites_paie).not.toHaveProperty('dsn_reprise');
  });

  it('les listes viennent du cahier technique, sans les codes interdits pour un CDD', () => {
    const motifs = MOTIFS_RECOURS_CDD.map((m) => m.code);
    expect(motifs).toEqual(['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '12', '13']);
    expect(NIVEAUX_DIPLOME_PREPARE.map((n) => n.code)).toEqual(['03', '04', '05', '06', '07', '08']);
  });
});

describe('code PCS-ESE sur la fiche', () => {
  const classificationDsn = {
    pcs: '674a',
    idcc: '0292',
    coefficient: 700,
    code_statut_dsn: '06',
    numero_contrat_dsn: '00004',
  };

  it('se relit depuis la classification', () => {
    const valeurs = buildDefaultValues(fiche({ classification_conventionnelle: classificationDsn }));
    expect(valeurs.code_pcs).toBe('674a');
  });

  it('se fusionne dans la classification sans rien perdre', () => {
    const employe = fiche({ classification_conventionnelle: classificationDsn });
    const valeurs = buildDefaultValues(employe);
    valeurs.code_pcs = '381b';
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.classification_conventionnelle).toEqual({ ...classificationDsn, pcs: '381b' });
  });

  it('se pose sur une fiche sans convention ni classification', () => {
    const employe = fiche({ classification_conventionnelle: null, collective_agreement_id: null });
    const valeurs = buildDefaultValues(employe);
    valeurs.code_pcs = '674a';
    const payload = buildUpdatePayload(valeurs, employe);
    expect(payload.classification_conventionnelle).toEqual({ pcs: '674a' });
  });

  it('inchangé et sans convention, la classification n’est pas envoyée', () => {
    const employe = fiche({ classification_conventionnelle: classificationDsn, collective_agreement_id: null });
    const payload = buildUpdatePayload(buildDefaultValues(employe), employe);
    expect(payload).not.toHaveProperty('classification_conventionnelle');
  });

  it('se valide au format PCS-ESE : trois chiffres et une lettre minuscule', () => {
    const champ = employeeProfileEditSchema.innerType().shape.code_pcs;
    expect(champ.safeParse('674a').success).toBe(true);
    expect(champ.safeParse('').success).toBe(true);
    expect(champ.safeParse('674A').success).toBe(false);
    expect(champ.safeParse('67a').success).toBe(false);
    expect(champ.safeParse('6741').success).toBe(false);
  });
});
