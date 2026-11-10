import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { RelectureIaARegarder } from './RelectureIaARegarder';
import { RelectureIaBouton } from './RelectureIaBouton';
import { queryKeys } from '@/lib/queryKeys';
import type {
  ARegarder,
  EtatRelecture,
  PreparationRelecture,
  RelectureIa,
} from '@/api/relectureIa';
import {
  coutAffiche,
  raisonBoutonGrise,
  selectionRelecture,
  texteProgression,
} from '@/features/payroll/utils/relectureIa';

vi.mock('@/hooks/queries/useCompanyId', () => ({ useActiveCompanyId: () => 'societe-1' }));

const preparation = (extra: Partial<PreparationRelecture> = {}): PreparationRelecture => ({
  year: 2026,
  month: 10,
  societes: [
    { company_id: 'c1', nom: 'Alpha', bulletins_generes: 40, a_relire: 12, salaries: [], sans_regles: false },
  ],
  total_a_relire: 12,
  cout_unitaire_eur: 0.08,
  cout_estime_eur: 0.96,
  derniere_relecture: null,
  relecture_en_cours: null,
  blocage: null,
  ...extra,
});

const relecture = (extra: Partial<RelectureIa> = {}): RelectureIa => ({
  id: 'r1',
  statut: 'en_cours',
  year: 2026,
  month: 10,
  total: 40,
  traites: 12,
  echecs: 0,
  points: 0,
  message: null,
  termine_at: null,
  ...extra,
});

type Cache = {
  peutLancer?: boolean;
  preparation?: PreparationRelecture;
  etat?: EtatRelecture;
};

const bouton = ({ peutLancer, preparation: prep, etat }: Cache) => {
  const client = new QueryClient();
  if (peutLancer !== undefined) {
    client.setQueryData(queryKeys.relectureIaDroits(), { peut_lancer: peutLancer });
  }
  if (prep) client.setQueryData(queryKeys.relectureIaPreparation(2026, 10), prep);
  if (etat) client.setQueryData(queryKeys.relectureIaEtat(), etat);
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(RelectureIaBouton, { year: 2026, month: 10, titreMois: 'Octobre 2026' }),
    ),
  );
};

const bloc = (donnees: ARegarder | undefined) => {
  const client = new QueryClient();
  if (donnees) {
    client.setQueryData(queryKeys.relectureIaARegarder('societe-1', 2026, 10), donnees);
  }
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(MemoryRouter, null, createElement(RelectureIaARegarder, { year: 2026, month: 10 })),
    ),
  );
};

describe('bouton « Relire la paie avec l’IA »', () => {
  it('visible pour le compte autorisé', () => {
    expect(bouton({ peutLancer: true, preparation: preparation() })).toContain(
      'Relire la paie avec l’IA',
    );
  });

  it('absent pour un autre compte', () => {
    expect(bouton({ peutLancer: false, preparation: preparation() })).toBe('');
  });

  it('absent tant que le droit n’est pas connu', () => {
    expect(bouton({})).toBe('');
  });

  it('grisé et dit pourquoi quand il n’y a rien à relire', () => {
    const html = bouton({
      peutLancer: true,
      preparation: preparation({ total_a_relire: 0, cout_estime_eur: 0 }),
    });
    expect(html).toContain('Rien à relire');
    expect(html).toContain('disabled');
  });

  it('grisé et dit pourquoi quand la clé manque', () => {
    const html = bouton({
      peutLancer: true,
      preparation: preparation({ blocage: 'La relecture n’est pas encore branchée.' }),
    });
    expect(html).toContain('pas encore branchée');
    expect(html).toContain('disabled');
  });

  it('montre la progression pendant une relecture', () => {
    const html = bouton({
      peutLancer: true,
      preparation: preparation(),
      etat: { relecture: relecture() },
    });
    expect(html).toContain('12 sur 40');
    expect(html).toContain('disabled');
  });

  it('garde le message de fin de la dernière relecture du mois', () => {
    const html = bouton({
      peutLancer: true,
      preparation: preparation(),
      etat: {
        relecture: relecture({ statut: 'terminee', message: '28 bulletins relus, 2 points à regarder.' }),
      },
    });
    expect(html).toContain('28 bulletins relus');
  });

  it('ne montre pas le message d’un autre mois', () => {
    const html = bouton({
      peutLancer: true,
      preparation: preparation(),
      etat: { relecture: relecture({ statut: 'terminee', month: 9, message: 'Septembre fini.' }) },
    });
    expect(html).not.toContain('Septembre fini');
  });
});

describe('bloc « À regarder »', () => {
  const point = {
    bulletin_relu_id: 'b1',
    payslip_id: 'p1',
    employee_id: 'e1',
    gravite: 'important' as const,
    ligne: 'Salaire de base',
    raison: 'Le montant de 2500 € surprend.',
    bulletin_modifie_depuis: false,
    nom: 'Alix Testeur',
  };

  it('dit si le mois n’a pas été relu', () => {
    expect(
      bloc({ relecture_faite: false, relu_le: null, points: [], autres_points: 0 }),
    ).toContain('pas encore été relue');
  });

  it('dit quand rien n’est relevé', () => {
    expect(
      bloc({ relecture_faite: true, relu_le: '2026-11-01T10:00:00Z', points: [], autres_points: 0 }),
    ).toContain('Rien à regarder');
  });

  it('montre le point, sa raison et le geste « Vu »', () => {
    const html = bloc({
      relecture_faite: true,
      relu_le: '2026-11-01T10:00:00Z',
      points: [point],
      autres_points: 0,
    });
    expect(html).toContain('Alix Testeur');
    expect(html).toContain('Salaire de base');
    expect(html).toContain('Important');
    expect(html).toContain('Vu, c’est normal');
    expect(html).toContain('/payslips/p1/edit');
  });

  it('compte les points laissés', () => {
    const html = bloc({
      relecture_faite: true,
      relu_le: '2026-11-01T10:00:00Z',
      points: [point],
      autres_points: 4,
    });
    expect(html).toContain('4 autres points moins importants');
  });

  it('prévient si le bulletin a changé depuis', () => {
    const html = bloc({
      relecture_faite: true,
      relu_le: '2026-11-01T10:00:00Z',
      points: [{ ...point, bulletin_modifie_depuis: true }],
      autres_points: 0,
    });
    expect(html).toContain('changé depuis la relecture');
  });
});

describe('textes de la relecture', () => {
  it('progression', () => {
    expect(texteProgression(relecture({ traites: 3, total: 9 }))).toBe('Relecture en cours : 3 sur 9.');
  });

  it('coût en euros, jamais à zéro s’il y a des bulletins', () => {
    expect(coutAffiche(0.96)).toBe('environ 0,96 €');
    expect(coutAffiche(0.001)).toBe('moins de 0,01 €');
  });

  it('raison du bouton grisé', () => {
    expect(raisonBoutonGrise(preparation({ total_a_relire: 0 }))).toContain('Rien à relire');
    expect(raisonBoutonGrise(preparation({ total_a_relire: 0, societes: [] }))).toContain('Aucun bulletin généré');
    expect(raisonBoutonGrise(preparation())).toBeNull();
    expect(raisonBoutonGrise(undefined)).toBeNull();
  });
});

describe('choix des salariés', () => {
  const societes = [
    {
      company_id: 'c1',
      nom: 'Alpha',
      bulletins_generes: 3,
      a_relire: 3,
      sans_regles: false,
      salaries: [
        { employee_id: 'e1', nom: 'A', bulletins: 2 },
        { employee_id: 'e2', nom: 'B', bulletins: 1 },
      ],
    },
    {
      company_id: 'c2',
      nom: 'Beta',
      bulletins_generes: 1,
      a_relire: 1,
      sans_regles: false,
      salaries: [{ employee_id: 'e3', nom: 'C', bulletins: 1 }],
    },
  ];

  it('par défaut, tout le monde', () => {
    expect(selectionRelecture(societes, new Set(), new Set())).toEqual({
      nombre: 4,
      companyIds: ['c1', 'c2'],
      employeeIds: null,
    });
  });

  it('un salarié retiré baisse le nombre, donc le prix', () => {
    expect(selectionRelecture(societes, new Set(), new Set(['e1']))).toEqual({
      nombre: 2,
      companyIds: ['c1', 'c2'],
      employeeIds: ['e2', 'e3'],
    });
  });

  it('une société dont tous les salariés sont retirés n’est pas lancée', () => {
    const choix = selectionRelecture(societes, new Set(), new Set(['e3']));
    expect(choix.companyIds).toEqual(['c1']);
    expect(choix.nombre).toBe(3);
  });

  it('un salarié retiré dans une société décochée ne compte plus', () => {
    expect(selectionRelecture(societes, new Set(['c2']), new Set(['e3'])).employeeIds).toBeNull();
  });

  it('aucune case cochée : rien à lancer', () => {
    expect(selectionRelecture(societes, new Set(['c1', 'c2']), new Set()).nombre).toBe(0);
  });
});
