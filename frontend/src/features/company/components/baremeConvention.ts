/**
 * Choix du barème de la convention dans la carte « Maintien de salaire »
 * (conception du 24/10/2026).
 *
 * « Aucun » : les réglages manuels, au centime comme avant. Un barème : ses
 * paliers s'appliquent, et les champs qu'il remplace disparaissent de l'écran.
 * Jamais un champ à l'écran que le moteur ignore.
 */
import type { BaremeConvention, MaintenanceSettings } from '@/api/maintenanceSettings';

export const AUCUN_BAREME = 'aucun';

export const CHOIX_BAREME: ReadonlyArray<{
  valeur: string;
  libelle: string;
  code: BaremeConvention | null;
}> = [
  { valeur: AUCUN_BAREME, libelle: 'Aucun : les réglages ci-dessous', code: null },
  { valeur: 'plasturgie_0292', libelle: 'Plasturgie (IDCC 0292)', code: 'plasturgie_0292' },
];

export const AIDE_BAREME =
  "Un barème tout fait applique les paliers de la convention : taux, durées selon le statut et l'ancienneté, carence et limites. Revenir à « Aucun » rend les réglages manuels, qui ne sont pas effacés.";

export const TEXTE_LEGAL_SOUS_BAREME =
  'Avec le barème, Martine compare chaque mois avec le maintien légal et verse le plus favorable.';

export const TEXTE_STATUT_CADRE =
  'Le statut cadre se lit sur la fiche du salarié ; une fiche sans statut est lue non-cadre.';

/** Champs que le barème remplace : ils disparaissent quand un barème est choisi. */
export const CHAMPS_REMPLACES_PAR_LE_BAREME: ReadonlyArray<keyof MaintenanceSettings> = [
  'apply_legal_maintenance',
  'min_seniority_months',
  'min_seniority_months_at_mp',
  'employer_waiting_days',
  'remove_employer_waiting',
  'annual_unique_waiting',
  'maintain_100_percent',
  'differentiated_at_illness',
  'no_seniority_condition',
  'paid_waiting_days_per_year',
  'paid_waiting_min_seniority_months',
  'custom_duration_days',
];

export function texteRegleParLeBareme(libelle: string): string {
  return `Réglé par le barème ${libelle}.`;
}

export function champVisible(
  cle: keyof MaintenanceSettings,
  form: Pick<MaintenanceSettings, 'bareme_convention'>,
): boolean {
  return !form.bareme_convention || !CHAMPS_REMPLACES_PAR_LE_BAREME.includes(cle);
}

export function choixBaremeDepuisReglage(code: BaremeConvention | null | undefined): string {
  return code ?? AUCUN_BAREME;
}

/** Le code à enregistrer ; undefined pour une valeur inconnue. */
export function reglageDepuisChoixBareme(valeur: string): BaremeConvention | null | undefined {
  const choix = CHOIX_BAREME.find((c) => c.valeur === valeur);
  return choix ? choix.code : undefined;
}

/** Le barème affiché n'est pas celui qui est enregistré. */
export function baremeModifie(
  form: Pick<MaintenanceSettings, 'bareme_convention'>,
  enregistre: Pick<MaintenanceSettings, 'bareme_convention'> | undefined,
): boolean {
  return Boolean(enregistre) && (form.bareme_convention ?? null) !== (enregistre?.bareme_convention ?? null);
}
