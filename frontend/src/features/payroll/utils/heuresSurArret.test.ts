import { describe, expect, it } from 'vitest';
import { AxiosError } from 'axios';
import { QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import {
  TITRE_INFO_BULLE_CONFLIT,
  aDesJoursAEffacer,
  bandeauAbsencesDuSalarie,
  choixApresCorrection,
  clesAInvaliderApresEffacement,
  effacerLesJours,
  etatDialogueHeuresSurArret,
  messageEchecEffacement,
  fusionnerJoursEnConflitImport,
  groupesParMois,
  lienCalendrierDuSalarie,
  lienModifierAbsence,
  lireJoursEnConflit,
  lireNatureDuLien,
  lireRefusApresCorrection,
  libelleDesJours,
  messageHeuresEffacees,
  natureDuConflit,
  prenomDe,
  prenomDuBulletin,
  raisonEchecEffacement,
  estJourEnConflit,
  textesDuChoix,
} from './heuresSurArret';

const jour = (j: number, mois = 9, annee = 2026, heures = 9) => ({
  annee,
  mois,
  jour: j,
  heures,
});

describe('lireJoursEnConflit', () => {
  it('garde type_prevu quand le backend le donne', () => {
    expect(
      lireJoursEnConflit([{ annee: 2026, mois: 9, jour: 12, heures: 4, type_prevu: 'arret_maladie' }])
    ).toEqual([{ ...jour(12, 9, 2026, 4), type_prevu: 'arret_maladie' }]);
  });
  it('lit la liste du backend et ignore les entrées invalides', () => {
    expect(
      lireJoursEnConflit([
        { annee: 2026, mois: 9, jour: 7, heures: 9 },
        { annee: 2026, mois: 9, jour: 'x', heures: 1 },
        null,
        { annee: 2026, mois: 9, jour: 8, heures: 4.5 },
      ])
    ).toEqual([jour(7), jour(8, 9, 2026, 4.5)]);
  });
  it('rend une liste vide pour autre chose qu’un tableau', () => {
    expect(lireJoursEnConflit(undefined)).toEqual([]);
    expect(lireJoursEnConflit('7')).toEqual([]);
  });
});

describe('libelleDesJours', () => {
  it('un mois : 7, 8 et 9 septembre', () => {
    expect(libelleDesJours([jour(7), jour(8), jour(9)])).toBe('7, 8 et 9 septembre');
  });
  it('un seul jour', () => {
    expect(libelleDesJours([jour(1)])).toBe('1er septembre');
  });
  it('deux jours', () => {
    expect(libelleDesJours([jour(7), jour(8)])).toBe('7 et 8 septembre');
  });
  it('deux mois : chaque mois garde ses jours', () => {
    expect(libelleDesJours([jour(31, 8), jour(1), jour(2)])).toBe(
      '31 août et 1er et 2 septembre'
    );
  });
  it('trie par date', () => {
    expect(libelleDesJours([jour(9), jour(7)])).toBe('7 et 9 septembre');
  });
});

describe('messageHeuresEffacees', () => {
  it('confirme à l’écran les jours effacés', () => {
    expect(messageHeuresEffacees([jour(7), jour(8)])).toBe(
      'Heures effacées : 7 et 8 septembre.'
    );
  });
});

describe('groupesParMois', () => {
  it('un appel par (année, mois), jours triés sans doublon', () => {
    expect(groupesParMois([jour(2), jour(31, 8), jour(1), jour(2)])).toEqual([
      { annee: 2026, mois: 8, jours: [31] },
      { annee: 2026, mois: 9, jours: [1, 2] },
    ]);
  });
});

describe('natureDuConflit', () => {
  const avecType = (type_prevu?: string) => ({ ...jour(7), type_prevu });
  it('arrêt : tous les jours ont un type arret_*, même un samedi d’arrêt', () => {
    expect(natureDuConflit([avecType('arret_maladie'), avecType('arret_at')])).toBe('arret');
  });
  it('autre absence', () => {
    expect(natureDuConflit([avecType('conges_payes')])).toBe('absence');
  });
  it('mélange arrêt et absence', () => {
    expect(natureDuConflit([avecType('arret_maladie'), avecType('rtt')])).toBe('mixte');
  });
  it('type manquant : repli neutre (texte « absence »), jamais lu dans le message', () => {
    expect(natureDuConflit([jour(7)])).toBe('absence');
    expect(natureDuConflit([avecType('arret_maladie'), jour(8)])).toBe('absence');
    expect(natureDuConflit([])).toBe('absence');
  });
});

describe('prenomDe', () => {
  it('prend le premier mot', () => {
    expect(prenomDe('Octavie Martin')).toBe('Octavie');
  });
  it('rien si le nom est vide ou absent', () => {
    expect(prenomDe('  ')).toBeNull();
    expect(prenomDe(undefined)).toBeNull();
  });
  it('ne prend pas un identifiant pour un prénom', () => {
    expect(prenomDe('5f0c1c8e-2b2a-4c63-9d66-0c0f0f0f0f0f')).toBeNull();
  });
});

describe('textesDuChoix', () => {
  it('arrêt avec prénom', () => {
    expect(textesDuChoix('arret', 'Octavie')).toEqual({
      effacer: 'Octavie était en arrêt : effacer ces heures',
      modifier: 'Octavie a travaillé : modifier l’arrêt',
    });
  });
  it('absence avec prénom', () => {
    expect(textesDuChoix('absence', 'Octavie')).toEqual({
      effacer: 'Octavie n’a pas travaillé ces jours-là : effacer ces heures',
      modifier: 'Octavie a travaillé : modifier l’absence',
    });
  });
  it('mélange : le texte des absences', () => {
    expect(textesDuChoix('mixte', 'Octavie').modifier).toBe(
      'Octavie a travaillé : modifier l’absence'
    );
  });
  it('sans prénom : « Le salarié », sans genre', () => {
    expect(textesDuChoix('arret', null)).toEqual({
      effacer: 'Le salarié était en arrêt : effacer ces heures',
      modifier: 'Le salarié a travaillé : modifier l’arrêt',
    });
    expect(textesDuChoix('absence', null).effacer).toBe(
      'Le salarié n’a pas travaillé ces jours-là : effacer ces heures'
    );
  });
});

describe('lienModifierAbsence', () => {
  it('ouvre l’écran des absences filtré sur le salarié, avec la nature du conflit', () => {
    expect(lienModifierAbsence('emp 1/é', 'arret')).toBe(
      '/leaves?employee=emp%201%2F%C3%A9&nature=arret'
    );
    expect(lienModifierAbsence('e1', 'absence')).toBe('/leaves?employee=e1&nature=absence');
  });
});

describe('lireNatureDuLien', () => {
  it('lit la nature posée par le lien', () => {
    expect(lireNatureDuLien('arret')).toBe('arret');
    expect(lireNatureDuLien('absence')).toBe('absence');
    expect(lireNatureDuLien('mixte')).toBe('mixte');
  });
  it('rien pour une valeur absente ou inconnue', () => {
    expect(lireNatureDuLien(null)).toBeNull();
    expect(lireNatureDuLien('conges')).toBeNull();
  });
});

describe('lienCalendrierDuSalarie', () => {
  it('ouvre l’onglet Calendrier de la fiche du salarié', () => {
    expect(lienCalendrierDuSalarie('emp 1/é')).toBe('/employees/emp%201%2F%C3%A9?tab=calendrier');
  });
});

describe('bandeauAbsencesDuSalarie', () => {
  const base = { employeeId: 'e1', chargement: false, erreur: false };

  it('aucune demande : le dit franchement et renvoie au calendrier', () => {
    const b = bandeauAbsencesDuSalarie({ ...base, nature: 'arret', nombreDeDemandes: 0 });
    expect(b.texte).toBe(
      'Aucune demande d’absence enregistrée pour ce salarié : l’arrêt a été saisi au planning. Corrigez-le dans le calendrier du salarié.'
    );
    expect(b.lien).toEqual({
      href: '/employees/e1?tab=calendrier',
      libelle: 'Ouvrir le calendrier du salarié',
    });
  });

  it('aucune demande, absence : accord au féminin', () => {
    expect(
      bandeauAbsencesDuSalarie({ ...base, nature: 'absence', nombreDeDemandes: 0 }).texte
    ).toBe(
      'Aucune demande d’absence enregistrée pour ce salarié : l’absence a été saisie au planning. Corrigez-la dans le calendrier du salarié.'
    );
  });

  it('des demandes : ne promet pas que l’arrêt y est', () => {
    const b = bandeauAbsencesDuSalarie({ ...base, nature: 'arret', nombreDeDemandes: 2 });
    expect(b.texte).toBe(
      'Demandes d’absence de ce salarié. Si l’arrêt à corriger n’apparaît pas ici, il a été saisi au planning : corrigez-le dans le calendrier du salarié.'
    );
    expect(b.texte).not.toMatch(/retrouvez/);
    expect(b.lien.href).toBe('/employees/e1?tab=calendrier');
  });

  it('des demandes, absence : elle a été saisie', () => {
    expect(
      bandeauAbsencesDuSalarie({ ...base, nature: 'absence', nombreDeDemandes: 1 }).texte
    ).toBe(
      'Demandes d’absence de ce salarié. Si l’absence à corriger n’apparaît pas ici, elle a été saisie au planning : corrigez-la dans le calendrier du salarié.'
    );
  });

  it('nature inconnue ou mixte : « l’arrêt ou l’absence »', () => {
    for (const nature of [null, 'mixte'] as const) {
      expect(bandeauAbsencesDuSalarie({ ...base, nature, nombreDeDemandes: 0 }).texte).toBe(
        'Aucune demande d’absence enregistrée pour ce salarié : l’arrêt ou l’absence a été saisi au planning. Corrigez-le dans le calendrier du salarié.'
      );
    }
  });

  it('pendant le chargement : n’affirme pas qu’il n’y a rien', () => {
    const b = bandeauAbsencesDuSalarie({
      ...base,
      chargement: true,
      nature: 'arret',
      nombreDeDemandes: 0,
    });
    expect(b.texte).not.toMatch(/Aucune demande/);
    expect(b.texte).toBe('Recherche des demandes d’absence de ce salarié…');
  });

  it('demandes illisibles : n’affirme pas qu’il n’y a rien, dit quoi faire', () => {
    const b = bandeauAbsencesDuSalarie({
      ...base,
      erreur: true,
      nature: 'arret',
      nombreDeDemandes: 0,
    });
    expect(b.texte).toBe(
      'Les demandes d’absence de ce salarié n’ont pas pu être chargées : rechargez la page. Si l’arrêt a été saisi au planning, corrigez-le dans le calendrier du salarié.'
    );
  });
});

describe('clesAInvaliderApresEffacement', () => {
  it('invalide les vraies requêtes : heures de la semaine et préflight de la paie', async () => {
    const client = new QueryClient();
    const semaine = ['employee-week-payroll', 'e1', '2026-09-07', false, ''];
    const autreSalarie = ['employee-week-payroll', 'e2', '2026-09-07', false, ''];
    const preflight = queryKeys.payrollPreflight('co-1', 2026, 9);
    const autreSociete = queryKeys.payrollPreflight('co-2', 2026, 9);
    for (const key of [semaine, autreSalarie, preflight, autreSociete]) {
      client.setQueryData(key, 'donnée');
    }

    for (const queryKey of clesAInvaliderApresEffacement('co-1', 'e1')) {
      await client.invalidateQueries({ queryKey });
    }

    expect(client.getQueryState(semaine)?.isInvalidated).toBe(true);
    expect(client.getQueryState(preflight)?.isInvalidated).toBe(true);
    expect(client.getQueryState(autreSalarie)?.isInvalidated).toBe(false);
    expect(client.getQueryState(autreSociete)?.isInvalidated).toBe(false);
  });

  it('plus de clé morte `schedules`', () => {
    expect(clesAInvaliderApresEffacement('co-1', 'e1')).not.toContainEqual(
      queryKeys.schedules('co-1')
    );
  });
});

describe('aDesJoursAEffacer', () => {
  it('vrai seulement pour une liste non vide', () => {
    expect(aDesJoursAEffacer([jour(7)])).toBe(true);
    expect(aDesJoursAEffacer([])).toBe(false);
    expect(aDesJoursAEffacer(undefined)).toBe(false);
    expect(aDesJoursAEffacer(null)).toBe(false);
  });
});

describe('etatDialogueHeuresSurArret', () => {
  it('des jours lisibles : le choix', () => {
    expect(etatDialogueHeuresSurArret([jour(7)], null)).toEqual({
      kind: 'choix',
      jours: [jour(7)],
    });
  });
  it('aucun jour lisible : pas d’effacement proposé', () => {
    expect(etatDialogueHeuresSurArret([], null)).toEqual({ kind: 'sans_jours' });
    expect(etatDialogueHeuresSurArret(undefined, null)).toEqual({ kind: 'sans_jours' });
  });
  it('heures effacées puis génération en échec : ne dit plus « en conflit », propose de relancer', () => {
    const etat = etatDialogueHeuresSurArret([jour(7), jour(8)], {
      effaces: [jour(7), jour(8)],
      echecGeneration: 'La génération a été interrompue. Réessayez dans quelques instants.',
    });
    expect(etat).toEqual({
      kind: 'generation_en_echec',
      titre: 'Heures effacées, bulletin non régénéré',
      confirmation: 'Heures effacées : 7 et 8 septembre.',
      echec:
        'Le bulletin n’a pas été régénéré. La génération a été interrompue. Réessayez dans quelques instants.',
      actionRelancer: 'Relancer la génération',
    });
  });
  it('rien d’effacé : on reste sur le choix', () => {
    expect(
      etatDialogueHeuresSurArret([jour(7)], { effaces: [], echecGeneration: 'x' }).kind
    ).toBe('choix');
  });
});

const erreurHttp = (status: number, detail?: unknown) =>
  Object.assign(new AxiosError(`Request failed with status code ${status}`), {
    response: { status, data: detail === undefined ? {} : { detail } },
  });
const coupureReseau = () => new AxiosError('Network Error', 'ERR_NETWORK');

describe('raisonEchecEffacement', () => {
  it('coupure réseau : vérifier la connexion puis réessayer', () => {
    expect(raisonEchecEffacement(coupureReseau())).toBe(
      'La connexion au serveur a été coupée. Vérifiez votre connexion internet, puis réessayez.'
    );
  });
  it('403 : pas le droit de modifier ce calendrier', () => {
    expect(raisonEchecEffacement(erreurHttp(403, 'Forbidden'))).toBe(
      'Vous n’avez pas le droit de modifier le calendrier de ce salarié.'
    );
  });
  it('404 : salarié introuvable', () => {
    expect(raisonEchecEffacement(erreurHttp(404))).toBe(
      'Salarié introuvable. Rechargez la page, puis réessayez.'
    );
  });
  it('401 : session expirée', () => {
    expect(raisonEchecEffacement(erreurHttp(401))).toBe(
      'Votre session a expiré. Reconnectez-vous, puis réessayez.'
    );
  });
  it('4xx avec un motif lisible du backend : on le reprend', () => {
    const motif =
      'Le 9 septembre n’est ni un jour d’arrêt ni une absence au planning : ses heures ne sont pas effacées. Rien n’a été modifié.';
    expect(raisonEchecEffacement(erreurHttp(422, motif))).toBe(motif);
  });
  it('4xx sans motif lisible : renvoie au calendrier', () => {
    expect(raisonEchecEffacement(erreurHttp(422, [{ loc: ['body'] }]))).toBe(
      'La demande a été refusée. Effacez ces heures à la main dans le calendrier du salarié.'
    );
  });
  it('5xx : le serveur n’a pas répondu, réessayer, sinon à la main', () => {
    const attendu =
      'Le serveur n’a pas répondu. Réessayez dans un instant ; si le problème persiste, effacez les heures à la main dans le calendrier du salarié.';
    expect(raisonEchecEffacement(erreurHttp(500, 'Erreur interne: NoneType'))).toBe(attendu);
    expect(raisonEchecEffacement(erreurHttp(502))).toBe(attendu);
  });
  it('503 avec le motif du backend (arrêts illisibles) : le motif, puis la sortie à la main', () => {
    expect(
      raisonEchecEffacement(
        erreurHttp(
          503,
          'Les arrêts n’ont pas pu être lus : impossible de savoir quels jours effacer. Réessayez dans un instant. Rien n’a été modifié.'
        )
      )
    ).toBe(
      'Les arrêts n’ont pas pu être lus : impossible de savoir quels jours effacer. Réessayez dans un instant. Rien n’a été modifié. Si le problème persiste, effacez les heures à la main dans le calendrier du salarié.'
    );
  });
  it('jamais « Une erreur est survenue », jamais la génération', () => {
    for (const erreur of [
      coupureReseau(),
      erreurHttp(403),
      erreurHttp(404),
      erreurHttp(422),
      erreurHttp(500),
      new Error('x'),
      undefined,
    ]) {
      const raison = raisonEchecEffacement(erreur);
      expect(raison).not.toMatch(/Une erreur est survenue/);
      expect(raison).not.toMatch(/génér/i);
      expect(raison.length).toBeGreaterThan(20);
    }
  });
});

describe('lireRefusApresCorrection', () => {
  it('lit recalcul_refus du backend', () => {
    expect(
      lireRefusApresCorrection({
        code: 'heures_sur_jour_d_arret',
        message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
        jours: [{ annee: 2026, mois: 9, jour: 7, heures: 9 }],
      })
    ).toEqual({
      code: 'heures_sur_jour_d_arret',
      message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
      jours: [jour(7)],
    });
  });
  it('null si absent ou mal formé', () => {
    expect(lireRefusApresCorrection(null)).toBeNull();
    expect(lireRefusApresCorrection(undefined)).toBeNull();
    expect(lireRefusApresCorrection({ message: 'sans code' })).toBeNull();
  });
});

describe('choixApresCorrection', () => {
  const refus = {
    code: 'heures_sur_jour_d_arret',
    message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
    jours: [{ annee: 2026, mois: 9, jour: 7, heures: 9 }],
  };
  it('heures sur arrêt : on propose le choix, pas « Régénérer »', () => {
    const d = choixApresCorrection({ recalcul_erreur: refus.message, recalcul_refus: refus });
    expect(d.kind).toBe('choix');
    if (d.kind === 'choix') {
      expect(d.refus.jours).toEqual([jour(7)]);
    }
  });
  it('autre refus ou simple erreur : « Régénérer » reste la sortie', () => {
    expect(
      choixApresCorrection({
        recalcul_erreur: 'Calcul impossible',
        recalcul_refus: { code: 'calendrier_incomplet', message: 'm', jours: [] },
      }).kind
    ).toBe('regenerer');
    expect(choixApresCorrection({ recalcul_erreur: 'Calcul impossible' }).kind).toBe(
      'regenerer'
    );
  });
  it('rien à dire si le recalcul a réussi', () => {
    expect(choixApresCorrection({ recalcul_erreur: null, recalcul_refus: null }).kind).toBe(
      'aucun'
    );
    expect(choixApresCorrection({}).kind).toBe('aucun');
  });
  it('refus d’heures sans jours lisibles : on retombe sur Régénérer avec le message', () => {
    expect(
      choixApresCorrection({
        recalcul_erreur: 'm',
        recalcul_refus: { code: 'heures_sur_jour_d_arret', message: 'm', jours: [] },
      }).kind
    ).toBe('regenerer');
  });
});

describe('estJourEnConflit', () => {
  it('repère un jour de la liste du backend', () => {
    expect(estJourEnConflit(7, [7, 9])).toBe(true);
    expect(estJourEnConflit(8, [7, 9])).toBe(false);
    expect(estJourEnConflit(8, undefined)).toBe(false);
  });
  it('l’info-bulle est celle du brief', () => {
    expect(TITRE_INFO_BULLE_CONFLIT).toBe('Heures saisies pendant l’arrêt');
  });
});

describe('fusionnerJoursEnConflitImport', () => {
  const direct = [{ employee_id: 'e1', jours: [jour(7)] }];
  const lot = [{ employee_id: 'e2', jours: [jour(8), jour(9)] }];
  it('chemin direct : la réponse immédiate', () => {
    expect(fusionnerJoursEnConflitImport(direct, undefined)).toEqual(direct);
  });
  it('avec batch_id : la réponse est vide, le résumé du lot porte la liste', () => {
    expect(fusionnerJoursEnConflitImport([], lot)).toEqual(lot);
  });
  it('les deux sources : une ligne par salarié, jours réunis sans doublon', () => {
    expect(
      fusionnerJoursEnConflitImport(
        [{ employee_id: 'e1', jours: [jour(7)] }],
        [
          { employee_id: 'e1', jours: [jour(7), jour(10)] },
          { employee_id: 'e2', jours: [jour(8)] },
        ]
      )
    ).toEqual([
      { employee_id: 'e1', jours: [jour(7), jour(10)] },
      { employee_id: 'e2', jours: [jour(8)] },
    ]);
  });
  it('ignore les entrées mal formées', () => {
    expect(fusionnerJoursEnConflitImport(null, [{ jours: [jour(1)] }, 3])).toEqual([]);
  });
});

describe('effacerLesJours', () => {
  it('appelle le backend une fois par mois et rend tout ce qui a été effacé', async () => {
    const appels: unknown[] = [];
    const resultat = await effacerLesJours([jour(1), jour(31, 8), jour(2)], async (annee, mois, jours) => {
      appels.push([annee, mois, jours]);
    });
    expect(appels).toEqual([
      [2026, 8, [31]],
      [2026, 9, [1, 2]],
    ]);
    expect(resultat).toEqual({ ok: true, effaces: [jour(31, 8), jour(1), jour(2)] });
  });

  it('au premier refus : s’arrête, garde la raison et ce qui était déjà effacé', async () => {
    const erreur = new Error('refus');
    const resultat = await effacerLesJours([jour(31, 8), jour(1)], async (_a, mois) => {
      if (mois === 9) throw erreur;
    });
    expect(resultat).toEqual({
      ok: false,
      effaces: [jour(31, 8)],
      restants: [jour(1)],
      erreur,
    });
  });

  it('refus dès le premier mois : rien n’est effacé', async () => {
    const resultat = await effacerLesJours([jour(7)], async () => {
      throw new Error('x');
    });
    expect(resultat.ok).toBe(false);
    if (!resultat.ok) expect(resultat.effaces).toEqual([]);
  });
});

describe('messageEchecEffacement', () => {
  it('pluriel : « les 7 et 8 septembre »', () => {
    expect(messageEchecEffacement([jour(7), jour(8)], erreurHttp(500))).toContain(
      'seulement les 7 et 8 septembre.'
    );
  });
  it('refus du backend : son motif, et la génération n’a pas été relancée', () => {
    expect(
      messageEchecEffacement([], erreurHttp(422, 'Le 9 septembre n’est ni un jour d’arrêt.'))
    ).toBe(
      'Les heures n’ont pas été effacées. Le 9 septembre n’est ni un jour d’arrêt. La génération n’a pas été relancée.'
    );
  });
  it('coupure réseau : l’effacement n’est pas confirmé, sans reprendre les textes de la génération', () => {
    const message = messageEchecEffacement([], coupureReseau());
    expect(message).toBe(
      'L’effacement n’a pas pu être confirmé. La connexion au serveur a été coupée. Vérifiez votre connexion internet, puis réessayez. La génération n’a pas été relancée.'
    );
    expect(message).not.toMatch(/génération a été interrompue/);
  });
  it('dit ce qui a été effacé avant le refus', () => {
    expect(messageEchecEffacement([jour(31, 8)], erreurHttp(403))).toBe(
      'Heures effacées seulement le 31 août. Le reste n’a pas pu l’être. Vous n’avez pas le droit de modifier le calendrier de ce salarié. La génération n’a pas été relancée.'
    );
  });
  it('partiel puis coupure : le reste n’est pas confirmé', () => {
    expect(messageEchecEffacement([jour(31, 8)], coupureReseau())).toContain(
      'Heures effacées seulement le 31 août. Le reste n’a pas pu être confirmé.'
    );
  });
});

describe('prenomDuBulletin', () => {
  it('lit le prénom de l’en-tête du bulletin', () => {
    expect(prenomDuBulletin({ en_tete: { salarie: { prenom: ' Octavie ', nom: 'X' } } })).toBe('Octavie');
  });
  it('sinon le premier mot du nom complet', () => {
    expect(prenomDuBulletin({ en_tete: { salarie: { nom_complet: 'Octavie Martin' } } })).toBe('Octavie');
  });
  it('rien si le bulletin ne porte pas l’identité', () => {
    expect(prenomDuBulletin({})).toBeNull();
    expect(prenomDuBulletin(undefined)).toBeNull();
    expect(prenomDuBulletin({ en_tete: { salarie: 'x' } })).toBeNull();
  });
});
