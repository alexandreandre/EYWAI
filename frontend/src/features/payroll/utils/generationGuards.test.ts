import { describe, expect, it } from 'vitest';
import {
  extractGenerationRefusal,
  estForcable,
  forcageDuRefus,
  refusForcablesEnGroupe,
  REFUSAL_DIALOG_LABELS,
  splitGenerationWarnings,
} from './generationGuards';

function httpError(status: number, detail: unknown) {
  return { response: { status, data: { detail } } };
}

describe('extractGenerationRefusal', () => {
  it('reconnaît le refus 422 calendrier_incomplet', () => {
    const error = httpError(422, {
      code: 'calendrier_incomplet',
      message: 'Le calendrier de mars 2026 comporte 4 jours à saisir.',
    });
    expect(extractGenerationRefusal(error)).toEqual({
      code: 'calendrier_incomplet',
      message: 'Le calendrier de mars 2026 comporte 4 jours à saisir.',
    });
  });

  it('reconnaît le refus 409 bulletin_valide', () => {
    const error = httpError(409, {
      code: 'bulletin_valide',
      message: 'Un bulletin validé existe déjà pour mars 2026.',
    });
    expect(extractGenerationRefusal(error)).toEqual({
      code: 'bulletin_valide',
      message: 'Un bulletin validé existe déjà pour mars 2026.',
    });
  });

  it('fournit un message de repli si le message manque ou est technique', () => {
    const sansMessage = httpError(422, { code: 'calendrier_incomplet' });
    expect(extractGenerationRefusal(sansMessage)?.message).toContain('incomplet');

    const technique = httpError(409, {
      code: 'bulletin_valide',
      message: 'Traceback (most recent call last): ...',
    });
    expect(extractGenerationRefusal(technique)?.message).toContain('validé');
  });

  it('ignore un backend ancien (detail texte) → gestion générique', () => {
    expect(
      extractGenerationRefusal(httpError(422, 'Calendrier incomplet'))
    ).toBeNull();
    expect(extractGenerationRefusal(httpError(409, 'Bulletin validé'))).toBeNull();
  });

  it('ignore les erreurs de validation FastAPI (detail tableau)', () => {
    expect(
      extractGenerationRefusal(httpError(422, [{ msg: 'field required' }]))
    ).toBeNull();
  });

  it('exige la paire statut + code attendue', () => {
    expect(
      extractGenerationRefusal(httpError(409, { code: 'calendrier_incomplet' }))
    ).toBeNull();
    expect(
      extractGenerationRefusal(httpError(422, { code: 'bulletin_valide' }))
    ).toBeNull();
    expect(
      extractGenerationRefusal(httpError(400, { code: 'bulletin_valide' }))
    ).toBeNull();
  });

  it('ignore les erreurs sans réponse HTTP', () => {
    expect(extractGenerationRefusal(new Error('Network Error'))).toBeNull();
    expect(extractGenerationRefusal(undefined)).toBeNull();
    expect(extractGenerationRefusal({ response: undefined })).toBeNull();
  });
});

describe('splitGenerationWarnings', () => {
  it('sépare alertes moteur (chaînes) et gardes forcées (objets)', () => {
    const { messages, guardWarnings } = splitGenerationWarnings([
      'Salaire sous le SMIC conventionnel',
      { code: 'calendrier_incomplet_force', message: 'Généré malgré 4 jours à saisir.' },
      { code: 'bulletin_valide_regenere', message: 'Ancienne version archivée.' },
    ]);
    expect(messages).toEqual([
      'Salaire sous le SMIC conventionnel',
      'Généré malgré 4 jours à saisir.',
      'Ancienne version archivée.',
    ]);
    expect(guardWarnings).toEqual([
      { code: 'calendrier_incomplet_force', message: 'Généré malgré 4 jours à saisir.' },
      { code: 'bulletin_valide_regenere', message: 'Ancienne version archivée.' },
    ]);
  });

  it('ignore les entrées vides ou illisibles sans casser', () => {
    const { messages, guardWarnings } = splitGenerationWarnings([
      '',
      null,
      42,
      { code: 'x' },
      { message: 'Sans code : simple alerte.' },
    ]);
    expect(messages).toEqual(['Sans code : simple alerte.']);
    expect(guardWarnings).toEqual([]);
  });

  it('tolère un champ warnings absent ou non-tableau', () => {
    expect(splitGenerationWarnings(undefined)).toEqual({
      messages: [],
      infos: [],
      guardWarnings: [],
    });
    expect(splitGenerationWarnings('oops')).toEqual({
      messages: [],
      infos: [],
      guardWarnings: [],
    });
  });
});

describe('extractGenerationRefusal — détails de la période à saisir', () => {
  it('porte les détails quand le backend les donne', () => {
    const error = httpError(422, {
      code: 'calendrier_incomplet',
      message:
        '07/2026 — 7 jour(s) à saisir dans la fenêtre des variables (22/06 → 26/07) : 22/06–26/06, 29/06–30/06.',
      fenetre: { debut: '2026-06-22', fin: '2026-07-26', semaines: [26, 27, 28, 29, 30], origine: 'regle' },
      jours_manquants: ['2026-06-22', '2026-06-23'],
      jours_informatifs: ['2026-07-27'],
    });
    expect(extractGenerationRefusal(error)?.details).toEqual({
      fenetre: { debut: '2026-06-22', fin: '2026-07-26', semaines: [26, 27, 28, 29, 30], origine: 'regle' },
      joursManquants: ['2026-06-22', '2026-06-23'],
      joursInformatifs: ['2026-07-27'],
    });
  });

  it('reste compatible avec un 422 sans détails (backend ancien)', () => {
    const error = httpError(422, { code: 'calendrier_incomplet', message: 'incomplet' });
    expect(extractGenerationRefusal(error)?.details).toBeUndefined();
  });
});

describe('splitGenerationWarnings — points à arbitrer', () => {
  it('sépare un point d’information des alertes', () => {
    const { messages, infos, guardWarnings } = splitGenerationWarnings([
      'Vraie alerte.',
      { code: 'transport_plafond_annuel_depasse', severity: 'info', message: 'Transport : 700 €.' },
    ]);
    expect(messages).toEqual(['Vraie alerte.']);
    expect(infos).toEqual(['Transport : 700 €.']);
    expect(guardWarnings).toEqual([]);
  });

  it('un objet sans sévérité reste une alerte, comme avant', () => {
    const { messages, infos, guardWarnings } = splitGenerationWarnings([
      { code: 'bulletin_valide_regenere', message: 'Régénéré.' },
    ]);
    expect(messages).toEqual(['Régénéré.']);
    expect(infos).toEqual([]);
    expect(guardWarnings).toEqual([{ code: 'bulletin_valide_regenere', message: 'Régénéré.' }]);
  });
});

describe('refus heures_sur_jour_d_arret et arrets_illisibles', () => {
  const jours = [{ annee: 2026, mois: 9, jour: 7, heures: 9 }];

  it('reconnaît le 422 heures_sur_jour_d_arret avec ses jours', () => {
    const error = httpError(422, {
      code: 'heures_sur_jour_d_arret',
      message: 'Octavie est en arrêt, mais des heures sont saisies le 7 septembre.',
      jours,
    });
    expect(extractGenerationRefusal(error)).toEqual({
      code: 'heures_sur_jour_d_arret',
      message: 'Octavie est en arrêt, mais des heures sont saisies le 7 septembre.',
      jours,
    });
  });

  it('reconnaît le 503 arrets_illisibles avec son message', () => {
    const error = httpError(503, {
      code: 'arrets_illisibles',
      message: 'Les arrêts de Octavie n’ont pas pu être lus. Réessayez dans un instant.',
    });
    expect(extractGenerationRefusal(error)).toEqual({
      code: 'arrets_illisibles',
      message: 'Les arrêts de Octavie n’ont pas pu être lus. Réessayez dans un instant.',
    });
  });

  it('un 503 sans code connu reste une erreur générique', () => {
    expect(extractGenerationRefusal(httpError(503, 'Service indisponible'))).toBeNull();
    expect(extractGenerationRefusal(httpError(503, { code: 'autre', message: 'm' }))).toBeNull();
  });

  it('le code doit aller avec son statut', () => {
    expect(
      extractGenerationRefusal(httpError(409, { code: 'heures_sur_jour_d_arret', message: 'm' }))
    ).toBeNull();
    expect(
      extractGenerationRefusal(httpError(422, { code: 'arrets_illisibles', message: 'm' }))
    ).toBeNull();
  });

  it('message de repli utile si le message manque', () => {
    expect(
      extractGenerationRefusal(httpError(422, { code: 'heures_sur_jour_d_arret', jours }))?.message
    ).toContain('heures');
    expect(extractGenerationRefusal(httpError(503, { code: 'arrets_illisibles' }))?.message).toContain(
      'Réessayez'
    );
  });

  it('aucun des deux ne se force', () => {
    expect(estForcable('calendrier_incomplet')).toBe(true);
    expect(estForcable('bulletin_valide')).toBe(true);
    expect(estForcable('heures_sur_jour_d_arret')).toBe(false);
    expect(estForcable('arrets_illisibles')).toBe(false);
  });
});

describe('refusForcablesEnGroupe : jamais de régénération en masse de bulletins validés', () => {
  const refus = (code: 'calendrier_incomplet' | 'bulletin_valide' | 'arrets_illisibles') => ({
    code,
    job: { employeeId: code },
  });

  it('un seul refus : il reste forçable, bulletin par bulletin', () => {
    expect(refusForcablesEnGroupe([refus('bulletin_valide')])).toHaveLength(1);
  });

  it('plusieurs refus : les bulletins validés ne se forcent pas', () => {
    const forcables = refusForcablesEnGroupe([
      refus('bulletin_valide'),
      refus('bulletin_valide'),
      refus('calendrier_incomplet'),
      refus('arrets_illisibles'),
    ]);
    expect(forcables.map((r) => r.code)).toEqual(['calendrier_incomplet']);
  });
});

describe('refus reprise_non_posee : générer quand même, en partant de cumuls à zéro', () => {
  const message =
    'La paie de cette société se faisait avant Martine (DSN importées de 01/2026 à 06/2026)… ' +
    'Sinon, le bulletin peut être généré quand même en partant de cumuls à zéro : il portera une alerte.';

  it('reconnaît le 422 reprise_non_posee avec son message', () => {
    expect(extractGenerationRefusal(httpError(422, { code: 'reprise_non_posee', message }))).toEqual({
      code: 'reprise_non_posee',
      message,
    });
  });

  it('se force, seul ou en groupe, par son propre drapeau', () => {
    expect(estForcable('reprise_non_posee')).toBe(true);
    const forcables = refusForcablesEnGroupe([
      { code: 'reprise_non_posee' as const, job: { employeeId: 'a' } },
      { code: 'calendrier_incomplet' as const, job: { employeeId: 'b' } },
    ]);
    expect(forcables.map((r) => r.code)).toEqual(['reprise_non_posee', 'calendrier_incomplet']);
    expect(forcageDuRefus('reprise_non_posee')).toEqual({ partir_de_cumuls_a_zero: true });
  });

  it('le bouton dit ce qu’il fait', () => {
    expect(REFUSAL_DIALOG_LABELS.reprise_non_posee.actionLabel).toBe(
      'Générer quand même, en partant de cumuls à zéro'
    );
  });

  it('chaque refus forçable a son drapeau, les autres aucun', () => {
    expect(forcageDuRefus('calendrier_incomplet')).toEqual({ force_calendrier_incomplet: true });
    expect(forcageDuRefus('bulletin_valide')).toEqual({ regenerer_bulletin_valide: true });
    expect(forcageDuRefus('heures_sur_jour_d_arret')).toEqual({});
    expect(forcageDuRefus('arrets_illisibles')).toEqual({});
  });
});
