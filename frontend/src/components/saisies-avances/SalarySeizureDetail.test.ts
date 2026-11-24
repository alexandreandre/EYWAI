// Le détail d'une saisie, rendu sans navigateur (vitest en environnement node,
// sans bibliothèque DOM) : la mensualité et le montant total s'y modifient, le
// reste dû s'y lit. Données fictives.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { SalarySeizure } from '@/api/saisiesAvances';

vi.mock('@/api/saisiesAvances', () => ({ updateSalarySeizure: vi.fn() }));

import { SaisieMontantsEditables } from './SalarySeizureDetail';

const SAISIE: SalarySeizure = {
  id: 'saisie-1',
  company_id: 'societe-exemple',
  employee_id: 'salarie-exemple',
  type: 'saisie_arret',
  creditor_name: 'Créancier fictif SARL',
  amount: 300,
  calculation_mode: 'fixe',
  start_date: '2026-07-01',
  status: 'active',
  priority: 4,
  montant_total: 1000,
  total_retenu: 400,
  reste_du: 600,
  created_at: '2026-07-01T08:00:00',
  updated_at: '2026-07-01T08:00:00',
};

function rendu(saisie: SalarySeizure): string {
  return renderToStaticMarkup(createElement(SaisieMontantsEditables, { seizure: saisie }));
}

describe('SaisieMontantsEditables', () => {
  it('la mensualité est un champ modifiable, prérempli', () => {
    const html = rendu(SAISIE);
    expect(html).toMatch(/<input[^>]*id="seizure-amount-edit"[^>]*>/);
    expect(html).toMatch(/id="seizure-amount-edit"[^>]*value="300"/);
    expect(html).not.toMatch(/id="seizure-amount-edit"[^>]*disabled/);
  });

  it('le montant total se saisit, et le reste dû se lit', () => {
    const html = rendu(SAISIE);
    expect(html).toMatch(/id="seizure-total-edit"[^>]*value="1000"/);
    expect(html).toContain('Déjà retenu');
    expect(html).toContain('400,00 €');
    expect(html).toContain('600,00 €');
    expect(html).toContain('Enregistrer');
  });

  it('sans montant total, le champ est vide et le reste dû n’est pas inventé', () => {
    const html = rendu({ ...SAISIE, montant_total: null, total_retenu: null, reste_du: null });
    expect(html).toMatch(/id="seizure-total-edit"[^>]*value=""/);
    expect(html).not.toContain('Reste dû');
  });

  it('en pourcentage, pas de mensualité à saisir', () => {
    const html = rendu({ ...SAISIE, calculation_mode: 'pourcentage', percentage: 10, amount: undefined });
    expect(html).not.toContain('seizure-amount-edit');
    expect(html).toContain('seizure-total-edit');
  });
});
