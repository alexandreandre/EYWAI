import { describe, expect, it } from 'vitest';
import { echeance, libelleFait, libelleSignalement } from './signalementsArret';

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
});
