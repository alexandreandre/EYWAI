/**
 * Textes du suivi IJSS et du maintien pour un arrêt sans subrogation.
 *
 * Le calcul est fait par le serveur : ces textes disent seulement ce qu'il a
 * posé sur le bulletin (part déduite du maintien, montant venu du suivi) et le
 * réglage de la société.
 */
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
