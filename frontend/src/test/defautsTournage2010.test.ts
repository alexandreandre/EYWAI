import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/** Gardes des textes d'écran relevés au tournage des vidéos (20/10/2026), par lecture du source. */
const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

describe('fiche, onglet « Soldes de congés »', () => {
  const texte = lire('components/employee-detail/EmployeeDetailLeaveBalancesTab.tsx');

  it('la phrase d’aide cite tous les compteurs que le crayon corrige, repos compensateur compris', () => {
    expect(texte).toMatch(/Le crayon d’une ligne corrige son solde : congés payés \(N-1 et N à la fin d’un mois\), RTT, JTC, repos compensateur\./);
  });
});
