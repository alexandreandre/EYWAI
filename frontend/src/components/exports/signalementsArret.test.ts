import { describe, expect, it } from 'vitest';
import {
  echeance,
  libelleFait,
  libelleSignalement,
  statutSignalementDeLArret,
} from './signalementsArret';

const ligne = {
  employee_id: 'e1', salarie: 'A. T.', nature: '04', motif: '01', debut: '2026-10-05',
  fin_prevue: '2026-10-09', subrogation: false, connu_le: '2026-10-06',
  a_deposer_avant: '2026-10-11', date_reprise: null, en_retard: false,
};

describe('signalements d’arrêt', () => {
  it('dit l’arrêt en mots simples', () => {
    expect(libelleSignalement(ligne)).toBe('Arrêt maladie du 05/10/2026 au 09/10/2026');
    expect(libelleSignalement({ ...ligne, nature: '05', date_reprise: '2026-10-08' })).toBe(
      'Reprise anticipée le 08/10/2026 (arrêt maladie du 05/10/2026)',
    );
  });
  it('dit la date limite, en urgence une fois dépassée', () => {
    expect(echeance(ligne)).toEqual({ texte: 'À déposer avant le 11/10/2026', urgent: false });
    expect(echeance({ ...ligne, en_retard: true })).toEqual({
      texte: 'En retard : à déposer avant le 11/10/2026',
      urgent: true,
    });
  });
  it('dit un signalement déjà généré', () => {
    const fait = { employee_id: 'e1', salarie: 'A. T.', nature: '05', motif: '06', debut: '2026-10-05',
      fin_prevue: '2026-10-16', essai: true, genere_le: '2026-10-12' };
    expect(libelleFait(fait)).toBe('Essai · reprise, accident du travail du 05/10/2026 · généré le 12/10/2026');
    expect(libelleFait({ ...fait, nature: '04', essai: false })).toBe(
      'Réel · arrêt, accident du travail du 05/10/2026 · généré le 12/10/2026',
    );
  });
  it('dit une fin de contrat', () => {
    expect(libelleSignalement({ ...ligne, nature: '07', motif: '', debut: '2026-12-18', fin_prevue: '2026-12-18' }))
      .toBe('Fin de contrat le 18/12/2026');
    expect(libelleFait({ employee_id: 'e1', salarie: 'A. T.', nature: '07', motif: '', debut: '2026-12-18',
      fin_prevue: '2026-12-18', essai: false, genere_le: '2026-12-21' }))
      .toBe('Réel · fin de contrat du 18/12/2026 · généré le 21/12/2026');
  });
});

describe('le signalement DSN d’un arrêt, sur l’écran des absences', () => {
  const arret = { employee_id: 'e1', selected_days: ['2026-10-06', '2026-10-05'] };
  const fait = {
    employee_id: 'e1', salarie: 'A. T.', nature: '04', motif: '01', debut: '2026-10-05',
    fin_prevue: '2026-10-09', essai: false, genere_le: '2026-10-07',
  };

  it('à déposer : dit la date limite', () => {
    expect(statutSignalementDeLArret(arret, { a_faire: [ligne], faits: [] })).toEqual({
      texte: 'Signalement DSN à déposer avant le 11/10/2026',
      urgent: false,
      fait: false,
    });
  });

  it('en retard : le dit', () => {
    const statut = statutSignalementDeLArret(arret, {
      a_faire: [{ ...ligne, en_retard: true }],
      faits: [],
    });
    expect(statut?.texte).toBe('Signalement DSN en retard : à déposer avant le 11/10/2026');
    expect(statut?.urgent).toBe(true);
  });

  it('fichier généré : Martine ne sait pas s’il est déposé et ne le prétend pas', () => {
    expect(statutSignalementDeLArret(arret, { a_faire: [], faits: [fait] })).toEqual({
      texte: 'Signalement DSN : fichier généré le 07/10/2026',
      urgent: false,
      fait: true,
    });
  });

  it('un fichier d’essai ne vaut pas signalement', () => {
    expect(
      statutSignalementDeLArret(arret, { a_faire: [], faits: [{ ...fait, essai: true }] }),
    ).toBeNull();
  });

  it('ni l’arrêt d’un collègue, ni une fin de contrat, ni une autre période', () => {
    const autres = {
      a_faire: [
        { ...ligne, employee_id: 'e2' },
        { ...ligne, nature: '07' },
        { ...ligne, debut: '2026-11-02', fin_prevue: '2026-11-06' },
      ],
      faits: [{ ...fait, employee_id: 'e2' }],
    };
    expect(statutSignalementDeLArret(arret, autres)).toBeNull();
  });

  it('sans jour ni signalements chargés : rien', () => {
    expect(statutSignalementDeLArret({ employee_id: 'e1', selected_days: [] }, { a_faire: [ligne], faits: [] })).toBeNull();
    expect(statutSignalementDeLArret(arret, undefined)).toBeNull();
  });
});
