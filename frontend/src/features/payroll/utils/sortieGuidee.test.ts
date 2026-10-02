import { describe, expect, it } from 'vitest';

import { payrollGenerationBlockReason } from './employmentPeriod';
import {
  BOUTON_CREER_LE_DEPART,
  BOUTON_GENERER_BULLETIN_SORTIE,
  bandeauxSortieDuMois,
  dateDeFinDuContrat,
  messageCreerLeDepart,
  messageGenererBulletinSortie,
} from './sortieGuidee';

const JEANNE = {
  id: 'e-cdd',
  first_name: 'Jeanne',
  last_name: 'Essai',
  hire_date: '2025-01-01',
  contract_end_date: '2026-09-15',
};

describe('qui déclenche le bandeau « créez son départ »', () => {
  it('une fin de contrat dans le mois, sans départ : le bandeau', () => {
    const bandeaux = bandeauxSortieDuMois([JEANNE], [], 2026, 9);
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].employeeId).toBe('e-cdd');
    expect(bandeaux[0].etape).toBe('creer_depart');
    expect(bandeaux[0].bouton).toBe(BOUTON_CREER_LE_DEPART);
  });

  it('une lecture groupée des départs, pas une décision par requête', () => {
    const autre = {
      id: 'e-reste',
      first_name: 'Paul',
      last_name: 'Essai',
      contract_end_date: '2026-12-31',
    };
    const bandeaux = bandeauxSortieDuMois(
      [JEANNE, autre],
      [{ employee_id: 'e-reste', last_working_day: '2026-12-31', status: 'demission_effective' }],
      2026,
      9
    );
    expect(bandeaux.map((b) => b.employeeId)).toEqual(['e-cdd']);
  });

  it('un départ déjà créé, sans bulletin : proposer de générer le bulletin de sortie', () => {
    const bandeaux = bandeauxSortieDuMois(
      [{ ...JEANNE, current_exit_id: 'exit-1' }],
      [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'demission_effective' }],
      2026,
      9
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].etape).toBe('generer_bulletin');
    expect(bandeaux[0].bouton).toBe(BOUTON_GENERER_BULLETIN_SORTIE);
    expect(bandeaux[0].message).toBe(messageGenererBulletinSortie(JEANNE));
  });

  it('un départ archivé, sans bulletin : même proposition de génération', () => {
    const bandeaux = bandeauxSortieDuMois(
      [JEANNE],
      [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'archivee' }],
      2026,
      9
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].etape).toBe('generer_bulletin');
  });

  it('un départ créé, bulletin du mois déjà là : plus de bandeau', () => {
    expect(
      bandeauxSortieDuMois(
        [{ ...JEANNE, current_exit_id: 'exit-1' }],
        [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'demission_effective' }],
        2026,
        9,
        new Set(['e-cdd'])
      )
    ).toEqual([]);
  });

  it('un départ annulé ne compte pas : le bandeau revient', () => {
    const bandeaux = bandeauxSortieDuMois(
      [JEANNE],
      [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'annulee' }],
      2026,
      9
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].etape).toBe('creer_depart');
  });

  it('une fin hors du mois affiché : rien', () => {
    expect(bandeauxSortieDuMois([JEANNE], [], 2026, 8)).toEqual([]);
    expect(bandeauxSortieDuMois([JEANNE], [], 2026, 10)).toEqual([]);
  });

  it('une fin de contrat propose le motif fin de CDD et son dernier jour', () => {
    const [bandeau] = bandeauxSortieDuMois([JEANNE], [], 2026, 9);
    expect(bandeau.dateIso).toBe('2026-09-15');
    expect(bandeau.motifPropose).toBe('fin_cdd');
  });

  it('une date de sortie déjà connue, sans date de fin de contrat : le bandeau', () => {
    const bandeaux = bandeauxSortieDuMois(
      [
        {
          id: 'e-sortie',
          first_name: 'Jeanne',
          last_name: 'Essai',
          hire_date: '2025-01-01',
          exit_last_working_day: '2026-09-20',
        },
      ],
      [],
      2026,
      9
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].dateIso).toBe('2026-09-20');
    // Sans fin de contrat, le motif du départ n'est pas deviné.
    expect(bandeaux[0].motifPropose).toBeNull();
  });

  it("un ancien départ de janvier n'est pas déjà créé pour une fin d'avril", () => {
    const reembauche = {
      id: 'e-cdd',
      first_name: 'Jeanne',
      last_name: 'Essai',
      hire_date: '2026-02-01',
      contract_end_date: '2026-04-15',
      current_exit_id: null,
    };
    const bandeaux = bandeauxSortieDuMois(
      [reembauche],
      [{ employee_id: 'e-cdd', last_working_day: '2026-01-31', status: 'archivee' }],
      2026,
      4
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].etape).toBe('creer_depart');
    expect(bandeaux[0].bouton).toBe(BOUTON_CREER_LE_DEPART);
  });
});

describe('génération du bulletin de sortie', () => {
  it('une fiche incomplète : la même raison que la ligne du mois, sans clic', () => {
    const fiche = {
      ...JEANNE,
      current_exit_id: 'exit-1',
      missing_payroll_fields: ['Coordonnées bancaires (RIB)'],
    };
    const raison = payrollGenerationBlockReason(fiche, 2026, 9);
    expect(raison).toBe('Fiche à compléter : Coordonnées bancaires (RIB)');

    const bandeaux = bandeauxSortieDuMois(
      [fiche],
      [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'demission_effective' }],
      2026,
      9
    );
    expect(bandeaux).toHaveLength(1);
    expect(bandeaux[0].etape).toBe('generer_bulletin');
    expect(bandeaux[0].peutGenerer).toBe(false);
    expect(bandeaux[0].raisonBlocage).toBe(raison);
    expect(bandeaux[0].message).toContain(raison);
  });

  it('une fiche complète : le bouton de génération reste actif', () => {
    const bandeaux = bandeauxSortieDuMois(
      [{ ...JEANNE, current_exit_id: 'exit-1' }],
      [{ employee_id: 'e-cdd', last_working_day: '2026-09-15', status: 'demission_effective' }],
      2026,
      9
    );
    expect(bandeaux[0].peutGenerer).toBe(true);
    expect(bandeaux[0].raisonBlocage).toBeNull();
    expect(bandeaux[0].bouton).toBe(BOUTON_GENERER_BULLETIN_SORTIE);
  });
});

describe('texte du bandeau', () => {
  it('prénom et nom, date JJ/MM, pas de X', () => {
    const message = messageCreerLeDepart(JEANNE, '2026-09-15');
    expect(message).toBe("Jeanne Essai quitte l'entreprise le 15/09 : créez son départ.");
    expect(message).not.toMatch(/\bX\b/);
  });

  it('sans prénom : le nom seul', () => {
    expect(messageCreerLeDepart({ last_name: 'Essai' }, '2026-09-15')).toBe(
      "Essai quitte l'entreprise le 15/09 : créez son départ."
    );
  });

  it('la date de fin retenue est celle du contrat, sinon la sortie connue', () => {
    expect(dateDeFinDuContrat(JEANNE)).toBe('2026-09-15');
    expect(dateDeFinDuContrat({ exit_last_working_day: '2026-09-20' })).toBe('2026-09-20');
    expect(dateDeFinDuContrat({})).toBeNull();
  });
});
