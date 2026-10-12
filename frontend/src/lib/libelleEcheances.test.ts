import { describe, expect, it } from 'vitest';

import { TITRE_ECHEANCES, lignesTitresExpires, messageEcheances } from './libelleEcheances';

describe('décompte des échéances', () => {
  it('dit tout ce qu’il compte, titres de séjour compris, avec leur fenêtre', () => {
    expect(TITRE_ECHEANCES).toContain('CDD');
    expect(TITRE_ECHEANCES).toContain('stage');
    expect(TITRE_ECHEANCES).toContain('périodes d’essai');
    expect(TITRE_ECHEANCES).toContain('titres de séjour');
    expect(TITRE_ECHEANCES).toContain('30 jours');
  });

  it('accorde le message au nombre', () => {
    expect(messageEcheances(0)).toBe('Aucune échéance à venir.');
    expect(messageEcheances(1)).toBe('1 salarié à traiter.');
    expect(messageEcheances(3)).toBe('3 salariés à traiter.');
  });
});

describe('titres expirés dans « Échéances » ([D6-4], 12/10/2026)', () => {
  it('le titre du bandeau dit que les titres expirés y sont', () => {
    expect(TITRE_ECHEANCES).toContain('titres de séjour (30 jours, ou déjà expirés)');
  });

  it('les titres expirés se listent en tête, « Expiré » devant', () => {
    expect(
      lignesTitresExpires([
        { employee_id: 'e2', first_name: 'Paul', last_name: 'Essai', reminder_type: 'cdd_end', deadline: '2026-10-20', days_remaining: 8, label: 'Fin de CDD le 20/10/2026' },
        { employee_id: 'e1', first_name: 'Jeanne', last_name: 'Essai', reminder_type: 'residence_permit', deadline: '2026-04-20', days_remaining: -175, label: 'Titre de séjour expiré le 20/04/2026' },
      ]),
    ).toEqual([{ employee_id: 'e1', texte: 'Expiré : Jeanne Essai — titre de séjour expiré le 20/04/2026' }]);
  });
});
