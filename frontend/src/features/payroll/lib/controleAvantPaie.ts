/**
 * Contrôles avant paie : une vérification en panne ne vaut pas « rien à signaler ».
 *
 * Quand une requête de contrôle échoue, ses compteurs retombent à zéro : sans
 * garde, l'écran affichait alors « tout va bien » et le verrou « Lancer la
 * paie » s'ouvrait (constat C1 de l'audit du 25/09). Décision : rendre la panne
 * visible, sans bloquer durement la paie — la gestionnaire peut réessayer, ou
 * générer quand même après une confirmation explicite.
 */

import type { PreflightAnomaly } from '@/api/payrollPreflight';
import { countOpenBlockingAnomalies } from '@/features/payroll/components/preflightLabels';
import type { Lecture } from '@/features/payroll/utils/listeControleMois';

export const MESSAGE_GENERER_SANS_CONTROLE =
  "Le contrôle avant paie n'a pas pu être vérifié. Générer quand même ?";

/**
 * Message de confirmation à montrer avant de générer, ou `null` s'il n'y a
 * rien à confirmer. Un contrôle en erreur se confirme toujours ; un contrôle
 * qui répond garde la règle d'avant (confirmation dès une anomalie bloquante
 * ouverte).
 */
export function messageConfirmationGeneration({
  controleEnErreur,
  anomalies,
}: {
  controleEnErreur: boolean;
  anomalies: PreflightAnomaly[];
}): string | null {
  if (controleEnErreur) return MESSAGE_GENERER_SANS_CONTROLE;
  const bloquantes = countOpenBlockingAnomalies(anomalies);
  if (bloquantes > 0) {
    const anomalies = bloquantes > 1 ? 'anomalies bloquantes ouvertes' : 'anomalie bloquante ouverte';
    return `${bloquantes} ${anomalies}. Générer quand même les bulletins ?`;
  }
  return null;
}

/** Un job du lancement groupé (même forme que celui de `usePayrollGeneration`). */
export type JobDuLancement = {
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  forceCalendrierIncomplet?: true;
};

function nomsResumes(noms: string[]): string {
  if (noms.length <= 3) return noms.join(', ');
  return `${noms.slice(0, 3).join(', ')} et ${noms.length - 3} autres`;
}

/**
 * Lancement groupé : une seule confirmation, et c'est elle qui envoie le forçage.
 * Avant, la confirmation des anomalies partait sans drapeau ; le serveur refusait
 * les calendriers incomplets et une deuxième fenêtre redemandait (audit R1, geste 2).
 * Contrôle illisible : on confirme sans rien forcer, le serveur refusera et le dira.
 */
export function lancementGroupe({
  ids,
  nomDe,
  year,
  month,
  controleEnErreur,
  anomalies,
  calendriersIncomplets,
}: {
  ids: readonly string[];
  nomDe: (id: string) => string;
  year: number;
  month: number;
  controleEnErreur: boolean;
  anomalies: PreflightAnomaly[];
  /** Salariés au calendrier incomplet, selon le contrôle avant paie du mois. */
  calendriersIncomplets: Lecture<string[]> | undefined;
}): { confirmation: string | null; jobs: JobDuLancement[] } {
  const incomplets =
    !controleEnErreur && calendriersIncomplets?.statut === 'ok' ? new Set(calendriersIncomplets.valeur) : new Set<string>();
  const aForcer = ids.filter((id) => incomplets.has(id));
  const anomaliesBloquantes = messageConfirmationGeneration({ controleEnErreur, anomalies });

  let confirmation = anomaliesBloquantes;
  if (aForcer.length > 0) {
    const n = aForcer.length;
    const phrase =
      n > 1
        ? `${n} calendriers incomplets (${nomsResumes(aForcer.map(nomDe))}) : leurs bulletins seront générés malgré les jours à saisir.`
        : `1 calendrier incomplet (${nomDe(aForcer[0])}) : son bulletin sera généré malgré les jours à saisir.`;
    confirmation = anomaliesBloquantes ? `${phrase} ${anomaliesBloquantes}` : `${phrase} Générer quand même ?`;
  }

  const jobs = ids.map((employeeId) => ({
    employeeId,
    employeeName: nomDe(employeeId),
    year,
    month,
    ...(incomplets.has(employeeId) ? { forceCalendrierIncomplet: true as const } : {}),
  }));
  return { confirmation, jobs };
}

/**
 * État du verrou « Lancer la paie » :
 * - `verification` : les compteurs du parcours sont en cours de chargement ;
 * - `indisponible` : un compteur n'a pas pu être lu — on ne sait pas s'il reste
 *   des étapes, le verrou ne s'ouvre donc pas en silence ;
 * - `etapes_en_attente` : au moins une étape a des actions à traiter ;
 * - `ouvert` : toutes les étapes suivies sont à zéro.
 *
 * La panne passe avant les étapes en attente : ce qu'il faut d'abord, c'est
 * réessayer, sans quoi les compteurs affichés ne sont pas complets.
 */
export type EtatVerrouPaie = 'verification' | 'indisponible' | 'etapes_en_attente' | 'ouvert';

export function etatVerrouPaie({
  enChargement,
  enErreur,
  compteurs,
}: {
  enChargement: boolean;
  enErreur: boolean;
  compteurs: readonly number[];
}): EtatVerrouPaie {
  if (enChargement) return 'verification';
  if (enErreur) return 'indisponible';
  return compteurs.every((n) => n === 0) ? 'ouvert' : 'etapes_en_attente';
}

/** Les étapes en attente avertissent (comme la liste de préparation) mais n'interdisent rien. */
export function peutLancerLaPaie(etat: EtatVerrouPaie): boolean {
  return etat === 'ouvert' || etat === 'etapes_en_attente';
}

export const AVERTISSEMENT_ETAPES_EN_ATTENTE =
  'Vous pouvez lancer la paie, mais vérifiez ces points en amont.';

export function titreBoutonLancerLaPaie(etat: EtatVerrouPaie): string {
  if (etat === 'verification') return 'Vérification du parcours de préparation…';
  if (etat === 'etapes_en_attente') return AVERTISSEMENT_ETAPES_EN_ATTENTE;
  return 'Lancer la paie';
}
