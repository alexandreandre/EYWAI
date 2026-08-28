import { describe, expect, it } from 'vitest';

import {
  PAYROLL_FOCUS_NAV_URLS,
  isPayrollFocusActive,
  isPayrollFocusAllowed,
  restrictToPayrollFocus,
} from './payrollFocus';

describe('PAYROLL_FOCUS_NAV_URLS', () => {
  it('contient exactement 19 entrées, sans doublon', () => {
    expect(PAYROLL_FOCUS_NAV_URLS).toHaveLength(19);
    expect(new Set(PAYROLL_FOCUS_NAV_URLS).size).toBe(19);
  });
});

describe('isPayrollFocusAllowed', () => {
  it('autorise chaque entrée de menu du périmètre', () => {
    for (const url of PAYROLL_FOCUS_NAV_URLS) {
      expect(isPayrollFocusAllowed(url)).toBe(true);
    }
  });

  it('autorise les sous-routes ouvertes depuis ces écrans', () => {
    expect(isPayrollFocusAllowed('/employees/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payroll/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payslips/abc-123/edit')).toBe(true);
  });

  it('refuse les écrans hors périmètre', () => {
    for (const url of [
      '/cse',
      '/formation',
      '/recruitment',
      '/onboarding',
      '/employee-exits',
      '/trial-periods',
      '/teams',
      '/documents',
      '/residence-permits',
      '/medical-follow-up',
      '/annual-reviews',
      '/analytics',
      '/analytics-paie',
      '/analytics-gestion',
      '/users',
      '/company',
      '/planning',
      '/badgeuse-rh',
      '/augmentations-et-promotions',
    ]) {
      expect(isPayrollFocusAllowed(url)).toBe(false);
    }
  });

  it('ignore la query string et le fragment', () => {
    expect(isPayrollFocusAllowed('/employees?alert=deadlines')).toBe(true);
    expect(isPayrollFocusAllowed('/annual-reviews?focus=upcoming')).toBe(false);
    expect(isPayrollFocusAllowed('/formation#entretiens')).toBe(false);
  });

  it('tolère la barre oblique finale', () => {
    expect(isPayrollFocusAllowed('/exports/')).toBe(true);
    expect(isPayrollFocusAllowed('/cse/')).toBe(false);
  });

  it('ne confond pas deux chemins de même préfixe textuel', () => {
    expect(isPayrollFocusAllowed('/employee-loans')).toBe(true);
    expect(isPayrollFocusAllowed('/employee-exits')).toBe(false);
  });
});

describe('isPayrollFocusActive', () => {
  it('est actif pour un compte client', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'gaelle.bouali@maji-invest.fr' })).toBe(true);
    expect(isPayrollFocusActive({ role: 'admin', email: 'vanessa.amate@maji-invest.fr' })).toBe(true);
  });

  it('est inactif pour un administrateur plateforme', () => {
    expect(isPayrollFocusActive({ role: 'rh', is_platform_admin: true })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', is_super_admin: true })).toBe(false);
  });

  it('est inactif pour un e-mail de la liste de contournement, quelle que soit la casse', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'alexandreandre2004@gmail.com' })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', email: 'Alexandreandre2004@GMAIL.com ' })).toBe(false);
  });

  it('est inactif sans utilisateur', () => {
    expect(isPayrollFocusActive(null)).toBe(false);
    expect(isPayrollFocusActive(undefined)).toBe(false);
  });
});

const teamGroups = [
  { items: [{ url: '/analytics' }] },
  {
    label: 'Effectifs',
    items: [
      { url: '/employees' },
      { url: '/recruitment' },
      { url: '/onboarding' },
      { url: '/employee-exits' },
      { url: '/trial-periods' },
      { url: '/teams' },
    ],
  },
  { label: 'Suivi documents', items: [{ url: '/documents' }, { url: '/residence-permits' }] },
];

const gestionGroups = [
  {
    items: [
      { url: '/analytics-gestion' },
      { url: '/badgeuse-rh' },
      { url: '/schedules' },
      { url: '/planning' },
      { url: '/users' },
    ],
  },
];

const paieGroups = [
  { items: [{ url: '/analytics-paie' }] },
  {
    workflow: true,
    items: [
      { url: '/schedules' },
      { url: '/leaves' },
      { url: '/suivi-ijss' },
      { url: '/suivi-temps-travail' },
      { url: '/suivi-contingent-hs' },
      { url: '/suivi-modulation' },
      { url: '/suivi-cet' },
      { url: '/expenses' },
      { url: '/saisies' },
      { url: '/salary-seizures' },
      { url: '/salary-advances' },
      { url: '/employee-loans' },
    ],
  },
  {
    label: 'Outils paie',
    items: [
      { url: '/simulation' },
      { url: '/rates' },
      { url: '/taux-pas' },
      { url: '/exports' },
      { url: '/payroll' },
    ],
  },
];

const urlsOf = (groups: { items: { url: string }[] }[]) =>
  groups.flatMap((g) => g.items.map((i) => i.url));

describe('restrictToPayrollFocus', () => {
  it('ne garde que Collaborateurs dans la section Effectifs', () => {
    const out = restrictToPayrollFocus('team', teamGroups);
    expect(urlsOf(out)).toEqual(['/employees']);
  });

  it('supprime entièrement la section Gestion', () => {
    expect(restrictToPayrollFocus('gestion', gestionGroups)).toEqual([]);
  });

  it('garde tout le parcours paie sauf Analytics Paie', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(urlsOf(out)).not.toContain('/analytics-paie');
    expect(urlsOf(out)).toHaveLength(17);
  });

  it('conserve les métadonnées de groupe', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(out.find((g) => g.label === 'Outils paie')).toBeDefined();
    expect(out.find((g) => (g as { workflow?: boolean }).workflow)).toBeDefined();
  });

  it('supprime les groupes devenus vides', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(out).toHaveLength(2);
  });

  it('ne mute pas les groupes reçus', () => {
    const before = urlsOf(paieGroups).length;
    restrictToPayrollFocus('paie', paieGroups);
    expect(urlsOf(paieGroups)).toHaveLength(before);
  });

  it('produit exactement les 19 URL du périmètre, toutes sections confondues', () => {
    const all = [
      '/',
      ...urlsOf(restrictToPayrollFocus('team', teamGroups)),
      ...urlsOf(restrictToPayrollFocus('gestion', gestionGroups)),
      ...urlsOf(restrictToPayrollFocus('paie', paieGroups)),
    ];
    expect(new Set(all)).toEqual(new Set(PAYROLL_FOCUS_NAV_URLS));
  });
});
