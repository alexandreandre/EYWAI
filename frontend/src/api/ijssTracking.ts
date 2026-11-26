import apiClient from './apiClient';

export type IjssLineStatus = 'pending' | 'partial' | 'ok' | 'variance' | 'justified';

export interface IjssPeriod {
  id: string;
  company_id: string;
  period_year: number;
  period_month: number;
  status: string;
  expected_total: number;
  received_cpam_total: number;
  received_bank_total: number;
  variance_total: number;
}

export interface IjssDashboardRow {
  expected_line_id?: string | null;
  employee_id: string;
  employee_name: string;
  absence_request_id?: string | null;
  ijss_theorique: number;
  ijss_subrogees_bulletin: number;
  received_cpam: number;
  received_bank: number;
  line_status: IjssLineStatus;
  subrogation_active: boolean;
  ijss_brut_validated?: number | null;
  validation_source?: string | null;
  applied_to_payslip_at?: string | null;
  applied_ijss_brut?: number | null;
  /** Part déduite du maintien, lue sur le bulletin actuel (arrêt non subrogé). */
  ijss_deduites?: number | null;
  ijss_deduites_source?: string | null;
  nb_jours_maintenus?: number | null;
  /** Montant appliqué qui ne change plus le bulletin (garanti versé en entier). */
  applique_sans_effet?: boolean;
}

export interface IjssPeriodDashboard {
  period: IjssPeriod;
  summary: { ok: number; variance: number; pending: number };
  rows: IjssDashboardRow[];
  unmatched_received?: IjssUnmatchedReceivedLine[];
}

export interface IjssUnmatchedReceivedLine {
  id: string;
  source: string;
  amount: number;
  employee_name_raw?: string | null;
  employee_nir?: string | null;
  payment_date?: string | null;
}

export interface IjssAbsenceStatus {
  status: string;
  absence_request_id: string;
  expected_line_id?: string | null;
  ijss_subrogees_bulletin?: number;
  ijss_brut_validated?: number | null;
  applied_to_payslip_at?: string | null;
  applied_ijss_brut?: number | null;
}

export const IJSS_ABSENCE_STATUS_LABELS: Record<string, string> = {
  pending: 'IJSS en attente CPAM',
  ok: 'IJSS rapprochée',
  justified: 'IJSS justifiée',
  variance: 'IJSS — écart',
  partial: 'IJSS partiel',
};

export async function getIjssPeriodDashboard(
  year: number,
  month: number,
): Promise<IjssPeriodDashboard> {
  const { data } = await apiClient.get<IjssPeriodDashboard>('/api/ijss-tracking/periods', {
    params: { year, month },
  });
  return data;
}

export async function syncIjssExpected(periodId: string): Promise<{ synced_count: number }> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/sync-expected`);
  return data;
}

export async function closeIjssPeriod(periodId: string, notes?: string): Promise<unknown> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/close`, {
    notes: notes ?? null,
  });
  return data;
}

export async function syncCpamDecomptes(periodId: string): Promise<{
  success: boolean;
  message: string;
  fallback?: string;
}> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/sync-cpam`);
  return data;
}

export async function importBankRecap(periodId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/import/bank`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function importCpamDecompte(periodId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/import/cpam`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function commitIjssImportBatch(batchId: string) {
  const { data } = await apiClient.post(`/api/ijss-tracking/import/batches/${batchId}/commit`);
  return data;
}

export async function justifyIjssVariance(
  expectedLineId: string,
  content: string,
): Promise<unknown> {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/justify`,
    { content },
  );
  return data;
}

export async function validateIjssExpectedLine(
  expectedLineId: string,
  amount?: number,
  source?: 'cpam_decompte' | 'bank_transfer' | 'manual',
) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/validate`,
    { amount: amount ?? null, source: source ?? null },
  );
  return data;
}

export async function applyIjssToPayslip(expectedLineId: string) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/apply-to-payslip`,
  );
  return data;
}

export async function applyAllValidatedIjss(periodId: string) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/apply-validated`,
  );
  return data;
}

export async function getAbsenceIjssStatus(absenceId: string): Promise<IjssAbsenceStatus> {
  const { data } = await apiClient.get<IjssAbsenceStatus>(
    `/api/ijss-tracking/absences/${absenceId}/ijss`,
  );
  return data;
}

export async function matchIjssReceivedLine(
  lineId: string,
  employeeId: string,
  expectedLineId?: string,
) {
  const { data } = await apiClient.patch(
    `/api/ijss-tracking/received-lines/${lineId}/match`,
    {
      employee_id: employeeId,
      expected_line_id: expectedLineId ?? null,
    },
  );
  return data;
}

export async function downloadIjssAuditExport(periodId: string): Promise<Blob> {
  const { data } = await apiClient.get(`/api/ijss-tracking/periods/${periodId}/export-audit`, {
    responseType: 'blob',
  });
  return data;
}

export const IJSS_LINE_STATUS_LABELS: Record<IjssLineStatus, string> = {
  ok: 'OK',
  partial: 'Partiel',
  variance: 'Écart',
  justified: 'Justifié',
  pending: 'En attente',
};

export interface IjssImportProfile {
  id?: string;
  batch_type: string;
  profile_name: string;
  column_mapping: Record<string, unknown>;
}

export async function getIjssImportProfiles(): Promise<IjssImportProfile[]> {
  const { data } = await apiClient.get<IjssImportProfile[]>(
    '/api/ijss-tracking/import-profiles',
  );
  return data;
}

export async function updateIjssImportProfile(
  batchType: 'bank_recap' | 'cpam_decompte_file',
  columnMapping: Record<string, unknown>,
): Promise<IjssImportProfile> {
  const { data } = await apiClient.put<IjssImportProfile>(
    `/api/ijss-tracking/import-profiles/${batchType}`,
    { column_mapping: columnMapping },
  );
  return data;
}

// ----- Écran « Arrêts & IJ » (retour d'Elsa du 16/11) -----

export type TypeJustificatifArret = 'virement_cpam' | 'ij_salarie' | 'decompte_cpam' | 'autre';

export const LIBELLES_JUSTIFICATIF_ARRET: Record<TypeJustificatifArret, string> = {
  virement_cpam: 'Virement de la CPAM (subrogation)',
  ij_salarie: 'IJ transmises par le salarié',
  decompte_cpam: 'Décompte CPAM',
  autre: 'Autre pièce',
};

export interface JustificatifArret {
  id: string;
  kind: TypeJustificatifArret;
  filename: string | null;
  url: string | null;
  created_at: string | null;
}

export type EtatMaintienArret =
  | 'bulletin_a_faire'
  | 'bulletin_a_recalculer'
  | 'bulletin_remis_avant_l_arret'
  | 'reporte_sur_le_bulletin_suivant'
  | 'report_au_prochain_calcul'
  | 'report_a_recalculer'
  | 'en_attente_des_ij'
  | 'verse'
  | 'sans_maintien';

export interface ArretDuMois {
  absence_id: string;
  employee_id: string;
  employee_name: string;
  type: string;
  arret_type: string | null;
  date_debut: string | null;
  date_fin: string | null;
  jours_dans_le_mois: number;
  subrogation_active: boolean;
  certificat_url: string | null;
  certificat_filename: string | null;
  ij_estimees: number | null;
  ij_recues: number | null;
  ij_saisies_du_mois: number | null;
  ij_appliquees_le: string | null;
  bulletin_id: string | null;
  maintien: {
    etat: EtatMaintienArret;
    montant_verse: number;
    montant_en_attente: number;
    motif: string | null;
  };
  justificatifs: JustificatifArret[];
}

export interface ArretsDuMois {
  year: number;
  month: number;
  periode_cloturee: boolean;
  arrets: ArretDuMois[];
}

export async function listerArretsDuMois(year: number, month: number): Promise<ArretsDuMois> {
  const { data } = await apiClient.get<ArretsDuMois>('/api/ijss-tracking/arrets', {
    params: { year, month },
  });
  return data;
}

export interface ReponseIjRecues {
  statut: 'en_attente_du_bulletin' | 'bulletin_recalcule' | 'bulletin_remis';
  message: string;
  montant: number;
}

export async function enregistrerIjRecues(
  absenceId: string,
  body: { year: number; month: number; montant: number },
): Promise<ReponseIjRecues> {
  const { data } = await apiClient.post<ReponseIjRecues>(
    `/api/ijss-tracking/arrets/${absenceId}/ij-recues`,
    body,
  );
  return data;
}

export async function ajouterJustificatifArret(
  absenceId: string,
  body: { kind: TypeJustificatifArret; storage_path: string; filename: string | null },
): Promise<unknown> {
  const { data } = await apiClient.post(`/api/ijss-tracking/arrets/${absenceId}/justificatifs`, body);
  return data;
}

export async function supprimerJustificatifArret(justificatifId: string): Promise<void> {
  await apiClient.delete(`/api/ijss-tracking/justificatifs/${justificatifId}`);
}
