import fs from 'node:fs';
import path from 'node:path';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { describe, expect, it } from 'vitest';

import { JoursASaisirListe } from './JoursASaisirListe';
import { lienCalendrierDuSalarie } from '@/features/payroll/utils/heuresSurArret';

const details = {
  fenetre: null,
  joursManquants: ['2026-10-26', '2026-10-27'],
  joursInformatifs: [],
} as never;

function rendu(props: Record<string, unknown>): string {
  return renderToStaticMarkup(
    createElement(
      StaticRouter,
      { location: '/payroll' },
      createElement(JoursASaisirListe, { details, ...props } as never)
    )
  );
}

describe('la fenêtre « Calendrier incomplet » dit où corriger', () => {
  it('propose « Compléter le planning » vers le calendrier du salarié', () => {
    const html = rendu({ lienPlanning: lienCalendrierDuSalarie('emp-1') });
    expect(html).toContain('Compléter le planning');
    expect(html).toContain('href="/employees/emp-1?tab=calendrier"');
  });

  it('sans lien demandé, pas de lien (génération groupée sans contexte)', () => {
    expect(rendu({})).not.toContain('Compléter le planning');
  });

  it('le dialogue de refus passe ce lien pour le refus calendrier incomplet', () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, './PayrollGenerationRefusalDialog.tsx'),
      'utf8'
    );
    expect(source).toMatch(/lienPlanning=\{lienCalendrierDuSalarie\(single\.job\.employeeId\)\}/);
  });
});
