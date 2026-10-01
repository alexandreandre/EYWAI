/**
 * Sortie guidée sur la paie du mois : qui doit créer un départ, et le texte
 * du bandeau. Décision pure — une lecture groupée des départs de la société
 * suffit, pas une requête par salarié.
 */

import { displayNamePrenomNom } from '@/lib/employeeName';
import { payrollGenerationBlockReason } from '@/features/payroll/utils/employmentPeriod';

export const BOUTON_CREER_LE_DEPART = 'Créer le départ';
export const BOUTON_GENERER_BULLETIN_SORTIE = 'Générer le bulletin de sortie';

const STATUTS_ANNULES = new Set(['annulee', 'annule', 'cancelled', 'canceled']);

export type SalariePourSortieGuidee = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  nom_usage?: string | null;
  hire_date?: string | null;
  date_debut_execution?: string | null;
  contract_end_date?: string | null;
  exit_last_working_day?: string | null;
  current_exit_id?: string | null;
  employment_status?: string | null;
  missing_payroll_fields?: string[] | null;
};

export type DepartPourSortieGuidee = {
  id?: string | null;
  employee_id: string;
  last_working_day?: string | null;
  status?: string | null;
};

export type EtapeSortieGuidee = 'creer_depart' | 'generer_bulletin';

export type BandeauSortieGuidee = {
  employeeId: string;
  etape: EtapeSortieGuidee;
  bouton: string;
  message: string;
  dateIso: string;
  /** Faux si la fiche empêche la génération : pas de clic, la raison est affichée. */
  peutGenerer: boolean;
  raisonBlocage: string | null;
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

/** Un départ ne compte que s'il concerne la fin de contrat du mois affiché. */
export function aUnDepartCree(
  salarie: SalariePourSortieGuidee,
  departs: readonly DepartPourSortieGuidee[],
  year: number,
  month: number
): boolean {
  const dateFin = dateDeFinDuContrat(salarie);
  return departs.some((d) => {
    if (d.employee_id !== salarie.id || statutAnnule(d.status)) return false;
    const lwd = sliceDate(d.last_working_day);
    if (lwd) return tombeDansLeMois(lwd, year, month);
    const memeDossier = Boolean(salarie.current_exit_id && d.id && d.id === salarie.current_exit_id);
    return memeDossier && Boolean(dateFin && tombeDansLeMois(dateFin, year, month));
  });
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

export function messageGenererBulletinSortie(
  salarie: Pick<SalariePourSortieGuidee, 'first_name' | 'last_name' | 'nom_usage'>,
  raisonBlocage?: string | null
): string {
  const base = `Départ de ${displayNamePrenomNom(salarie)} créé : générez son bulletin de sortie.`;
  return raisonBlocage ? `${base} ${raisonBlocage}` : base;
}

function bandeauCommun(
  salarie: SalariePourSortieGuidee,
  etape: EtapeSortieGuidee,
  dateIso: string,
  year: number,
  month: number
): BandeauSortieGuidee {
  if (etape === 'creer_depart') {
    return {
      employeeId: salarie.id,
      etape,
      bouton: BOUTON_CREER_LE_DEPART,
      message: messageCreerLeDepart(salarie, dateIso),
      dateIso,
      peutGenerer: false,
      raisonBlocage: null,
    };
  }
  const raisonBlocage = payrollGenerationBlockReason(salarie, year, month);
  return {
    employeeId: salarie.id,
    etape,
    bouton: raisonBlocage ?? BOUTON_GENERER_BULLETIN_SORTIE,
    message: messageGenererBulletinSortie(salarie, raisonBlocage),
    dateIso,
    peutGenerer: raisonBlocage === null,
    raisonBlocage,
  };
}

export function bandeauxSortieDuMois(
  salaries: readonly SalariePourSortieGuidee[],
  departs: readonly DepartPourSortieGuidee[],
  year: number,
  month: number,
  idsAvecBulletin: ReadonlySet<string> = new Set()
): BandeauSortieGuidee[] {
  const bandeaux: BandeauSortieGuidee[] = [];
  for (const salarie of salaries) {
    const dateIso = dateDeFinDuContrat(salarie);
    if (!dateIso || !tombeDansLeMois(dateIso, year, month)) continue;
    if (!aUnDepartCree(salarie, departs, year, month)) {
      bandeaux.push(bandeauCommun(salarie, 'creer_depart', dateIso, year, month));
      continue;
    }
    if (idsAvecBulletin.has(salarie.id)) continue;
    bandeaux.push(bandeauCommun(salarie, 'generer_bulletin', dateIso, year, month));
  }
  return bandeaux;
}
