import type { HrDeadlineCandidate } from '@/api/hrDeadlineReminders';
import { pluriel } from '@/lib/pluriel';

/** Ce que compte le décompte « Échéances » : dit en toutes lettres, titres de séjour compris. */
export const TITRE_ECHEANCES =
  'Échéances : fins de CDD et de stage, périodes d’essai (15 jours), titres de séjour (30 jours, ou déjà expirés)';

export function messageEcheances(nombre: number): string {
  return nombre === 0 ? 'Aucune échéance à venir.' : `${pluriel(nombre, 'salarié')} à traiter.`;
}

/**
 * Les titres de séjour déjà expirés, à montrer en tête du bandeau ([D6-4],
 * 12/10/2026) : un titre expiré n'apparaissait nulle part en mode paie.
 */
export function lignesTitresExpires(
  candidats: HrDeadlineCandidate[] | null | undefined,
): { employee_id: string; texte: string }[] {
  return (candidats ?? [])
    .filter((c) => c.reminder_type === 'residence_permit' && c.days_remaining < 0)
    .sort((a, b) => a.days_remaining - b.days_remaining)
    .map((c) => {
      const [annee, mois, jour] = c.deadline.slice(0, 10).split('-');
      return {
        employee_id: c.employee_id,
        texte: `Expiré : ${`${c.first_name} ${c.last_name}`.trim()} — titre de séjour expiré le ${jour}/${mois}/${annee}`,
      };
    });
}
