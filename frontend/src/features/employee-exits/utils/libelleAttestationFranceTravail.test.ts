import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { documentTypeLabels } from '@/api/employeeExits';

import { messageDocumentsARevoir } from './documentsSortie';

/**
 * L'attestation destinée à France Travail porte un seul nom (relevé du
 * 12/10/2026) : la checklist disait « Attestation France Travail », le menu
 * « Générer un document » et la liste des documents « Attestation employeur ».
 */
describe('nom de l’attestation France Travail', () => {
  it('la liste des documents et les messages disent « Attestation France Travail »', () => {
    expect(documentTypeLabels.attestation_pole_emploi).toBe('Attestation France Travail');
    expect(messageDocumentsARevoir(['attestation_pole_emploi'])).toContain(
      'Attestation France Travail'
    );
  });

  it('le dossier de départ ne dit plus « Attestation employeur »', () => {
    const source = readFileSync(
      path.resolve(__dirname, '../../../components/exits/ExitDetailsPanel.tsx'),
      'utf-8'
    );
    expect(source).not.toMatch(/[Aa]ttestation employeur/);
  });
});
