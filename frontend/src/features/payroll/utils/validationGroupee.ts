/**
 * « Valider les bulletins prêts » : la vue par mois valide en une fois ce qui
 * n'a rien à revoir. Le serveur repasse chaque bulletin par la règle de
 * validation d'un seul (à recalculer, à régénérer, alerte critique) et rend
 * ses refus avec leur raison (revue du 05/10 : valider un par un coûtait
 * 75 à 100 clics par mois).
 */

import { estBulletinImporte } from './bulletinImporte';
import { estARevoir, type LigneDuMois } from './revueDuMois';

export type ResultatValidationGroupee = {
  valides: string[];
  refus: Array<{ payslip_id: string; raison: string }>;
};

export type RefusNomme = { payslipId: string; nom: string; raison: string };

export const NOM_BULLETIN_INCONNU = 'Bulletin inconnu';

/** Généré, calculé par MARTINE, pas encore validé, et rien à revoir. */
export function estPretAValider(ligne: LigneDuMois): boolean {
  const bulletin = ligne.bulletin;
  if (ligne.statut !== 'success' || !bulletin) return false;
  if (estBulletinImporte(bulletin) || bulletin.status === 'valide') return false;
  return !estARevoir(ligne);
}

export function libelleBoutonValider(n: number): string {
  return `Valider les bulletins prêts (${n})`;
}

function bulletins(n: number, participe: string): string {
  return n > 1 ? `${n} bulletins ${participe}s` : `${n} bulletin ${participe}`;
}

export function resumeValidationGroupee(
  resultat: ResultatValidationGroupee,
  nomParBulletin: Readonly<Record<string, string>>
): { titre: string; refus: RefusNomme[] } {
  const nValides = resultat.valides.length;
  const nRefus = resultat.refus.length;
  const valides = nValides > 0 ? bulletins(nValides, 'validé') : 'Aucun bulletin validé';
  const titre =
    nRefus === 0
      ? `${valides}.`
      : `${valides}, ${nRefus} refusé${nRefus > 1 ? 's' : ''} : ouvrez-${nRefus > 1 ? 'les' : 'le'} pour corriger.`;
  return {
    titre,
    refus: resultat.refus.map((r) => ({
      payslipId: r.payslip_id,
      nom: nomParBulletin[r.payslip_id] ?? NOM_BULLETIN_INCONNU,
      raison: r.raison,
    })),
  };
}
