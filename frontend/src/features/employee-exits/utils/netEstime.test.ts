import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * [H3] Le dossier de départ ne calcule pas le net d'une indemnité : son régime
 * social (cotisations, CSG/CRDS au-delà du minimum, contribution patronale) est
 * porté par le bulletin de sortie. L'édition du reçu n'écrit donc plus un
 * « Total net estimé », qui valait le brut.
 */
describe('reçu pour solde de tout compte, édition', () => {
  it('n’écrit plus « Total net estimé »', () => {
    const source = readFileSync(
      path.resolve(__dirname, '../../../components/exit-document-edit/SoldeToutCompteSection.tsx'),
      'utf-8'
    );
    expect(source).not.toContain('Total net estimé');
  });
});
