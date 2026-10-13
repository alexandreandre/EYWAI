import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

describe('Fin de CDD : « Prime de précarité non due » se saisit à l’écran', () => {
  it('la création d’une fin de CDD propose la case et envoie le motif', () => {
    const t = lire('components/exits/CreateExitDialog.tsx');
    expect(t).toContain('LIBELLE_PRECARITE_NON_DUE');
    expect(t).toContain('OPTIONS_MOTIF_PRECARITE_NON_DUE');
    expect(t).toContain(
      "exitType === 'fin_cdd' && precariteNonDue && motifPrecarite ? { precarite_non_due: motifPrecarite }"
    );
    expect(t).toContain('MESSAGE_MOTIF_PRECARITE_MANQUANT');
  });

  it('l’onglet « Indemnités » d’une fin de CDD la montre et l’enregistre', () => {
    const t = lire('components/exits/ExitDetailsPanel.tsx');
    expect(t).toContain("exitDetails.exit_type === 'fin_cdd'");
    expect(t).toContain('updateEmployeeExit(exitId, { precarite_non_due: motif })');
    expect(t).toContain('LIBELLE_PRECARITE_NON_DUE');
  });

  it('l’API porte le motif à la création et à la modification', () => {
    const t = lire('api/employeeExits.ts');
    expect(t).toContain('precarite_non_due?: MotifPrecariteNonDue;');
    expect(t).toContain('precarite_non_due?: MotifPrecariteNonDue | null;');
  });
});
