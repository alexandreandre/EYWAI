/**
 * Exports à refaire : un bulletin du mois recalculé, supprimé ou ajouté après
 * un export laisse le fichier sorti faux. Le serveur le dit (`a_refaire`) ;
 * l'écran Exports l'écrit sur la ligne de l'export, et le bandeau du bulletin
 * nomme les exports concernés.
 */

import type { ExportDuMois } from '@/api/payslips';

export const LIBELLE_EXPORT_A_REFAIRE = 'Bulletins modifiés depuis cet export : à refaire';

export type BandeauExportsDuMois = { titre: string; texte: string; aRefaire: boolean };

export function bandeauExportsDuMois(
  exports: ExportDuMois[],
  date: (iso: string) => string
): BandeauExportsDuMois | null {
  if (exports.length === 0) return null;
  const nommer = (liste: ExportDuMois[]) => liste.map((e) => `${e.libelle} (${date(e.date)})`).join(' · ');
  const aRefaire = exports.filter((e) => e.a_refaire === true);
  const aJour = exports.filter((e) => e.a_refaire !== true);
  if (aRefaire.length === 0) {
    return {
      titre: 'Déjà exporté pour ce mois',
      texte: `${nommer(aJour)}. Après une correction, refaites ces exports.`,
      aRefaire: false,
    };
  }
  const phrases = [`Bulletins modifiés depuis ces exports : ${nommer(aRefaire)}. Refaites-les.`];
  if (aJour.length > 0) phrases.push(`À jour : ${nommer(aJour)}.`);
  return { titre: 'Exports à refaire', texte: phrases.join(' '), aRefaire: true };
}
