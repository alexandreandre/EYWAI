/**
 * Les paliers du maintien sous le barème de la convention, tels que le détail
 * du bulletin et l'aperçu de l'absence les montrent (conception du 24/10/2026).
 *
 * Le calcul est fait par le serveur : ces textes disent seulement les paliers
 * qu'il a posés. Sans barème, il n'y en a pas, et rien ne s'affiche.
 */
import type { MaintenancePreview, PalierDuMaintien } from '@/api/absences';
import { pluriel } from '@/lib/pluriel';

export function eurosFr(n: number): string {
  const [entier, decimales] = Math.abs(n).toFixed(2).split('.');
  const groupes = entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${n < 0 ? '-' : ''}${groupes},${decimales} €`;
}

export function pourcentFr(taux: number): string {
  const valeur = Math.round(taux * 10000) / 100;
  return Number.isInteger(valeur) ? `${valeur} %` : `${valeur.toFixed(2).replace('.', ',')} %`;
}

function dateFr(iso: string): string {
  const [, mois, jour] = iso.split('-');
  return `${jour}/${mois}`;
}

function joursDuPalier(n: number, ouvres: boolean): string {
  return ouvres ? pluriel(n, 'jour ouvré', 'jours ouvrés') : pluriel(n, 'jour');
}

/** « Du 01/07 au 02/07 : 2 jours ouvrés à 100 % — 194,04 € (IJSS déduites 82,38 €) ». */
export function ligneDuPalier(palier: PalierDuMaintien, enJoursOuvres: boolean): string {
  const texte =
    `Du ${dateFr(palier.du)} au ${dateFr(palier.au)} : ` +
    `${joursDuPalier(palier.jours, enJoursOuvres)} à ${pourcentFr(palier.taux)} — ${eurosFr(palier.garanti)}`;
  return palier.ijss_deduites ? `${texte} (IJSS déduites ${eurosFr(palier.ijss_deduites)})` : texte;
}

/** Le titre de la section, ou null sans barème. */
export function titreDesPaliers(maintien: MaintenancePreview['maintien']): string | null {
  if (!maintien.paliers || !maintien.bareme_detail) return null;
  return maintien.regle_retenue === 'legal'
    ? 'Maintien légal, plus favorable ce mois-ci que le barème'
    : maintien.bareme_detail;
}

export function lignesDesPaliers(maintien: MaintenancePreview['maintien']): string[] {
  return (maintien.paliers ?? []).map((p) => ligneDuPalier(p, Boolean(maintien.paliers_en_jours_ouvres)));
}
