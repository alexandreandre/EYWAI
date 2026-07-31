// src/api/residencePermits.ts
// API pour la page Titres de séjour (liste RH)

import apiClient from "./apiClient";
import { downloadBlob, parseContentDispositionFilename } from "@/lib/downloadBlob";

export type ResidencePermitStatus =
  | "valid"
  | "to_renew"
  | "expired"
  | "to_complete";

export interface ResidencePermitListItem {
  employee_id: string;
  first_name: string;
  last_name: string;
  is_subject_to_residence_permit: boolean;
  residence_permit_status: ResidencePermitStatus | null;
  residence_permit_expiry_date: string | null;
  residence_permit_days_remaining: number | null;
  residence_permit_data_complete: boolean | null;
  residence_permit_type: string | null;
  residence_permit_number: string | null;
}

/**
 * Récupère la liste des titres de séjour pour l'entreprise active.
 * Le backend filtre sur is_subject_to_residence_permit = true et employment_status actif/en_sortie.
 */
export const getResidencePermits = () => {
  return apiClient.get<ResidencePermitListItem[]>("/api/residence-permits");
};

const EXPORT_FALLBACK_FILENAME = "titres-de-sejour.xlsx";

/**
 * Message d'erreur du serveur quand la réponse est un Blob.
 *
 * En `responseType: "blob"`, axios livre aussi le corps des erreurs sous forme de
 * Blob : sans cette lecture, un 400 « Aucun salarié à exporter » s'afficherait
 * comme un objet illisible.
 */
export async function residencePermitsExportErrorMessage(
  error: unknown,
  fallback = "L'export a échoué. Réessayez dans un instant.",
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

/**
 * Télécharge l'export des salariés désignés.
 *
 * On envoie les identifiants des lignes affichées, dans leur ordre d'affichage,
 * et non les critères de filtrage : la règle de filtrage n'existe qu'ici, et le
 * fichier correspond à l'écran par construction.
 */
export async function exportResidencePermits(employeeIds: string[]): Promise<void> {
  const res = await apiClient.post<Blob>(
    "/api/residence-permits/export",
    { employee_ids: employeeIds },
    { responseType: "blob" },
  );
  const filename = parseContentDispositionFilename(
    res.headers["content-disposition"],
    EXPORT_FALLBACK_FILENAME,
  );
  downloadBlob(res.data as Blob, filename);
}
