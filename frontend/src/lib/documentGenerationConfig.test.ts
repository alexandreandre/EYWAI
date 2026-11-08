import { describe, expect, it } from 'vitest';
import type { GeneratedDocument } from '@/api/documents';
import {
  ATTESTATION_COURANTE_TYPES,
  NOMBRE_MOIS_PAR_DEFAUT,
  attestationsDuSalarie,
  parseEmployeeDocumentDeepLink,
  payloadAttestation,
} from './documentGenerationConfig';
import { ATTESTATIONS_RETIREES, DOCUMENT_TYPE_LABELS, typesDeModeleProposes } from '@/api/documentLibrary';

describe('parseEmployeeDocumentDeepLink', () => {
  it('parse fiche_poste avec jobId', () => {
    expect(
      parseEmployeeDocumentDeepLink('tab=documents&generate=fiche_poste&jobId=job-123')
    ).toEqual({ generate: 'fiche_poste', jobId: 'job-123' });
  });

  it('retourne vide si pas de generate', () => {
    expect(parseEmployeeDocumentDeepLink('tab=documents')).toEqual({});
  });
});

// Attestations à la demande (05/11/2026) : deux lettres, emploi et salaire.
describe('attestations', () => {
  it("deux types seulement, la première est « Attestation d'emploi »", () => {
    expect([...ATTESTATION_COURANTE_TYPES]).toEqual(['attestation_emploi', 'attestation_salaire']);
    expect(DOCUMENT_TYPE_LABELS.attestation_emploi).toBe("Attestation d'emploi");
    expect(NOMBRE_MOIS_PAR_DEFAUT).toBe(3);
  });

  it('le nombre de mois ne part que pour le salaire, borné de 1 à 12', () => {
    const base = { employeeId: 'sal-1', templateId: null };
    expect(payloadAttestation({ ...base, documentType: 'attestation_emploi', nombreMois: 6 })).toEqual({
      employee_id: 'sal-1',
      document_type: 'attestation_emploi',
      category: 'attestation_courante',
      template_id: null,
    });
    expect(
      payloadAttestation({ ...base, documentType: 'attestation_salaire', nombreMois: 6 }).nombre_mois,
    ).toBe(6);
    expect(
      payloadAttestation({ ...base, documentType: 'attestation_salaire', nombreMois: 40 }).nombre_mois,
    ).toBe(12);
    expect(
      payloadAttestation({ ...base, documentType: 'attestation_salaire', nombreMois: Number.NaN }).nombre_mois,
    ).toBe(NOMBRE_MOIS_PAR_DEFAUT);
  });

  it('le modèle standard part sans identifiant de modèle', () => {
    expect(
      payloadAttestation({
        employeeId: 'sal-1',
        documentType: 'attestation_emploi',
        nombreMois: 3,
        templateId: '__martine__',
      }).template_id,
    ).toBeNull();
  });

  it('les attestations du salarié, la plus récente en premier', () => {
    const doc = (id: string, document_type: string, created_at: string) =>
      ({ id, document_type, category: 'attestation_courante', created_at }) as GeneratedDocument;
    const rows = [
      doc('a', 'attestation_emploi', '2026-11-01T10:00:00Z'),
      doc('b', 'cdi', '2026-11-04T10:00:00Z'),
      doc('c', 'attestation_salaire', '2026-11-05T10:00:00Z'),
      doc('d', 'attestation_retraite', '2026-10-01T10:00:00Z'),
    ];
    expect(attestationsDuSalarie(rows).map((d) => d.id)).toEqual(['c', 'a', 'd']);
  });

  it("la bibliothèque ne propose plus les sept types retirés à l'import", () => {
    expect(ATTESTATIONS_RETIREES.size).toBe(7);
    const proposes = typesDeModeleProposes().map(([cle]) => cle);
    expect(proposes).toContain('attestation_emploi');
    expect(proposes).not.toContain('attestation_location');
    expect(DOCUMENT_TYPE_LABELS.attestation_location).toBeTruthy();
  });
});
