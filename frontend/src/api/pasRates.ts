// src/api/pasRates.ts
// API du suivi des taux de prélèvement à la source.

import apiClient from "./apiClient";
import { downloadBlob, parseContentDispositionFilename } from "@/lib/downloadBlob";

export type PasStatut = "a_jour" | "bareme" | "a_rafraichir" | "manquant";

export type PasNature =
  | "inchange"
  | "nouveau"
  | "modifie"
  | "hors_effectif"
  | "non_rapproche";

export type PasSource = "dsn" | "crm";

export interface PasLigne {
  employee_id: string;
  nom: string;
  prenom: string;
  matricule: string;
  company_name: string;
  taux: number | null;
  type_taux: string | null;
  type_libelle: string;
  identifiant_taux: string | null;
  periode: string | null;
  source: string | null;
  statut: PasStatut;
  statut_libelle: string;
}

export interface PasVue {
  reference: string;
  compteurs: Record<string, number>;
  lignes: PasLigne[];
}

export interface PasHistoriqueLigne {
  periode: string | null;
  taux: number | null;
  type_taux: string | null;
  type_libelle: string;
  source: string | null;
  source_fichier: string | null;
  applied_at: string | null;
}

export interface PasApercuLigne {
  employee_id: string | null;
  nom: string;
  prenom: string;
  taux_actuel: number | null;
  taux_fichier: number | null;
  type_actuel: string | null;
  type_fichier: string | null;
  type_fichier_libelle: string;
  identifiant_fichier: string | null;
  nature: PasNature;
}

export interface PasApercu {
  periode: string;
  siren: string;
  fichier: string;
  source: string;
  compteurs: Record<string, number>;
  lignes: PasApercuLigne[];
  avertissements: string[];
}

export interface PasApplication {
  periode: string;
  appliques: number;
  historique: number;
  echecs: { employee_id: string; salarie: string; erreur: string }[];
}

export const getPasRates = () => apiClient.get<PasVue>("/api/pas-rates");

export const setPasRateManuel = (employeeId: string, taux: number) =>
  apiClient.put<{ taux: number; periode: string }>(
    `/api/pas-rates/${employeeId}/taux`,
    { taux },
  );

export const getPasHistorique = (employeeId: string) =>
  apiClient.get<PasHistoriqueLigne[]>(`/api/pas-rates/${employeeId}/historique`);

function fichierForm(file: File, source: PasSource): FormData {
  const form = new FormData();
  form.append("file", file);
  form.append("source", source);
  return form;
}

/** Ce que le fichier changerait. N'écrit rien. */
export async function previewPasRates(
  file: File,
  source: PasSource,
): Promise<PasApercu> {
  const { data } = await apiClient.post<PasApercu>(
    "/api/pas-rates/preview",
    fichierForm(file, source),
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

/**
 * Applique les taux du fichier.
 *
 * Le fichier est renvoyé plutôt que les lignes de l'aperçu : c'est le serveur
 * qui décide ce qu'il écrit, pas le navigateur.
 */
export async function applyPasRates(
  file: File,
  source: PasSource,
): Promise<PasApplication> {
  const { data } = await apiClient.post<PasApplication>(
    "/api/pas-rates/apply",
    fichierForm(file, source),
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

const EXPORT_FALLBACK_FILENAME = "taux-pas.xlsx";

export async function exportPasRates(): Promise<void> {
  const res = await apiClient.get<Blob>("/api/pas-rates/export", {
    responseType: "blob",
  });
  const filename = parseContentDispositionFilename(
    res.headers["content-disposition"],
    EXPORT_FALLBACK_FILENAME,
  );
  downloadBlob(res.data as Blob, filename);
}

/** Détail d'erreur du serveur, y compris quand la réponse est un Blob. */
export async function pasRatesErrorMessage(
  error: unknown,
  fallback = "L'opération a échoué. Réessayez dans un instant.",
): Promise<string> {
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  if (data instanceof Blob) {
    try {
      const detail = JSON.parse(await data.text())?.detail;
      if (typeof detail === "string") return detail;
    } catch {
      // Corps non JSON : on garde le repli.
    }
  }
  const detail = (data as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}
