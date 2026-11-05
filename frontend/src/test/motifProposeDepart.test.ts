import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

// « Fin de CDD » proposée d'office pour un CDD à terme (spec du 05/11, R8).
describe('formulaire de départ : motif proposé par Martine', () => {
  const t = lire('components/exits/CreateExitDialog.tsx');

  it('propose le motif et le dernier jour à partir du salarié choisi', () => {
    expect(t).toContain('motifProposeAuDepart(selectedEmployee)');
    expect(t).toContain('setLastWorkingDay(propose.dernierJour)');
  });

  it('ne remplace jamais un motif choisi par la RH, ni un motif imposé', () => {
    expect(t).toContain('if (!open || initialExitType || motifChoisiParLaRh.current) return;');
    expect(t).toContain('motifChoisiParLaRh.current = true;');
  });

  it('dit que la proposition vient de Martine', () => {
    expect(t).toContain('data-testid="motif-propose-info"');
    expect(t).toContain('{motifPropose.phrase}');
  });

  it('la liste des salariés porte le contrat', () => {
    const api = lire('api/employeeExits.ts');
    expect(api).toContain('contract_end_date?: string | null;');
  });
});
