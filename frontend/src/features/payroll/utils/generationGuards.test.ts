import { describe, expect, it } from 'vitest';
import {
  extractGenerationRefusal,
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
