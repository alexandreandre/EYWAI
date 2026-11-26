import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  avecMoisDePaie,
  lienAvecMois,
  moisDeLAdresse,
  moisDePaieAffiche,
  moisDePaieRetenu,
  periodeDuMois,
  retenirMoisDePaie,
  EVENEMENT_MOIS_DE_PAIE,
  choisirPaieEnCours,
  paieEnCours,
} from './moisDePaie';

/** Un stockage de session en mémoire, comme sessionStorage. */
function stockage(): Storage {
  const valeurs = new Map<string, string>();
  return {
    get length() {
      return valeurs.size;
    },
    clear: () => valeurs.clear(),
    getItem: (cle) => valeurs.get(cle) ?? null,
    key: (i) => [...valeurs.keys()][i] ?? null,
    removeItem: (cle) => void valeurs.delete(cle),
    setItem: (cle, valeur) => void valeurs.set(cle, String(valeur)),
  };
}

const LE_4_NOVEMBRE = new Date(2026, 10, 4, 9, 0);
const LE_20_NOVEMBRE = new Date(2026, 10, 20, 9, 0);

describe('le mois de paie se lit dans l’adresse', () => {
  it('forme unique : month=AAAA-MM', () => {
    expect(moisDeLAdresse('month=2026-10')).toEqual({ year: 2026, month: 10 });
    expect(moisDeLAdresse(new URLSearchParams('view=month&month=2026-09'))).toEqual({ year: 2026, month: 9 });
  });

  it('l’ancienne forme des Primes (year=2026&month=7) se lit encore', () => {
    expect(moisDeLAdresse('year=2026&month=7&employee=e-1')).toEqual({ year: 2026, month: 7 });
  });

  it('une valeur illisible est ignorée', () => {
    expect(moisDeLAdresse('')).toBeNull();
    expect(moisDeLAdresse('month=2026-13')).toBeNull();
    expect(moisDeLAdresse('month=7')).toBeNull();
    expect(moisDeLAdresse('month=abc')).toBeNull();
  });
});

describe('le mois s’écrit dans l’adresse sous une seule forme', () => {
  it('month=AAAA-MM, l’ancien year retiré, le reste gardé', () => {
    const apres = avecMoisDePaie(new URLSearchParams('year=2026&month=7&employee=e-1'), { year: 2026, month: 10 });
    expect(apres.get('month')).toBe('2026-10');
    expect(apres.has('year')).toBe(false);
    expect(apres.get('employee')).toBe('e-1');
  });

  it('un lien vers un autre écran emporte le mois', () => {
    expect(lienAvecMois('/schedules', { year: 2026, month: 10 })).toBe('/schedules?month=2026-10');
    expect(lienAvecMois('/payroll?view=month', { year: 2027, month: 1 })).toBe('/payroll?view=month&month=2027-01');
  });

  it('la période des exports est la même chaîne', () => {
    expect(periodeDuMois({ year: 2026, month: 10 })).toBe('2026-10');
  });
});

describe('un seul mois de paie d’un écran à l’autre', () => {
  it('sans rien : le mois de paie (jusqu’au 15, le mois précédent), pas le mois civil', () => {
    expect(moisDePaieAffiche('', null, LE_4_NOVEMBRE)).toEqual({ year: 2026, month: 10 });
    expect(moisDePaieAffiche('', null, LE_20_NOVEMBRE)).toEqual({ year: 2026, month: 11 });
  });

  it('le mois choisi sur un écran est retrouvé sur le suivant', () => {
    const session = stockage();
    retenirMoisDePaie({ year: 2026, month: 9 }, session);
    expect(moisDePaieAffiche('', moisDePaieRetenu(session), LE_4_NOVEMBRE)).toEqual({ year: 2026, month: 9 });
  });

  it('l’adresse l’emporte sur la mémoire (un lien, un retour arrière)', () => {
    const session = stockage();
    retenirMoisDePaie({ year: 2026, month: 9 }, session);
    expect(moisDePaieAffiche('month=2026-08', moisDePaieRetenu(session), LE_4_NOVEMBRE)).toEqual({
      year: 2026,
      month: 8,
    });
  });

  it('une mémoire illisible ou absente ne gêne pas', () => {
    const session = stockage();
    session.setItem('martine-mois-de-paie', '{pas du json');
    expect(moisDePaieRetenu(session)).toBeNull();
    expect(moisDePaieRetenu(null)).toBeNull();
    expect(() => retenirMoisDePaie({ year: 2026, month: 9 }, null)).not.toThrow();
  });
});

describe('la paie en cours, par société, choisie et non consultée (Elsa, 26/11)', () => {
  afterEach(() => vi.unstubAllGlobals());
  const LE_26_NOVEMBRE = new Date(2026, 10, 26, 9, 0);

  function fenetre(societe: string) {
    const local = stockage();
    local.setItem('activeCompanyId', societe);
    const evenements: string[] = [];
    vi.stubGlobal('window', {
      localStorage: local,
      dispatchEvent: (e: Event) => {
        evenements.push(e.type);
        return true;
      },
    });
    return { local, evenements };
  }

  it('sans choix : le mois de paie par défaut', () => {
    fenetre('lewis');
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 11 });
  });

  it('LEWIS choisit octobre, une autre société reste en novembre', () => {
    const f = fenetre('lewis');
    choisirPaieEnCours({ year: 2026, month: 10 });
    expect(f.evenements).toEqual([EVENEMENT_MOIS_DE_PAIE]);
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 10 });
    f.local.setItem('activeCompanyId', 'autre');
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 11 });
    f.local.setItem('activeCompanyId', 'lewis');
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 10 });
  });

  it('consulter un mois (mois retenu de l’affichage) ne change pas la paie en cours', () => {
    const f = fenetre('lewis');
    retenirMoisDePaie({ year: 2026, month: 9 }, stockage());
    expect(f.evenements).toEqual([]);
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 11 });
  });

  it('un choix trop ancien ou trop loin revient au mois par défaut', () => {
    fenetre('lewis');
    choisirPaieEnCours({ year: 2025, month: 10 });
    expect(paieEnCours(LE_26_NOVEMBRE)).toEqual({ year: 2026, month: 11 });
  });

  it('choisir le même mois ne prévient personne', () => {
    const f = fenetre('lewis');
    choisirPaieEnCours({ year: 2026, month: 10 });
    choisirPaieEnCours({ year: 2026, month: 10 });
    expect(f.evenements).toHaveLength(1);
  });
});
