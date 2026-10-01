import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { invaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';
import {
  clesApresReport,
  executerReport,
  messageEchecReport,
  messageSuccesReport,
  saisieDuReport,
  vueDuReport,
  type EtatReportNetNegatif,
} from '@/features/payroll/utils/reportNetNegatif';

const SANS_REPORT: EtatReportNetNegatif = {
  payslip_id: 'ps-9',
  company_id: 'co-1',
  employee_id: 'e1',
  annee: 2026,
  mois: 9,
  net_a_payer: -115.43,
  montant_a_reporter: 115.43,
  annee_suivante: 2026,
  mois_suivant: 10,
  nom_du_report: 'Report NAP négatif 09/2026',
  saisie: null,
  verrou: null,
};
const REPORT = { id: 's-1', name: 'Report NAP négatif 09/2026', amount: -115.43 };

describe('vueDuReport : ce que propose le bouton', () => {
  it('sans report : alerte nommée et bouton « Reporter X € sur <mois suivant> »', () => {
    const vue = vueDuReport(SANS_REPORT);
    expect(vue.visible).toBe(true);
    expect(vue.texte).toBe(
      'Net à payer négatif : −115,43 €. Rien ne sera viré en septembre 2026. Reprenez cette somme en octobre 2026.'
    );
    expect(vue.bouton).toBe('Reporter 115,43 € sur octobre 2026');
    expect(vue.action).toBe('creer');
    expect(vue.desactive).toBe(false);
  });

  it('report du même montant : « Reporté », un lien, aucun doublon possible', () => {
    const vue = vueDuReport({ ...SANS_REPORT, saisie: REPORT });
    expect(vue.texte).toBe('Reporté sur octobre 2026 (115,43 €)');
    expect(vue.action).toBeNull();
    expect(vue.bouton).toBeNull();
    expect(vue.lien).toBe('/saisies?year=2026&month=10&employee=e1');
  });

  it('montant différent : « Report à mettre à jour : a € → b € » sur la même saisie', () => {
    const vue = vueDuReport({ ...SANS_REPORT, saisie: { ...REPORT, amount: -100 } });
    expect(vue.texte).toBe('Report à mettre à jour : 100,00 € → 115,43 €');
    expect(vue.bouton).toBe('Mettre à jour le report');
    expect(vue.action).toBe('mettre_a_jour');
  });

  it('net redevenu positif avec un report : proposer de le supprimer', () => {
    const vue = vueDuReport({ ...SANS_REPORT, net_a_payer: 12, montant_a_reporter: 0, saisie: REPORT });
    expect(vue.texte).toBe('Le net n’est plus négatif : supprimer le report d’octobre 2026 ?');
    expect(vue.bouton).toBe('Supprimer le report');
    expect(vue.action).toBe('supprimer');
  });

  it('net positif sans report : rien à montrer', () => {
    expect(vueDuReport({ ...SANS_REPORT, net_a_payer: 12, montant_a_reporter: 0 }).visible).toBe(false);
  });

  it('bulletin suivant validé : bouton désactivé, expliqué, sans glisser sur un autre mois', () => {
    const vue = vueDuReport({ ...SANS_REPORT, verrou: 'bulletin_valide' });
    expect(vue.desactive).toBe(true);
    expect(vue.bouton).toBe('Reporter 115,43 € sur octobre 2026');
    expect(vue.explication).toBe(
      'Le bulletin d’octobre 2026 est déjà validé : impossible d’y reporter la somme.'
    );
  });

  it('mois suivant clôturé : bouton désactivé, expliqué', () => {
    const vue = vueDuReport({ ...SANS_REPORT, saisie: REPORT, net_a_payer: 3, montant_a_reporter: 0, verrou: 'mois_cloture' });
    expect(vue.desactive).toBe(true);
    expect(vue.explication).toBe('La paie d’octobre 2026 est clôturée : impossible d’en retirer le report.');
  });

  it('décembre se reporte sur janvier de l’année suivante', () => {
    const vue = vueDuReport({ ...SANS_REPORT, mois: 12, annee_suivante: 2027, mois_suivant: 1 });
    expect(vue.bouton).toBe('Reporter 115,43 € sur janvier 2027');
  });
});

describe('saisieDuReport : la saisie « sur le net » du mois suivant', () => {
  it('nommée selon la convention, marquée, hors cotisations et hors impôt', () => {
    expect(saisieDuReport(SANS_REPORT)).toEqual({
      year: 2026,
      month: 10,
      name: 'Report NAP négatif 09/2026',
      description: 'Net à payer négatif du bulletin de septembre 2026, repris sur octobre 2026.',
      amount: -115.43,
      is_socially_taxed: false,
      is_taxable: false,
      sur_le_net: true,
      catalog_prime_id: 'report_nap_negatif',
    });
  });
});

describe('executerReport : les appels à l’API des saisies, dans la société du bulletin', () => {
  function apiEspion() {
    const appels: unknown[][] = [];
    return {
      appels,
      api: {
        creer: async (...a: unknown[]) => void appels.push(['creer', ...a]),
        mettreAJour: async (...a: unknown[]) => void appels.push(['mettreAJour', ...a]),
        supprimer: async (...a: unknown[]) => void appels.push(['supprimer', ...a]),
      },
    };
  }

  it('créer : une saisie au mois suivant, pour la société du bulletin', async () => {
    const { appels, api } = apiEspion();
    await executerReport('creer', SANS_REPORT, api);
    expect(appels).toEqual([['creer', 'e1', saisieDuReport(SANS_REPORT), 'co-1']]);
  });

  it('mettre à jour : la même saisie, au nouveau montant', async () => {
    const { appels, api } = apiEspion();
    await executerReport('mettre_a_jour', { ...SANS_REPORT, saisie: { ...REPORT, amount: -100 } }, api);
    expect(appels).toEqual([['mettreAJour', 's-1', { amount: -115.43 }, 'co-1']]);
  });

  it('supprimer : la saisie existante', async () => {
    const { appels, api } = apiEspion();
    await executerReport('supprimer', { ...SANS_REPORT, saisie: REPORT }, api);
    expect(appels).toEqual([['supprimer', 'e1', 's-1', 'co-1']]);
  });
});

describe('messages', () => {
  it('le succès nomme le montant et le mois', () => {
    expect(messageSuccesReport('creer', SANS_REPORT)).toBe('Report de 115,43 € créé dans les saisies d’octobre');
    expect(messageSuccesReport('mettre_a_jour', SANS_REPORT)).toBe(
      'Report mis à jour : 115,43 € dans les saisies d’octobre'
    );
    expect(messageSuccesReport('supprimer', SANS_REPORT)).toBe('Report supprimé des saisies d’octobre');
  });

  it('l’échec donne la raison de l’API', () => {
    const erreur = { response: { status: 403, data: { detail: 'Accès réservé aux RH.' } } };
    expect(messageEchecReport('creer', erreur)).toBe('Report non créé : Accès réservé aux RH.');
  });

  it('sans raison lisible, le message dit quoi faire, jamais un générique seul', () => {
    const erreur = { response: { status: 500, data: {} } };
    expect(messageEchecReport('supprimer', erreur)).toBe(
      'Report non supprimé : le serveur n’a pas donné de raison (erreur 500). Réessayez, ou corrigez la saisie depuis l’écran Primes.'
    );
  });
});

describe('invalidations après un report', () => {
  it('l’état du report, les bulletins du salarié et la paie du mois', async () => {
    const cles = clesApresReport('co-1', 'e1');
    expect(cles).toContainEqual(queryKeys.reportNetNegatifTous('co-1'));
    expect(cles).toContainEqual(queryKeys.employeePayslips('co-1', 'e1'));
    expect(cles).toContainEqual(queryKeys.payrollPreflightTousMois('co-1'));
  });

  it('une régénération recharge aussi l’état du report (le net a pu changer)', async () => {
    const client = new QueryClient();
    const cle = queryKeys.reportNetNegatif('co-1', 'ps-9');
    client.setQueryData(cle, SANS_REPORT);
    await invaliderApresBulletin(client, 'co-1', 'e1');
    expect(client.getQueryState(cle)?.isInvalidated).toBe(true);
  });

  it('l’état du report n’est jamais persisté', async () => {
    const { isPersistableQueryKey } = await import('@/lib/queryCachePersistence');
    expect(isPersistableQueryKey(queryKeys.reportNetNegatif('co-1', 'ps-9'))).toBe(false);
  });
});
