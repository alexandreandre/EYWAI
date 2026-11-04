import { moisDePaieAffiche, periodeDuMois, type MoisDePaie } from '@/features/payroll/utils/moisDePaie';

export interface OptionMois {
  value: string;
  label: string;
}

function optionDuMois(annee: number, mois0: number): OptionMois {
  const date = new Date(annee, mois0, 1);
  const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  return {
    value: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`,
    label: label.charAt(0).toUpperCase() + label.slice(1),
  };
}

/**
 * Mois proposés pour un export : sans année choisie, les 12 mois d'avant, le mois
 * en cours et les 2 suivants ; avec une année, ses douze mois (mois plus anciens).
 */
export function optionsDeMois(now: Date, annee: number | null): OptionMois[] {
  if (annee !== null) {
    return Array.from({ length: 12 }, (_, mois0) => optionDuMois(annee, mois0));
  }
  const options: OptionMois[] = [];
  for (let i = -12; i <= 2; i++) {
    options.push(optionDuMois(now.getFullYear(), now.getMonth() + i));
  }
  return options;
}

/** L'année en cours et les six précédentes, pour retrouver un mois plus ancien. */
export function anneesProposees(now: Date): number[] {
  return Array.from({ length: 7 }, (_, i) => now.getFullYear() - i);
}

/**
 * La période proposée à l'ouverture : le mois de paie, comme la Paie et le
 * Calendrier (le mois de l'adresse, sinon celui de l'écran précédent, sinon le
 * mois de paie du jour), et non le mois civil. Hors des mois récents, la liste
 * s'ouvre sur son année.
 */
export function periodeParDefaut(
  search: string | URLSearchParams,
  retenu: MoisDePaie | null,
  now: Date,
): { periode: string; annee: number | null } {
  const mois = moisDePaieAffiche(search, retenu, now);
  const periode = periodeDuMois(mois);
  const recente = optionsDeMois(now, null).some((o) => o.value === periode);
  return { periode, annee: recente ? null : mois.year };
}
