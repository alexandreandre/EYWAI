/**
 * Données de la fiche que seule la DSN déclare, codes du cahier technique
 * DSN 2026 (P26). Rangées sous `specificites_paie.dsn_reprise`, là où le
 * chargeur de reprise pose celles des salariés repris.
 */

export type CodeDsn = { code: string; libelle: string };

/**
 * Motif de recours d'un CDD (S21.G00.40.021). Les codes 11 (apprentissage ou
 * mission), 14 (contrat d'engagement maritime) et 15 (intérim) sont refusés
 * pour un CDD de droit privé (CCH-12, CCH-13) : ils ne sont pas proposés.
 */
export const MOTIFS_RECOURS_CDD: readonly CodeDsn[] = [
  { code: '01', libelle: "Remplacement d'un salarié" },
  { code: '02', libelle: "Accroissement temporaire de l'activité" },
  { code: '03', libelle: 'Emploi à caractère saisonnier' },
  { code: '04', libelle: 'Contrat vendanges' },
  { code: '05', libelle: "Contrat d'usage" },
  { code: '06', libelle: 'CDD à objet défini' },
  { code: '07', libelle: "Remplacement d'un chef d'entreprise" },
  { code: '08', libelle: "Remplacement d'un chef d'exploitation agricole" },
  { code: '09', libelle: 'Recrutement de personnes sans emploi en difficulté' },
  { code: '10', libelle: 'Complément de formation professionnelle' },
  { code: '12', libelle: "Remplacement d'un salarié passé à temps partiel" },
  { code: '13', libelle: 'Attente de la suppression définitive du poste' },
];

/** Niveau de diplôme préparé par un apprenti (S21.G00.30.025). */
export const NIVEAUX_DIPLOME_PREPARE: readonly CodeDsn[] = [
  { code: '03', libelle: 'CAP ou BEP' },
  { code: '04', libelle: 'Bac, brevet de technicien ou brevet professionnel' },
  { code: '05', libelle: 'Bac +2 (BTS, BUT/DUT, licence 2)' },
  { code: '06', libelle: 'Bac +3 ou +4 (licence, licence pro, master 1)' },
  { code: '07', libelle: "Bac +5 (master 2, diplôme d'ingénieur)" },
  { code: '08', libelle: 'Bac +8 (doctorat)' },
];

/** Code PCS-ESE (S21.G00.40.004) : trois chiffres et une lettre minuscule. */
export const FORMAT_PCS_ESE = /^\d{3}[a-z]$/;
