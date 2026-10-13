import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { PayrollProgressBar } from './PayrollProgressBar';
import { bilanDeGeneration } from '@/features/payroll/utils/generationEnCours';
import type { PayrollGenerationLogEntry } from '@/features/payroll/hooks/usePayrollGeneration';

const entree = (
  id: string,
  status: PayrollGenerationLogEntry['status'],
  extra: Partial<PayrollGenerationLogEntry> = {}
): PayrollGenerationLogEntry => ({
  id,
  employeeId: id,
  employeeName: 'Élodie Vasseur',
  year: 2026,
  month: 10,
  status,
  ...extra,
});

const refusee = entree('e-1', 'error', {
  refus: true,
  error: 'Des heures sont saisies sur des jours d’arrêt : 19/10, 20/10.',
});

describe('bilan de fin de génération — rejeu C1/C2 du 12/10', () => {
  it('une génération refusée se dit refusée', () => {
    expect(bilanDeGeneration([refusee])).toBe('0 bulletin généré, 1 refusé');
  });

  it('générés, refusés et échecs sont comptés à part et accordés', () => {
    expect(
      bilanDeGeneration([
        entree('a', 'success'),
        entree('b', 'warning'),
        refusee,
        entree('c', 'error', { refus: true }),
        entree('d', 'error', { error: 'Erreur serveur' }),
      ])
    ).toBe('2 bulletins générés, 2 refusés, 1 en échec');
    expect(bilanDeGeneration([entree('a', 'success')])).toBe('1 bulletin généré');
  });
});

describe('la barre de suivi ne dit pas « traité » pour un refus', () => {
  const rendu = (props: Record<string, unknown> = {}) =>
    renderToStaticMarkup(
      createElement(PayrollProgressBar, {
        phase: 'done',
        progress: 100,
        currentLabel: null,
        estimatedRemainingSec: null,
        log: [refusee],
        totalJobs: 1,
        completedCount: 1,
        ...props,
      })
    );

  it('dit « 0 bulletin généré, 1 refusé » une fois terminée', () => {
    const html = rendu();
    expect(html).toContain('0 bulletin généré, 1 refusé');
    expect(html).not.toContain('traité sur');
  });

  it('propose de rouvrir le refus', () => {
    expect(rendu({ onVoirRefus: () => undefined })).toContain('Voir le refus');
    expect(rendu()).not.toContain('Voir le refus');
  });

  it('pendant la génération, le compteur reste « traité sur »', () => {
    expect(rendu({ phase: 'running' })).toContain('1 bulletin traité sur 1');
  });
});
