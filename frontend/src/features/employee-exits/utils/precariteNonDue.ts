/**
 * Fin de CDD : « Prime de précarité non due » et son motif.
 *
 * Les cas de la fiche service-public F40 « Fin d'un contrat à durée déterminée
 * (CDD) » et la rupture anticipée à l'initiative du salarié (Code du travail,
 * L1243-10, 4°). Rangé dans `exit_notes.precarite_non_due` ; mêmes codes que le
 * serveur (backend/app/modules/payroll/engine/precarite_non_due.py). Le bulletin
 * de sortie ne verse pas la prime ; le solde de tout compte et l'attestation
 * France Travail disent pourquoi.
 */
export type MotifPrecariteNonDue =
  | 'embauche_cdi'
  | 'refus_cdi'
  | 'rupture_anticipee_salarie'
  | 'faute_grave'
  | 'force_majeure'
  | 'cdd_usage'
  | 'contrat_aide'
  | 'complement_formation'
  | 'jeune_vacances'
  | 'saisonnier';

export const LIBELLE_PRECARITE_NON_DUE = 'Prime de précarité non due';

export const OPTIONS_MOTIF_PRECARITE_NON_DUE: { value: MotifPrecariteNonDue; label: string }[] = [
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
];

export const AIDE_PRECARITE_NON_DUE =
  "Le bulletin de sortie ne verse pas la prime ; le solde de tout compte et l'attestation France " +
  'Travail disent pourquoi (Code du travail, L1243-8 et L1243-10 ; fiche service-public F40).';

export const MESSAGE_MOTIF_PRECARITE_MANQUANT =
  "Indiquez pourquoi la prime de précarité n'est pas due : le solde de tout compte et l'attestation France Travail le disent.";

const CODES = new Set<string>(OPTIONS_MOTIF_PRECARITE_NON_DUE.map((o) => o.value));

/** Le motif rangé dans le départ, s'il est l'un des cas connus. */
export function motifPrecariteNonDue(
  exitNotes: Record<string, unknown> | null | undefined
): MotifPrecariteNonDue | null {
  const motif = exitNotes?.precarite_non_due;
  return typeof motif === 'string' && CODES.has(motif) ? (motif as MotifPrecariteNonDue) : null;
}
