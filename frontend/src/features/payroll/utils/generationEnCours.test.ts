import { describe, expect, it } from 'vitest';

import {
  CLE_INTERRUPTION,
  libelleBandeauGeneration,
  lienQuitteLaPage,
  lireInterruption,
  noterInterruption,
  oublierInterruption,
  phraseInterruption,
  questionQuitterGeneration,
  recapitulatifEchecs,
} from './generationEnCours';

describe('bandeau et question pendant la génération — revue du 05/10', () => {
  it('le bandeau dit où en est la génération et de ne pas quitter', () => {
    expect(libelleBandeauGeneration(3, 25)).toBe(
      'Génération en cours (3/25) : ne quittez pas cette page.'
    );
  });

  it('la question avant de quitter dit ce qui sera perdu', () => {
    expect(questionQuitterGeneration(3, 25)).toBe(
      'Une génération est en cours (3/25). Quitter la page l’arrête : les 22 bulletins restants ne seront pas générés. Quitter quand même ?'
    );
  });
});

describe('lienQuitteLaPage — un clic sur un lien de l’application quitte-t-il la page ?', () => {
  const ici = { origin: 'https://paie.exemple.fr', pathname: '/payroll' };
  const lien = (href: string | null, extra: Partial<{ target: string | null; download: boolean }> = {}) => ({
    href,
    target: null,
    download: false,
    ...extra,
  });

  it('un lien vers une autre page de l’application : oui', () => {
    expect(lienQuitteLaPage(lien('/payslips/ps-1/edit'), ici)).toBe(true);
    expect(lienQuitteLaPage(lien('https://paie.exemple.fr/exports'), ici)).toBe(true);
  });

  it('la même page avec d’autres paramètres : non', () => {
    expect(lienQuitteLaPage(lien('/payroll?view=month&month=2026-09'), ici)).toBe(false);
  });

  it('un nouvel onglet, un téléchargement, une ancre, un lien vide : non', () => {
    expect(lienQuitteLaPage(lien('/exports', { target: '_blank' }), ici)).toBe(false);
    expect(lienQuitteLaPage(lien('/bulletin.pdf', { download: true }), ici)).toBe(false);
    expect(lienQuitteLaPage(lien('#haut'), ici)).toBe(false);
    expect(lienQuitteLaPage(lien(null), ici)).toBe(false);
  });

  it('un site externe : non, le navigateur pose déjà sa question', () => {
    expect(lienQuitteLaPage(lien('https://www.net-entreprises.fr'), ici)).toBe(false);
  });
});

describe('recapitulatifEchecs — les échecs restent lisibles une fois le suivi fermé', () => {
  it('ne garde que les échecs, avec le salarié, le mois et la raison', () => {
    expect(
      recapitulatifEchecs([
        { id: 'a', employeeId: 'e-1', employeeName: 'Jeanne Essai', year: 2026, month: 9, status: 'success' },
        {
          id: 'b',
          employeeId: 'e-2',
          employeeName: 'Paul Essai',
          year: 2026,
          month: 9,
          status: 'error',
          error: 'Calendrier incomplet.',
        },
        { id: 'c', employeeId: 'e-3', employeeName: 'Lou Essai', year: 2026, month: 9, status: 'warning' },
      ])
    ).toEqual([
      { cle: 'b', employeeId: 'e-2', nom: 'Paul Essai', mois: 'Septembre 2026', raison: 'Calendrier incomplet.' },
    ]);
  });

  it('un échec sans message en a un quand même', () => {
    const [echec] = recapitulatifEchecs([
      { id: 'b', employeeId: 'e-2', employeeName: 'Paul Essai', year: 2026, month: 9, status: 'error' },
    ]);
    expect(echec?.raison.length).toBeGreaterThan(10);
  });
});

class StockageMemoire {
  donnees = new Map<string, string>();
  getItem(cle: string) {
    return this.donnees.get(cle) ?? null;
  }
  setItem(cle: string, valeur: string) {
    this.donnees.set(cle, valeur);
  }
  removeItem(cle: string) {
    this.donnees.delete(cle);
  }
}

describe('interruption — quitter la page en pleine génération ne passe plus inaperçu', () => {
  it('se note, se relit pour la même société, puis s’oublie', () => {
    const stockage = new StockageMemoire();
    noterInterruption(stockage, { companyId: 'c-1', faits: 12, total: 25 });
    expect(lireInterruption(stockage, 'c-1')).toEqual({ companyId: 'c-1', faits: 12, total: 25 });
    expect(lireInterruption(stockage, 'c-2')).toBeNull();
    oublierInterruption(stockage);
    expect(lireInterruption(stockage, 'c-1')).toBeNull();
  });

  it('une note illisible ou un stockage indisponible ne cassent rien', () => {
    const stockage = new StockageMemoire();
    stockage.setItem(CLE_INTERRUPTION, '{pas du json');
    expect(lireInterruption(stockage, 'c-1')).toBeNull();
    expect(lireInterruption(null, 'c-1')).toBeNull();
    expect(() => noterInterruption(null, { companyId: 'c-1', faits: 1, total: 2 })).not.toThrow();
  });

  it('la phrase dit ce qui a été fait et quoi relancer', () => {
    expect(phraseInterruption({ companyId: 'c-1', faits: 12, total: 25 })).toBe(
      'La dernière génération s’est arrêtée quand la page a été quittée : 12 bulletins sur 25 traités. Les autres sont encore « À générer » : relancez « Générer le mois ».'
    );
  });
});
