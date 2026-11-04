// Textes de la fenêtre « Mettre à jour les taux » (import des taux d'impôt).
// La DSN du mois vient en premier, comme dans la vidéo B.5 : la RH ne peut pas
// télécharger le compte rendu métier, net-entreprises l'affiche seulement à l'écran.

import type { PasApplication, PasSource } from '@/api/pasRates';
import { sanitizeBackendMessage } from '@/lib/errorMessages';

export const INTRO_IMPORT_PAS =
  "Déposez la DSN du mois : Martine y lit le taux d'impôt de chaque salarié. Rien n'est écrit tant que vous n'avez pas confirmé.";

export const SOURCES_IMPORT_PAS: { value: PasSource; label: string; aide: string }[] = [
  {
    value: 'dsn',
    label: 'DSN du mois',
    aide: 'Le fichier de la DSN mensuelle, tel que votre logiciel de paie l’a déposé.',
  },
  {
    value: 'crm',
    label: 'Compte rendu métier',
    aide: "Seulement si vous l'avez en fichier : net-entreprises l'affiche à l'écran, sans le proposer en téléchargement.",
  },
];

/**
 * Le bilan d'un import qui a des échecs : il reste dans la fenêtre au lieu de
 * disparaître avec le message éphémère, et dit la raison de chaque échec
 * (audit R1, geste 8). `null` : tout est appliqué, rien à garder.
 */
export function bilanImportPas(resultat: PasApplication): {
  titre: string;
  lignes: { salarie: string; raison: string }[];
  aide: string;
} | null {
  const n = resultat.echecs.length;
  if (n === 0) return null;
  return {
    titre: `${resultat.appliques} taux mis à jour, ${n} salarié${n > 1 ? 's' : ''} en échec`,
    lignes: resultat.echecs.map((e) => ({
      salarie: e.salarie,
      raison: sanitizeBackendMessage(e.erreur) ?? 'Raison non précisée par le serveur.',
    })),
    aide: `Période ${resultat.periode}. Corrigez ces taux à la main dans la liste, ou redéposez un fichier corrigé.`,
  };
}
