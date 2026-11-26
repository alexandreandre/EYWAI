/**
 * Activité partielle (retour d'Elsa du 16/11, LEWIS) : réglage de la société et
 * heures chômées du mois. Martine pose les deux variables du mois (retenue et
 * indemnité) que le moteur paie déjà.
 */
import apiClient from './apiClient';

export interface ReglageActivitePartielle {
  active: boolean;
  date_debut: string | null;
  date_fin: string | null;
  taux_indemnite: number;
  plancher_horaire: number;
  plafond_horaire: number;
  heures_par_jour: number | null;
  reference_decision: string | null;
  note: string | null;
  updated_at?: string | null;
}

export interface SalarieActivitePartielle {
  employee_id: string;
  nom: string;
  statut: string | null;
  taux_horaire: number | null;
  /** Forfait annuel en jours : 1 jour = 7 h, taux selon la fiche du ministère du Travail. */
  forfait_jours?: boolean;
  heures_par_jour: number;
  deja: { heures: number | null; retenue: number; indemnite: number } | null;
  /** Jours « Activité partielle » posés au calendrier du mois : ils font foi au bulletin. */
  calendrier?: {
    jours: number[];
    heures: number;
    retenue: number | null;
    indemnite: number | null;
  } | null;
  /**
   * Indemnité portée par le bulletin du mois, s'il existe : prime d'ancienneté
   * comprise dans l'assiette (R5122-18). Sans bulletin, les montants de l'écran
   * sont avant la prime ; le bulletin les recalcule.
   */
  indemnite_bulletin?: number | null;
}

export interface MoisActivitePartielle {
  reglage: ReglageActivitePartielle;
  refus: string | null;
  salaries: SalarieActivitePartielle[];
}

export interface ResultatActivitePartielle {
  employee_id: string;
  nom?: string;
  statut: 'pose' | 'retire' | 'rien' | 'refuse' | 'bulletin_remis';
  message?: string;
  heures?: number;
  taux_horaire?: number;
  indemnite_horaire?: number;
  retenue?: number;
  indemnite?: number;
  regle?: string;
}

export const lireReglageActivitePartielle = async () =>
  (await apiClient.get<ReglageActivitePartielle>('/api/activite-partielle/reglage')).data;

export const enregistrerReglageActivitePartielle = async (r: ReglageActivitePartielle) =>
  (await apiClient.put<ReglageActivitePartielle>('/api/activite-partielle/reglage', r)).data;

export const lireMoisActivitePartielle = async (year: number, month: number) =>
  (await apiClient.get<MoisActivitePartielle>('/api/activite-partielle/mois', { params: { year, month } })).data;

export const poserHeuresActivitePartielle = async (
  year: number,
  month: number,
  saisies: { employee_id: string; heures: number }[],
) =>
  (
    await apiClient.post<{
      resultats: ResultatActivitePartielle[];
      bulletins_a_recalculer: { employee_id: string; year: number; month: number }[];
    }>('/api/activite-partielle/mois', { year, month, saisies })
  ).data;
