import { describe, expect, it } from 'vitest';

import {
  MESSAGE_GENERER_DABORD_BULLETIN,
  documentsARevoir,
  documentsDeSortieGrises,
  messageDocumentsARevoir,
} from './documentsSortie';

describe('documents de sortie tant que le bulletin manque', () => {
  it('sans bulletin du mois de sortie : grisés, avec la mention', () => {
    expect(documentsDeSortieGrises(null)).toBe(true);
    expect(documentsDeSortieGrises(undefined)).toBe(true);
    expect(MESSAGE_GENERER_DABORD_BULLETIN).toBe('Générez d\'abord le bulletin de sortie');
  });

  it('dès que le bulletin du mois de sortie existe : plus grisés', () => {
    expect(documentsDeSortieGrises({ mois: '09/2026' })).toBe(false);
  });
});

describe('documents de sortie à revoir', () => {
  const solde = (generatedAt: string) => ({
    document_type: 'solde_tout_compte',
    document_category: 'generated',
    generated_at: generatedAt,
  });

  it('le bulletin de sortie recalculé après le solde met le solde à revoir', () => {
    const notes = {
      bulletin_recalcule: {
        timestamp: '2026-10-04T12:00:00+00:00',
        generated_documents_to_review: ['solde_tout_compte'],
      },
    };
    expect(documentsARevoir(notes, [solde('2026-10-02T05:50:02+00:00')])).toEqual([
      'solde_tout_compte',
    ]);
  });

  it('régénéré après le recalcul, le document n’est plus à revoir', () => {
    const notes = {
      bulletin_recalcule: {
        timestamp: '2026-10-04T12:00:00+00:00',
        generated_documents_to_review: ['solde_tout_compte'],
      },
    };
    expect(documentsARevoir(notes, [solde('2026-10-04T12:05:00+00:00')])).toEqual([]);
  });

  it('un changement de date et un bulletin recalculé ne listent chaque document qu’une fois', () => {
    const notes = {
      last_working_day_change: {
        timestamp: '2026-10-03T08:00:00+00:00',
        generated_documents_to_review: ['solde_tout_compte', 'certificat_travail'],
      },
      bulletin_recalcule: {
        timestamp: '2026-10-04T12:00:00+00:00',
        generated_documents_to_review: ['solde_tout_compte'],
      },
    };
    const docs = [
      solde('2026-10-01T00:00:00+00:00'),
      { document_type: 'certificat_travail', document_category: 'generated', generated_at: '2026-10-01T00:00:00+00:00' },
    ];
    expect(documentsARevoir(notes, docs)).toEqual(['solde_tout_compte', 'certificat_travail']);
  });

  it('sans note, rien à revoir', () => {
    expect(documentsARevoir(null, [solde('2026-10-01T00:00:00+00:00')])).toEqual([]);
  });

  it('le message nomme les documents à régénérer', () => {
    expect(messageDocumentsARevoir(['solde_tout_compte', 'attestation_pole_emploi'])).toBe(
      'Le départ ou un bulletin a changé après leur génération : régénérez Solde de tout compte, ' +
        'Attestation employeur avant publication ou remise au collaborateur.'
    );
  });
});
