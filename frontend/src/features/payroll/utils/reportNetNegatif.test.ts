import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { invaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';
import {
  clesApresReport,
  executerReport,
  messageEchecReport,
  messageSuccesReport,
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
  saisies: [],
  autre_retenue_sur_le_net: null,
  verrou: null,
};
const REPORT = { id: 's-1', name: 'Report NAP négatif 09/2026', amount: -115.43 };
const AVEC_REPORT: EtatReportNetNegatif = {
  ...SANS_REPORT,
  saisie: REPORT,
  saisies: [REPORT],
};

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
    const vue = vueDuReport(AVEC_REPORT);
    expect(vue.texte).toBe('Reporté sur octobre 2026 (115,43 €)');
    expect(vue.action).toBeNull();
    expect(vue.bouton).toBeNull();
    expect(vue.lien).toBe('/saisies?year=2026&month=10&employee=e1');
  });

  it('montant différent : « Report à mettre à jour : a € → b € » sur la même saisie', () => {
    const saisie = { ...REPORT, amount: -100 };
    const vue = vueDuReport({ ...SANS_REPORT, saisie, saisies: [saisie] });
    expect(vue.texte).toBe('Report à mettre à jour : 100,00 € → 115,43 €');
    expect(vue.bouton).toBe('Mettre à jour le report');
    expect(vue.action).toBe('mettre_a_jour');
  });

  it('net redevenu positif avec un report : proposer de le supprimer', () => {
    const vue = vueDuReport({
      ...AVEC_REPORT,
      net_a_payer: 12,
      montant_a_reporter: 0,
    });
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
    const vue = vueDuReport({
      ...AVEC_REPORT,
      net_a_payer: 3,
      montant_a_reporter: 0,
      verrou: 'mois_cloture',
    });
    expect(vue.desactive).toBe(true);
    expect(vue.explication).toBe('La paie d’octobre 2026 est clôturée : impossible d’en retirer le report.');
  });

  it('décembre se reporte sur janvier de l’année suivante', () => {
    const vue = vueDuReport({ ...SANS_REPORT, mois: 12, annee_suivante: 2027, mois_suivant: 1 });
    expect(vue.bouton).toBe('Reporter 115,43 € sur janvier 2027');
  });

  it('montant déjà juste et mois suivant validé : le lien s’accompagne de l’explication, sans écriture', () => {
    const vue = vueDuReport({ ...AVEC_REPORT, verrou: 'bulletin_valide' });
    expect(vue.texte).toBe('Reporté sur octobre 2026 (115,43 €)');
    expect(vue.action).toBeNull();
    expect(vue.bouton).toBeNull();
    expect(vue.lien).toBe('/saisies?year=2026&month=10&employee=e1');
    expect(vue.explication).toBe(
      'Le bulletin d’octobre 2026 est déjà validé : impossible d’y reporter la somme.'
    );
  });

  it('retenue sous un autre nom : pas de second report, montant nommé, lien vers les saisies', () => {
    const vue = vueDuReport({
      ...SANS_REPORT,
      autre_retenue_sur_le_net: { id: 's-9', name: 'Acompte', amount: -300 },
    });
    expect(vue.texte).toBe(
      'Une retenue sur le net de 300,00 € existe déjà en octobre 2026, sous un autre nom. Ouvrez les saisies avant d’ajouter le report.'
    );
    expect(vue.action).toBeNull();
    expect(vue.bouton).toBeNull();
    expect(vue.lien).toBe('/saisies?year=2026&month=10&employee=e1');
  });

  it('plusieurs reports reconnus : chaque montant, chacun déduit, chemin pour n’en garder qu’un', () => {
    const a = REPORT;
    const b = { id: 's-2', name: 'Report NAP négatif 09/2026', amount: -100 };
    const vue = vueDuReport({ ...SANS_REPORT, saisie: a, saisies: [a, b] });
    expect(vue.texte).toBe(
      'Plusieurs reports existent déjà en octobre 2026 : 115,43 € et 100,00 €. Chacun est déduit du net tant que la ligne existe. Ouvrez les saisies pour n’en garder qu’un.'
    );
    expect(vue.action).toBeNull();
    expect(vue.bouton).toBeNull();
    expect(vue.lien).toBe('/saisies?year=2026&month=10&employee=e1');
  });
});

describe('executerReport : l’endpoint du report, dans la société du bulletin', () => {
  it('envoie l’action au bulletin, sans poster une seconde saisie', async () => {
    const appels: unknown[][] = [];
    const api = {
      executer: async (...a: unknown[]) => {
        appels.push(a);
      },
    };
    await executerReport('creer', SANS_REPORT, api);
    await executerReport('mettre_a_jour', AVEC_REPORT, api);
    await executerReport('supprimer', AVEC_REPORT, api);
    expect(appels).toEqual([
      ['ps-9', 'creer', 'co-1'],
      ['ps-9', 'mettre_a_jour', 'co-1'],
      ['ps-9', 'supprimer', 'co-1'],
    ]);
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
    expect(isPersistableQueryKey(queryKeys.reportsNetNegatifDuMois('co-1', 2026, 9))).toBe(false);
  });

  it('une régénération recharge aussi les reports groupés du mois', async () => {
    const client = new QueryClient();
    const cle = queryKeys.reportsNetNegatifDuMois('co-1', 2026, 9);
    client.setQueryData(cle, []);
    await invaliderApresBulletin(client, 'co-1', 'e1');
    expect(client.getQueryState(cle)?.isInvalidated).toBe(true);
  });
});
