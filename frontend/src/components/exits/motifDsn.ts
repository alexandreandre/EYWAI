// Motif de fin de contrat déclaré en DSN : ce que dit le dossier de sortie.
import type { MotifDsnDossier } from '@/api/employeeExits';

/** Valeur spéciale du menu : laisser Martine proposer. */
export const MOTIF_PROPOSE = 'propose';

/** La phrase affichée sous le choix : ce qui part en DSN, ou ce qu'il reste à faire. */
export function phraseMotifDsn(motif: MotifDsnDossier): string {
  if (motif.alerte) return motif.alerte;
  if (!motif.retenu) return 'Aucun motif DSN : cette sortie n’en déclare pas.';
  const libelle = motif.options.find((o) => o.code === motif.retenu)?.libelle;
  const suffixe = libelle ? ` (${libelle})` : '';
  return motif.choisi
    ? `Déclaré en DSN : ${motif.retenu}${suffixe}.`
    : `Proposé par Martine et déclaré en DSN : ${motif.retenu}${suffixe}.`;
}

/** Le choix affiché : le motif du dossier, sinon la proposition de Martine. */
export function valeurMotifDsn(motif: MotifDsnDossier): string {
  return motif.choisi ?? MOTIF_PROPOSE;
}
