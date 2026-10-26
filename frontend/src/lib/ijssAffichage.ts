/**
 * Textes du suivi IJSS et du maintien pour un arrêt sans subrogation.
 *
 * Le calcul est fait par le serveur : ces textes disent seulement ce qu'il a
 * posé sur le bulletin (part déduite du maintien, montant venu du suivi) et le
 * réglage de la société.
 */
import { formatTauxFr } from '@/lib/employeeAbsencesUtils';
import { pluriel } from '@/lib/pluriel';

/** Libellé du montant d'IJSS dans la fiche d'une ligne du suivi. */
export function libelleIjssDuPanneau(subrogationActive: boolean): string {
  return subrogationActive ? 'IJSS bulletin (subrogées)' : 'IJSS versées au salarié par la CPAM';
}

/** « Déduites du maintien : 687,12 € (19 jours maintenus) », ou rien sans déduction. */
export function phraseDeduitesDuMaintien(
  row: { ijss_deduites?: number | null; nb_jours_maintenus?: number | null },
  eur: (n: number) => string,
): string | null {
  const deduites = Number(row.ijss_deduites ?? 0);
  if (!(deduites > 0)) return null;
  const jours = Number(row.nb_jours_maintenus ?? 0);
  const base = `Déduites du maintien : ${eur(deduites)}`;
  if (!(jours > 0)) return base;
  return `${base} (${pluriel(jours, 'jour')} ${jours < 2 ? 'maintenu' : 'maintenus'})`;
}

/** Un montant appliqué qui ne change plus le bulletin. */
export function phraseAppliqueSansEffet(): string {
  return 'Appliqué, sans effet : la société verse le garanti en entier';
}

/**
 * La ligne qui relie le salaire journalier de base à l'indemnité : les 21 %
 * forfaitaires d'un congé de maternité, de paternité ou d'adoption (CSS
 * R331-5), ou un plafond. `null` quand le salaire journalier est retenu tel
 * quel ou que le serveur ne le dit pas.
 */
export function phraseSalaireJournalierRetenu(
  ijss: {
    salaire_journalier_base?: number | null;
    base_plafonnee?: number | null;
    taux_forfaitaire_retire?: number | null;
  },
  eur: (n: number) => string,
): string | null {
  const retenu = Number(ijss.base_plafonnee ?? 0);
  if (!(retenu > 0)) return null;
  const taux = Number(ijss.taux_forfaitaire_retire ?? 0);
  if (taux > 0) return `Moins ${formatTauxFr(taux)} forfaitaires : ${eur(retenu)} par jour`;
  if (retenu < Number(ijss.salaire_journalier_base ?? 0) - 0.005) {
    return `Retenu dans la limite du plafond : ${eur(retenu)} par jour`;
  }
  return null;
}

/** Détail du maintien : le montant d'IJSS vient du suivi, ou de l'estimation de Martine. */
export function libelleIjssDuDetail(montantDuSuivi: boolean | undefined): string {
  return montantDuSuivi ? 'IJSS validées (suivi IJSS)' : 'IJSS estimées';
}

/**
 * Pliant « Maintien & subrogation » : ce que fait le réglage de la société.
 * `null` quand le réglage n'est pas connu : mieux vaut se taire que se tromper.
 */
export function texteDeductionDuPliant(
  subrogationActive: boolean,
  deduireIjssSansSubrogation: boolean | undefined,
): string | null {
  if (subrogationActive) return 'Déduit du maintien applicable';
  if (deduireIjssSansSubrogation === undefined) return null;
  return deduireIjssSansSubrogation
    ? 'IJSS déduites du maintien (réglage de la société)'
    : 'Aucune déduction : salaire garanti versé en entier (réglage de la société)';
}
