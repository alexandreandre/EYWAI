import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';
import { QueryClient, QueryObserver, type QueryKey } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { clesAInvaliderApresEffacement } from '@/features/payroll/utils/heuresSurArret';
import {
  clesApresAnnulation,
  clesAInvaliderApresBulletin,
  clesAutourDesBulletins,
  clesDeLaPaieDuMois,
  invaliderApresBulletin,
  invaliderCles,
} from '@/features/payroll/utils/invalidationsBulletin';

/** Les requêtes que montrent la paie du mois, la fiche salarié et l'écran du bulletin. */
const LISTE_E1 = queryKeys.employeePayslips('co-1', 'e1');
const LISTE_E2 = queryKeys.employeePayslips('co-1', 'e2');
const LISTE_AUTRE_SOCIETE = queryKeys.employeePayslips('co-2', 'e1');
const COMPARAISON = queryKeys.payslipComparison('ps-1');
const TENDANCE = queryKeys.payslipTrend('ps-1');
const ANOMALIES = queryKeys.payslipsAnomalies('co-1', 2026, 9);
const DOCUMENTS = queryKeys.documentsExplorer('co-1');
const PREFLIGHT = queryKeys.payrollPreflight('co-1', 2026, 9);
const PREFLIGHT_AUTRE_MOIS = queryKeys.payrollPreflight('co-1', 2026, 8);
const PREFLIGHT_AUTRE_SOCIETE = queryKeys.payrollPreflight('co-2', 2026, 9);
const SALARIES = queryKeys.employees('co-1');
const FICHE = queryKeys.employee('co-1', 'e1');

function clientAvec(cles: readonly QueryKey[]): QueryClient {
  const client = new QueryClient();
  for (const key of cles) client.setQueryData(key, 'donnée');
  return client;
}

const TOUTES = [
  LISTE_E1,
  LISTE_E2,
  LISTE_AUTRE_SOCIETE,
  COMPARAISON,
  TENDANCE,
  ANOMALIES,
  DOCUMENTS,
  PREFLIGHT,
  PREFLIGHT_AUTRE_MOIS,
  PREFLIGHT_AUTRE_SOCIETE,
  SALARIES,
  FICHE,
];

function invalidee(client: QueryClient, key: QueryKey): boolean | undefined {
  return client.getQueryState(key)?.isInvalidated;
}

describe('invaliderApresBulletin : après génération, régénération ou suppression', () => {
  it('la liste des bulletins du salarié, les requêtes du bulletin et la paie du mois sont invalidées', async () => {
    const client = clientAvec(TOUTES);

    await invaliderApresBulletin(client, 'co-1', 'e1');

    for (const key of [LISTE_E1, COMPARAISON, TENDANCE, ANOMALIES, DOCUMENTS, PREFLIGHT, PREFLIGHT_AUTRE_MOIS]) {
      expect(invalidee(client, key), JSON.stringify(key)).toBe(true);
    }
  });

  it('rien hors du salarié et de la société : autre salarié, autre société, fiche, liste des salariés', async () => {
    const client = clientAvec(TOUTES);

    await invaliderApresBulletin(client, 'co-1', 'e1');

    for (const key of [LISTE_E2, LISTE_AUTRE_SOCIETE, PREFLIGHT_AUTRE_SOCIETE, SALARIES, FICHE]) {
      expect(invalidee(client, key), JSON.stringify(key)).toBe(false);
    }
  });

  it('salarié inconnu (bulletin introuvable) : toutes les listes de bulletins de la société', async () => {
    const client = clientAvec(TOUTES);

    await invaliderApresBulletin(client, 'co-1', undefined);

    expect(invalidee(client, LISTE_E1)).toBe(true);
    expect(invalidee(client, LISTE_E2)).toBe(true);
    expect(invalidee(client, PREFLIGHT)).toBe(true);
    expect(invalidee(client, LISTE_AUTRE_SOCIETE)).toBe(false);
    expect(invalidee(client, FICHE)).toBe(false);
  });

  it('attend le rechargement de la liste affichée avant de rendre la main', async () => {
    const client = new QueryClient();
    let lectures = 0;
    // La liste à l'écran : un observateur la tient active.
    const vue = new QueryObserver(client, {
      queryKey: LISTE_E1,
      queryFn: async () => {
        lectures += 1;
        return ['bulletin rechargé'];
      },
      staleTime: Infinity,
      initialData: ['bulletin périmé'],
    });
    const arret = vue.subscribe(() => undefined);

    await invaliderApresBulletin(client, 'co-1', 'e1');

    expect(lectures).toBe(1);
    expect(client.getQueryData(LISTE_E1)).toEqual(['bulletin rechargé']);
    arret();
  });
});

describe('clesAInvaliderApresBulletin', () => {
  it('la liste du salarié, puis tout ce qui entoure les bulletins', () => {
    expect(clesAInvaliderApresBulletin('co-1', 'e1')).toEqual([
      LISTE_E1,
      ...clesAutourDesBulletins('co-1'),
    ]);
  });

  it('autour des bulletins : comparaison, tendance, anomalies, report du net négatif, documents et paie du mois', () => {
    expect(clesAutourDesBulletins('co-1')).toEqual([
      queryKeys.payslipComparisonTous(),
      queryKeys.payslipTrendTous(),
      queryKeys.payslipsAnomaliesTousMois('co-1'),
      queryKeys.reportNetNegatifTous('co-1'),
      DOCUMENTS,
      ...clesDeLaPaieDuMois('co-1'),
    ]);
  });
});

describe('invaliderCles', () => {
  it('invalide chaque clé reçue, et seulement elles', async () => {
    const client = clientAvec(TOUTES);

    await invaliderCles(client, [LISTE_E2, PREFLIGHT]);

    expect(invalidee(client, LISTE_E2)).toBe(true);
    expect(invalidee(client, PREFLIGHT)).toBe(true);
    expect(invalidee(client, LISTE_E1)).toBe(false);
  });
});

describe('cohérence avec l’effacement d’heures', () => {
  it('l’effacement invalide la même paie du mois que la génération', () => {
    const effacement = clesAInvaliderApresEffacement('co-1', 'e1');
    for (const key of clesDeLaPaieDuMois('co-1')) {
      expect(effacement).toContainEqual(key);
    }
  });
});

describe('clesApresAnnulation : un lot annulé', () => {
  it('le salarié du bulletin en cours : le serveur a pu le générer', () => {
    expect(clesApresAnnulation('co-1', 'e1')).toEqual(clesAInvaliderApresBulletin('co-1', 'e1'));
  });

  it('aucun bulletin en cours : ce qui entoure les bulletins seulement', () => {
    expect(clesApresAnnulation('co-1', null)).toEqual(clesAutourDesBulletins('co-1'));
  });

  it('le lot l’utilise à l’annulation, avec le salarié du bulletin interrompu', () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, '../hooks/usePayrollGeneration.ts'),
      'utf8'
    );
    expect(source).toMatch(/clesApresAnnulation\(companyId, salarieInterrompu\)/);
  });
});
