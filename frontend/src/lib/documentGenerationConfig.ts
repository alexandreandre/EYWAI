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

export const ATTESTATION_COURANTE_TYPES = [
  'attestation_emploi',
  'attestation_presence',
  'attestation_anciennete',
  'attestation_poste',
  'attestation_salaire',
  'attestation_revenus',
  'attestation_location',
  'attestation_pret',
  'attestation_retraite',
] as const;

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
