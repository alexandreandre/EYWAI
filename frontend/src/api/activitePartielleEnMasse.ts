/**
 * Activité partielle en masse (26/11, LEWIS : tous les vendredis) : l'aperçu,
 * calculé par le serveur sans rien écrire, puis l'enregistrement, qui rend le
 * même décompte. Chaque jour est écrit par le chemin du calendrier d'un salarié.
 */
import apiClient from './apiClient';

export type RaisonLaisse =
  | 'absence'
  | 'repos'
  | 'bulletin_valide'
  | 'hors_contrat'
  | 'deja_ap'
  | 'heures_saisies'
  | 'echec';

export interface SalarieEnMasse {
  employee_id: string;
  nom: string;
  forfait_jours: boolean;
  passes: string[];
  laisses: { date: string; raison: RaisonLaisse }[];
  /** Mois que le serveur n'a pas pu enregistrer, avec la raison. */
  erreurs: string[];
}

export interface DecompteEnMasse {
  enregistre: boolean;
  dates: string[];
  total_passes: number;
  total_laisses: number;
  laisses_par_raison: Partial<Record<RaisonLaisse, number>>;
  libelles_raisons: Record<string, string>;
  salaries: SalarieEnMasse[];
  /** Des dates hors de la période déclarée par la société, dites avant d'enregistrer. */
  avertissement: string | null;
}

export interface DemandeEnMasse {
  employee_ids: string[];
  dates: string[];
}

export async function apercuActivitePartielleEnMasse(demande: DemandeEnMasse): Promise<DecompteEnMasse> {
  const { data } = await apiClient.post<DecompteEnMasse>(
    '/api/schedules/activite-partielle-en-masse/apercu',
    demande,
  );
  return data;
}

export async function poserActivitePartielleEnMasse(demande: DemandeEnMasse): Promise<DecompteEnMasse> {
  const { data } = await apiClient.post<DecompteEnMasse>('/api/schedules/activite-partielle-en-masse', demande);
  return data;
}
