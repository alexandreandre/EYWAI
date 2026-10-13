import { describe, expect, it } from 'vitest';
import type { AbsenceBalance } from '@/api/absences';
import {
  formatCongePayeInsufficientMessage,
  formatCongeSansSoldeRh,
  formatQuantiteFr,
  formatBalanceRemaining,
  formatRhLeaveBalanceDetail,
  getRhLeaveBalanceShortLabel,
  isRhLeaveBalanceVisible,
} from './employeeAbsencesUtils';

describe('employeeAbsencesUtils — soldes RH', () => {
  it('raccourcit les libellés pour la fiche employé', () => {
    expect(getRhLeaveBalanceShortLabel('Congés Payés (période précédente)')).toBe('CP N-1');
    expect(getRhLeaveBalanceShortLabel('Congés Payés')).toBe('CP total');
    expect(getRhLeaveBalanceShortLabel('Type inconnu')).toBe('Type inconnu');
  });

  it('masque le congé sans solde du résumé RH', () => {
    const balance: AbsenceBalance = {
      type: 'Congé sans solde',
      acquired: 0,
      taken: 2,
      remaining: 'N/A',
    };
    expect(isRhLeaveBalanceVisible(balance)).toBe(false);
  });

  it('formate le détail acquis / pris / restant', () => {
    const balance: AbsenceBalance = {
      type: 'Congés Payés',
      acquired: 25,
      taken: 6.5,
      remaining: 18.5,
    };
    expect(formatRhLeaveBalanceDetail(balance)).toBe(
      'Acquis : 25 j · Pris : 6,50 j · Restant : 18,50 j',
    );
  });
});

describe("formatCongePayeInsufficientMessage : accord en nombre", () => {
  it("singulier pour un jour, pluriel au-delà", () => {
    expect(formatCongePayeInsufficientMessage(1, 1)).toContain("il vous reste 1 jour disponible pour 1 jour demandé.");
    expect(formatCongePayeInsufficientMessage(2, 3)).toContain("il vous reste 2 jours disponibles pour 3 jours demandés.");
  });
});

describe('formatCongeSansSoldeRh : le texte parle à la RH', () => {
  it('nomme le salarié et ne dit pas « votre »', () => {
    const texte = formatCongeSansSoldeRh('Camille', 2, 3);
    expect(texte).toContain('Le solde de congés payés de Camille est de 2 jours.');
    expect(texte).toContain('3 jours demandés');
    expect(texte).not.toMatch(/votre|vous demandez/i);
  });

  it('dit que l’excédent est payé, sans promettre de sans solde (décision du 12/10)', () => {
    const texte = formatCongeSansSoldeRh('Camille', 2, 4);
    expect(texte).toContain('2 jours au-delà du solde seront payés en entier');
    expect(texte).toContain('le solde passera en négatif');
    expect(texte).toContain('posez plutôt un congé sans solde');
    expect(texte).not.toMatch(/considérés? comme congé sans solde|non rémunéré/);
  });

  it('accorde le singulier et la virgule', () => {
    const texte = formatCongeSansSoldeRh('Camille', 0.5, 1);
    expect(texte).toContain('est de 0,5 jour.');
    expect(texte).toContain('1 jour demandé');
    expect(texte).toContain('0,5 jour au-delà du solde sera payé en entier');
  });
});

describe('formatQuantiteFr : format du bulletin', () => {
  it('deux décimales et virgule quand il y en a, entier sinon', () => {
    expect(formatQuantiteFr(6.24, 'j')).toBe('6,24 j');
    expect(formatQuantiteFr(6.2400000001, 'j')).toBe('6,24 j');
    expect(formatQuantiteFr(10, 'j')).toBe('10 j');
    expect(formatQuantiteFr(2.5, 'h')).toBe('2,50 h');
    expect(formatQuantiteFr(0, 'j')).toBe('0 j');
  });

  it('sert au solde restant du tableau', () => {
    expect(formatBalanceRemaining(6.24, 'j')).toBe('6,24 j');
    expect(formatBalanceRemaining('N/A', 'j')).toBe('Non applicable');
  });
});
