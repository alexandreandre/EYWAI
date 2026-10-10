import { describe, expect, it } from 'vitest';

import {
  MESSAGE_A_RECALCULER,
  MESSAGE_COMPARAISON_INDISPONIBLE,
  estPerime,
  jobsDesBulletinsPerimes,
  jobsDesLignesPerimes,
  libelleBoutonRecalculerTout,
  messageValidesChanges,
  nomsDesValidesChanges,
  libelleToastRecalcul,
  infobulleARecalculer,
  messageARecalculer,
  montantsDepuisLigne,
  montantsDepuisReponse,
  toastsDeFinDeRecalcul,
} from './bulletinARecalculer';

describe('estPerime', () => {
  it('seul true est à recalculer', () => {
    expect(estPerime({ a_recalculer: true })).toBe(true);
    expect(estPerime({ a_recalculer: false })).toBe(false);
    expect(estPerime({ a_recalculer: null })).toBe(false);
    expect(estPerime({})).toBe(false);
    expect(estPerime(undefined)).toBe(false);
  });

  it('un bulletin repris ne se marque pas, même si le serveur dit true', () => {
    expect(estPerime({ a_recalculer: true, origine: 'importe' })).toBe(false);
  });
});

describe('messageARecalculer', () => {
  const MUTUELLE = 'La mutuelle a changé depuis le calcul : recalculez avant de valider.';

  it('dit ce que le serveur a vu changer', () => {
    expect(messageARecalculer({ a_recalculer: true, raison_a_recalculer: MUTUELLE })).toBe(MUTUELLE);
  });

  it('le dit aussi quand le mois d’avant est à régénérer', () => {
    expect(
      messageARecalculer({
        a_recalculer: true,
        a_regenerer: 'Le bulletin du mois précédent a changé…',
        raison_a_recalculer: MUTUELLE,
      })
    ).toBe(MUTUELLE);
  });

  it('le mois d’avant seul se dit par « À régénérer »', () => {
    expect(
      messageARecalculer({
        a_recalculer: true,
        a_regenerer: 'Le bulletin du mois précédent a changé…',
        raison_a_recalculer: null,
      })
    ).toBeNull();
  });

  it('sans raison du serveur, un bulletin périmé garde le message général', () => {
    expect(messageARecalculer({ a_recalculer: true })).toBe(MESSAGE_A_RECALCULER);
    expect(messageARecalculer({ a_recalculer: false })).toBeNull();
    expect(messageARecalculer(undefined)).toBeNull();
  });

  it('un bulletin repris n’a jamais d’alerte', () => {
    expect(
      messageARecalculer({ a_recalculer: true, origine: 'importe', raison_a_recalculer: MUTUELLE })
    ).toBeNull();
  });

  it('le message général ne prétend pas savoir que c’est le calendrier', () => {
    expect(MESSAGE_A_RECALCULER).not.toMatch(/^Le calendrier ou les absences/);
    expect(MESSAGE_A_RECALCULER).toMatch(/fiche/);
  });
});

describe('jobsDesBulletinsPerimes', () => {
  const salaries = [
    { id: 'e1', first_name: 'Jeanne', last_name: 'Essai' },
    { id: 'e2', first_name: 'Paul', last_name: 'Essai' },
    { id: 'e3', first_name: 'Claire', last_name: 'Essai' },
  ];

  it('ne relance que les bulletins périmés du mois, pas les inconnus ni les repris', () => {
    const jobs = jobsDesBulletinsPerimes(
      salaries,
      {
        e1: [
          {
            year: 2026,
            month: 5,
            a_recalculer: true,
            origine: 'calcule',
            heures_sup: 2,
            salaire_brut: 1800,
            net_a_payer: 1400,
          },
        ],
        e2: [{ year: 2026, month: 5, a_recalculer: null, origine: 'calcule' }],
        e3: [{ year: 2026, month: 5, a_recalculer: true, origine: 'importe' }],
      },
      2026,
      5
    );
    expect(jobs).toEqual([
      {
        employeeId: 'e1',
        employeeName: 'Jeanne Essai',
        year: 2026,
        month: 5,
        montantsAvant: { heures_sup: 2, salaire_brut: 1800, net_a_payer: 1400 },
      },
    ]);
  });

  it('un salarié, tous ses mois périmés de l’année', () => {
    const jobs = jobsDesLignesPerimes(salaries[0], [
      { year: 2026, month: 4, a_recalculer: true, origine: 'calcule' },
      { year: 2026, month: 5, a_recalculer: false, origine: 'calcule' },
      { year: 2025, month: 12, a_recalculer: true, origine: 'calcule' },
    ]);
    expect(jobs.map((j) => `${j.year}-${j.month}`)).toEqual(['2026-4', '2025-12']);
  });

  it('ignore un bulletin d’un autre mois', () => {
    const jobs = jobsDesBulletinsPerimes(
      salaries.slice(0, 1),
      {
        e1: [{ year: 2026, month: 4, a_recalculer: true, origine: 'calcule' }],
      },
      2026,
      5
    );
    expect(jobs).toEqual([]);
  });
});

describe('libelleToastRecalcul', () => {
  const avant = { heures_sup: 2, salaire_brut: 1800, net_a_payer: 1400 };
  const apres = { heures_sup: 4, salaire_brut: 1900, net_a_payer: 1480 };

  it('résume heures sup, brut et net avant → après', () => {
    const toast = libelleToastRecalcul(avant, apres);
    expect(toast.title).toBe('Bulletin recalculé');
    expect(toast.description).toContain('Heures sup.');
    expect(toast.description).toContain('2');
    expect(toast.description).toContain('4');
    expect(toast.description).toContain('1 800');
    expect(toast.description).toContain('1 900');
    expect(toast.description).toContain('1 400');
    expect(toast.description).toContain('1 480');
  });

  it('ne invente pas un chiffre si un montant manque', () => {
    expect(libelleToastRecalcul(avant, null).description).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
    expect(
      libelleToastRecalcul(avant, { ...apres, net_a_payer: null }).description
    ).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
    expect(libelleToastRecalcul(null, apres).description).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
  });
});

describe('montants depuis la ligne ou la réponse', () => {
  it('lit les trois champs, ou null', () => {
    expect(
      montantsDepuisLigne({ heures_sup: 1, salaire_brut: 2, net_a_payer: 3 })
    ).toEqual({ heures_sup: 1, salaire_brut: 2, net_a_payer: 3 });
    expect(montantsDepuisReponse({})).toEqual({
      heures_sup: null,
      salaire_brut: null,
      net_a_payer: null,
    });
  });
});

describe('libellés écran', () => {
  it('le bouton dit quoi relancer, le message de validation dit de recalculer', () => {
    expect(libelleBoutonRecalculerTout(3)).toBe('Recalculer tout ce qui a changé (3)');
    expect(MESSAGE_A_RECALCULER).toMatch(/recalculez avant de valider/i);
  });
});

describe('toastsDeFinDeRecalcul', () => {
  const sansInsecables = (texte: string) => texte.replace(/\s/g, ' ');
  const item = (employeeName: string, net: [number, number]) => ({
    employeeName,
    avant: { heures_sup: 0, salaire_brut: 2000, net_a_payer: net[0] },
    apres: { heures_sup: 0, salaire_brut: 2000, net_a_payer: net[1] },
  });

  it('rien à dire sans recalcul', () => {
    expect(toastsDeFinDeRecalcul([])).toEqual([]);
  });

  it('un recalcul unitaire : le détail, avec le nom du salarié dans le titre', () => {
    const toasts = toastsDeFinDeRecalcul([item('Camille Test', [1400, 1480])]);
    expect(toasts).toHaveLength(1);
    expect(toasts[0].title).toBe('Bulletin de Camille Test recalculé');
    expect(sansInsecables(toasts[0].description)).toContain('1 480');
  });

  it('un lot : un seul message, les noms et le net avant → après', () => {
    const toasts = toastsDeFinDeRecalcul([
      item('Camille Test', [1400, 1480]),
      item('Dominique Essai', [1500, 1500]),
      item('Claude Exemple', [1600, 1550]),
    ]);
    expect(toasts).toHaveLength(1);
    expect(toasts[0].title).toBe('3 bulletins recalculés');
    for (const nom of ['Camille Test', 'Dominique Essai', 'Claude Exemple']) {
      expect(toasts[0].description).toContain(nom);
    }
    expect(sansInsecables(toasts[0].description)).toContain('1 400');
    expect(sansInsecables(toasts[0].description)).toContain('1 480');
    expect(toasts[0].description).toContain('→');
  });

  it('un lot dont la comparaison manque le dit pour ce salarié', () => {
    const toasts = toastsDeFinDeRecalcul([
      item('Camille Test', [1400, 1480]),
      { employeeName: 'Alix Modèle', avant: null, apres: null },
    ]);
    expect(toasts[0].description).toContain('Alix Modèle : recalculé, comparaison indisponible');
  });
});

describe('libelleToastRecalcul : élision devant le nom', () => {
  it("dit « Bulletin d'Élodie Test recalculé »", () => {
    expect(libelleToastRecalcul(null, null, 'Élodie Test').title).toBe("Bulletin d'Élodie Test recalculé");
  });
});

describe('messageARecalculer : bulletin déjà validé', () => {
  const GESTE = ' : régénérez le bulletin (l’ancienne version est archivée), puis validez-le de nouveau.';

  it('dit le vrai geste au lieu de « recalculez avant de valider »', () => {
    expect(
      messageARecalculer({
        status: 'valide',
        a_recalculer: true,
        raison_a_recalculer: 'Les variables du mois ont changé depuis le calcul : recalculez avant de valider.',
      })
    ).toBe('Les variables du mois ont changé depuis la validation' + GESTE);
  });

  it('sans phrase du serveur, le message général suit le même geste', () => {
    expect(messageARecalculer({ status: 'valide', a_recalculer: true })).toBe(
      'Une donnée du bulletin a changé depuis la validation' + GESTE
    );
  });

  it('un bulletin en brouillon garde « recalculez avant de valider »', () => {
    expect(messageARecalculer({ status: 'brouillon', a_recalculer: true })).toBe(MESSAGE_A_RECALCULER);
  });
});

describe('infobulleARecalculer : la pastille dit la même chose que le bandeau', () => {
  const raison = 'Les variables du mois ont changé depuis le calcul : recalculez avant de valider.';

  it('un bulletin validé : régénérer puis valider de nouveau, pas « recalculez avant de valider »', () => {
    const texte = infobulleARecalculer({ status: 'valide', a_recalculer: true, raison_a_recalculer: raison });
    expect(texte).toBe(messageARecalculer({ status: 'valide', a_recalculer: true, raison_a_recalculer: raison }));
    expect(texte).toContain('régénérez le bulletin');
    expect(texte).not.toContain('recalculez avant de valider');
  });

  it('un brouillon garde la phrase du serveur', () => {
    expect(infobulleARecalculer({ status: 'brouillon', a_recalculer: true, raison_a_recalculer: raison })).toBe(raison);
  });
});

describe('bulletins validés « à recalculer » : jamais recalculés en groupe', () => {
  const salaries = [
    { id: 'e1', first_name: 'Jeanne', last_name: 'Essai' },
    { id: 'e2', first_name: 'Paul', last_name: 'Essai' },
  ];
  const lignes = {
    e1: [{ year: 2026, month: 5, a_recalculer: true, origine: 'calcule', status: 'valide' }],
    e2: [{ year: 2026, month: 5, a_recalculer: true, origine: 'calcule', status: 'brouillon' }],
  };

  it('la liste du mois exclut les validés', () => {
    expect(jobsDesBulletinsPerimes(salaries, lignes, 2026, 5).map((j) => j.employeeId)).toEqual(['e2']);
  });

  it('la liste d’un salarié exclut ses mois validés', () => {
    expect(jobsDesLignesPerimes(salaries[0], lignes.e1)).toEqual([]);
  });

  it('nomme les validés qui ont changé', () => {
    expect(nomsDesValidesChanges(salaries, lignes, 2026, 5)).toEqual(['Jeanne Essai']);
  });

  it('le message est accordé et sans bouton', () => {
    expect(messageValidesChanges(['Jeanne Essai'])).toBe(
      '1 bulletin validé a changé depuis sa validation : ouvrez-le pour décider (Jeanne Essai).'
    );
    expect(messageValidesChanges(['A B', 'C D'])).toBe(
      '2 bulletins validés ont changé depuis leur validation : ouvrez-les un par un pour décider (A B, C D).'
    );
    expect(messageValidesChanges([])).toBeNull();
  });
});
