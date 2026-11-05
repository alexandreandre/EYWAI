import type { GeneratedDocument, GenerateDocumentPayload } from '@/api/documents';

export const CONTRACT_TYPES = [
  'cdi',
  'cdd',
  'convention_stage',
  'contrat_alternance',
] as const;

export const AVENANT_TYPES = [
  'avenant_salaire',
  'avenant_poste',
  'avenant_temps',
  'avenant_lieu',
  'avenant_general',
] as const;

/**
 * Attestations remises à la demande du salarié (05/11/2026) : la lettre de
 * travail (modèle du ministère, plus rémunération et période d'essai) et la
 * lettre de salaire (bulletins remis). Les sept autres types sont retirés.
 */
export const ATTESTATION_COURANTE_TYPES = ['attestation_emploi', 'attestation_salaire'] as const;
export type AttestationType = (typeof ATTESTATION_COURANTE_TYPES)[number];

export const NOMBRE_MOIS_PAR_DEFAUT = 3;
export const NOMBRE_MOIS_MAX = 12;

export function payloadAttestation({
  employeeId,
  documentType,
  nombreMois,
  templateId,
}: {
  employeeId: string;
  documentType: AttestationType;
  nombreMois: number;
  templateId: string | null;
}): GenerateDocumentPayload {
  const payload: GenerateDocumentPayload = {
    employee_id: employeeId,
    document_type: documentType,
    category: 'attestation_courante',
    template_id: templateId && templateId !== '__martine__' ? templateId : null,
  };
  if (documentType === 'attestation_salaire') {
    const n = Number.isFinite(nombreMois) ? Math.round(nombreMois) : NOMBRE_MOIS_PAR_DEFAUT;
    payload.nombre_mois = Math.min(NOMBRE_MOIS_MAX, Math.max(1, n));
  }
  return payload;
}

/** Les attestations déjà générées pour un salarié (anciens types compris), la plus récente en premier. */
export function attestationsDuSalarie(rows: GeneratedDocument[]): GeneratedDocument[] {
  return rows
    .filter((d) => d.category === 'attestation_courante' && d.document_type.startsWith('attestation_'))
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export const FICHE_POSTE_TYPES = ['fiche_poste'] as const;

export type DocumentGenMode =
  | 'contrat'
  | 'avenant'
  | 'attestation'
  | 'fiche_poste'
  | null;

export const CLIENT_TEMPLATE_ONLY_TYPES = new Set(['fiche_poste', 'document_transmis']);

export function parseEmployeeDocumentDeepLink(search: string): {
  generate?: 'fiche_poste';
  jobId?: string;
} {
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const generate = params.get('generate');
  const jobId = params.get('jobId') ?? undefined;
  if (generate === 'fiche_poste') {
    return { generate: 'fiche_poste', jobId };
  }
  return {};
}
