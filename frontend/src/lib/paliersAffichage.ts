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

/** « 6,7 % », « 21,84 % », « 22 % » : sans zéro inutile. */
function pourcentCourt(taux: number): string {
  const valeur = Math.round(taux * 10000) / 100;
  return `${String(valeur).replace('.', ',')} %`;
}

/** La conversion des IJSS sous un barème qui garantit le net (conception du 03/11/2026). */
export function phraseGarantieNette(garantie: NonNullable<MaintenancePreview['maintien']['garantie_nette']>): string {
  const sens = garantie.reduction >= 0 ? 'réduit' : 'augmenté';
  return (
    `Garantie du net : les IJSS (${eurosFr(garantie.ijss_deduites)}) sont comptées nettes de CSG et CRDS ` +
    `(${pourcentCourt(garantie.taux_ijss)}), puis ramenées au brut avec ${pourcentCourt(garantie.taux_salarial)} ` +
    `de cotisations salariales. Maintien ${sens} de ${eurosFr(Math.abs(garantie.reduction))}.`
  );
}

/** Le plafond au net sous un barème qui borne le maintien (métallurgie, 03/11/2026). */
export function phrasePlafondNet(plafond: NonNullable<MaintenancePreview['maintien']['plafond_net']>): string {
  return (
    `Plafond au net : le maintien ne peut pas dépasser le net que le salarié aurait perçu. ` +
    `Les IJSS (${eurosFr(plafond.ijss_deduites)}) sont comptées nettes de CSG et CRDS ` +
    `(${pourcentCourt(plafond.taux_ijss)}), puis ramenées au brut avec ${pourcentCourt(plafond.taux_salarial)} ` +
    `de cotisations salariales. Maintien réduit de ${eurosFr(Math.abs(plafond.reduction))}.`
  );
}

export function lignesDesPaliers(maintien: MaintenancePreview['maintien']): string[] {
  const lignes = (maintien.paliers ?? []).map((p) => ligneDuPalier(p, Boolean(maintien.paliers_en_jours_ouvres)));
  if (!lignes.length) return lignes;
  if (maintien.garantie_nette) return [...lignes, phraseGarantieNette(maintien.garantie_nette)];
  if (maintien.plafond_net) return [...lignes, phrasePlafondNet(maintien.plafond_net)];
  return lignes;
}
