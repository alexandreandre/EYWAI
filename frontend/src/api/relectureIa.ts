// frontend/src/api/relectureIa.ts
// Relecture de la paie d'un mois par l'IA : préparation, lancement, suivi, points à regarder.

import apiClient from './apiClient';
import { enTeteSociete } from './payslips';

export type GraviteRelecture = 'important' | 'a_verifier';

export interface SocieteARelire {
  company_id: string;
  nom: string;
  bulletins_generes: number;
  a_relire: number;
  /** Aucune règle propre à la société : relue avec les règles générales. */
  sans_regles: boolean;
}

export interface RelectureIa {
  id: string;
  statut: 'en_cours' | 'terminee' | 'echec';
  year: number;
  month: number;
  total: number;
  traites: number;
  echecs: number;
  points: number;
  message: string | null;
  termine_at: string | null;
}

export interface PreparationRelecture {
  year: number;
  month: number;
  societes: SocieteARelire[];
  total_a_relire: number;
  cout_unitaire_eur: number;
  cout_estime_eur: number;
  derniere_relecture: string | null;
  relecture_en_cours: RelectureIa | null;
  /** Pourquoi la relecture ne peut pas démarrer, s'il y a une raison. */
  blocage: string | null;
}

export interface EtatRelecture {
  relecture: RelectureIa | null;
}

export interface ResultatLancement {
  statut: 'lancee' | 'deja_en_cours' | 'rien_a_relire' | 'bloquee';
  message: string | null;
  relecture_id: string | null;
}

export interface PointARegarder {
  bulletin_relu_id: string;
  payslip_id: string;
  employee_id: string;
  gravite: GraviteRelecture;
  ligne: string;
  raison: string;
  bulletin_modifie_depuis: boolean;
  nom: string;
}

export interface ARegarder {
  relecture_faite: boolean;
  relu_le: string | null;
  points: PointARegarder[];
  /** Points moins importants laissés de côté par le plafond. */
  autres_points: number;
}

export async function getDroitsRelecture(): Promise<{ peut_lancer: boolean }> {
  const response = await apiClient.get<{ peut_lancer: boolean }>('/api/relecture-ia/droits');
  return response.data;
}

export async function getPreparationRelecture(
  year: number,
  month: number,
): Promise<PreparationRelecture> {
  const response = await apiClient.get<PreparationRelecture>('/api/relecture-ia/preparation', {
    params: { year, month },
  });
  return response.data;
}

export async function getEtatRelecture(): Promise<EtatRelecture> {
  const response = await apiClient.get<EtatRelecture>('/api/relecture-ia/etat');
  return response.data;
}

export async function lancerRelecture(
  year: number,
  month: number,
  companyIds: string[],
): Promise<ResultatLancement> {
  const response = await apiClient.post<ResultatLancement>('/api/relecture-ia/lancer', {
    year,
    month,
    company_ids: companyIds,
  });
  return response.data;
}

export async function getARegarder(
  year: number,
  month: number,
  companyId?: string | null,
): Promise<ARegarder> {
  const response = await apiClient.get<ARegarder>('/api/relecture-ia/a-regarder', {
    params: { year, month },
    ...enTeteSociete(companyId),
  });
  return response.data;
}

export async function marquerPointVu(
  bulletinReluId: string,
  ligne: string,
  companyId?: string | null,
): Promise<void> {
  await apiClient.post(
    '/api/relecture-ia/vus',
    { bulletin_relu_id: bulletinReluId, ligne },
    enTeteSociete(companyId),
  );
}
