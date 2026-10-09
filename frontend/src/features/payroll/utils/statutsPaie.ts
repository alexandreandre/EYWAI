/**
 * Statuts de salarié et paie. Le serveur ne génère un bulletin que pour un
 * salarié actif (`PAYROLL_ACTIVE_STATUSES`) : un salarié « En onboarding »
 * est refusé même avec une fiche complète, tant qu'il n'est pas passé en Actif.
 */

const LIBELLES: Record<string, string> = {
  actif: 'Actif',
  active: 'Actif',
  en_onboarding: 'En onboarding',
  en_sortie: 'En départ',
  parti: 'Parti',
  suspendu: 'Suspendu',
  demissionnaire: 'Démissionnaire',
};

export function libelleStatutSalarie(statut: string | null | undefined): string {
  return LIBELLES[(statut ?? 'actif').toLowerCase()] ?? 'Statut inconnu';
}

export function statutPermetLaPaie(statut: string | null | undefined): boolean {
  const cle = (statut ?? 'actif').toLowerCase();
  return cle === 'actif' || cle === 'active';
}

export const MESSAGE_STATUTS_PRIS_EN_COMPTE =
  'Seul le statut Actif permet de générer un bulletin. Un collaborateur En onboarding doit d’abord être passé en Actif sur sa fiche.';
