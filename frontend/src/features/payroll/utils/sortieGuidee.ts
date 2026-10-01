/**
 * Sortie guidée sur la paie du mois : qui doit créer un départ, et le texte
 * du bandeau. Décision pure — une lecture groupée des départs de la société
 * suffit, pas une requête par salarié.
 */

import { displayNamePrenomNom } from '@/lib/employeeName';

export const BOUTON_CREER_LE_DEPART = 'Créer le départ';

const STATUTS_ANNULES = new Set(['annulee', 'annule', 'cancelled', 'canceled']);

export type SalariePourSortieGuidee = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  nom_usage?: string | null;
  contract_end_date?: string | null;
  exit_last_working_day?: string | null;
  current_exit_id?: string | null;
};

export type DepartPourSortieGuidee = {
  employee_id: string;
  last_working_day?: string | null;
  status?: string | null;
};

export type EtapeSortieGuidee = 'creer_depart';

export type BandeauSortieGuidee = {
  employeeId: string;
  etape: EtapeSortieGuidee;
  bouton: string;
  message: string;
  dateIso: string;
};

function sliceDate(value?: string | null): string | null {
  if (!value) return null;
  const iso = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso : null;
}

function tombeDansLeMois(iso: string, year: number, month: number): boolean {
  const attendu = `${year}-${String(month).padStart(2, '0')}`;
  return iso.slice(0, 7) === attendu;
}

function statutAnnule(status?: string | null): boolean {
  return STATUTS_ANNULES.has((status || '').toLowerCase());
}

export function dateDeFinDuContrat(
  salarie: Pick<SalariePourSortieGuidee, 'contract_end_date' | 'exit_last_working_day'>
): string | null {
  return sliceDate(salarie.contract_end_date) || sliceDate(salarie.exit_last_working_day);
}

export function aUnDepartCree(
  salarie: SalariePourSortieGuidee,
  departs: readonly DepartPourSortieGuidee[]
): boolean {
  if (salarie.current_exit_id) return true;
  return departs.some((d) => d.employee_id === salarie.id && !statutAnnule(d.status));
}

function jjMm(iso: string): string {
  const [, mois, jour] = iso.split('-');
  return `${jour}/${mois}`;
}

export function messageCreerLeDepart(
  salarie: Pick<SalariePourSortieGuidee, 'first_name' | 'last_name' | 'nom_usage'>,
  dateIso: string
): string {
  return `${displayNamePrenomNom(salarie)} quitte l'entreprise le ${jjMm(dateIso)} : créez son départ.`;
}

export function bandeauxSortieDuMois(
  salaries: readonly SalariePourSortieGuidee[],
  departs: readonly DepartPourSortieGuidee[],
  year: number,
  month: number
): BandeauSortieGuidee[] {
  const bandeaux: BandeauSortieGuidee[] = [];
  for (const salarie of salaries) {
    const dateIso = dateDeFinDuContrat(salarie);
    if (!dateIso || !tombeDansLeMois(dateIso, year, month)) continue;
    if (aUnDepartCree(salarie, departs)) continue;
    bandeaux.push({
      employeeId: salarie.id,
      etape: 'creer_depart',
      bouton: BOUTON_CREER_LE_DEPART,
      message: messageCreerLeDepart(salarie, dateIso),
      dateIso,
    });
  }
  return bandeaux;
}
