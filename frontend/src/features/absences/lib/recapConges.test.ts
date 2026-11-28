import { describe, expect, it } from 'vitest';

import type { RecapConges } from '@/api/absences';
import {
  colonnesDuTableau,
  etatDuRecap,
  filtrerSalaries,
  formatJours,
  libellePeriode,
  messagePeriodeRecap,
  periodeDuMoisDePaie,
} from './recapConges';

const recap = (totaux: Record<string, number>): RecapConges => ({
  debut: '2026-11-01',
  fin: '2026-11-30',
  colonnes: [
    { cle: 'cp', libelle: 'Congés payés', source: 'Calendrier' },
    { cle: 'rtt', libelle: 'RTT', source: 'Calendrier' },
    { cle: 'arret_maladie', libelle: 'Arrêt maladie', source: 'Calendrier' },
  ],
  source_soldes: 'Aperçu des soldes',
  note_arrets: 'Arrêts',
  date_des_soldes: '2026-11-28',
  salaries: [
    { employee_id: 'a', prenom: 'Élodie', nom: 'Zed', matricule: '007', jours: {}, total_jours: 0, solde_cp_n1: 1, solde_cp_n: 2 },
    { employee_id: 'b', prenom: 'Bob', nom: 'Yod', matricule: null, jours: {}, total_jours: 0, solde_cp_n1: null, solde_cp_n: null },
  ],
  totaux,
  aucun_jour: Object.values(totaux).every((v) => v <= 0),
});

describe('récapitulatif des congés', () => {
  it('prend par défaut tout le mois de paie', () => {
    expect(periodeDuMoisDePaie({ year: 2026, month: 11 })).toEqual({ debut: '2026-11-01', fin: '2026-11-30' });
    expect(periodeDuMoisDePaie({ year: 2028, month: 2 })).toEqual({ debut: '2028-02-01', fin: '2028-02-29' });
  });

  it('refuse une période vide, à l’envers ou de plus d’un an, et dit pourquoi', () => {
    expect(messagePeriodeRecap({ debut: '', fin: '2026-11-30' })).toBe('Choisissez le premier jour de la période.');
    expect(messagePeriodeRecap({ debut: '2026-11-30', fin: '2026-11-01' })).toBe('Le premier jour est après le dernier.');
    expect(messagePeriodeRecap({ debut: '2025-01-01', fin: '2026-11-30' })).toBe('Période trop longue : un an au plus.');
    expect(messagePeriodeRecap({ debut: '2026-02-30', fin: '2026-03-01' })).toBe('Choisissez le premier jour de la période.');
    expect(messagePeriodeRecap({ debut: '2026-01-01', fin: '2026-12-31' })).toBeNull();
  });

  it('dit toujours où il en est : chargement, erreur, aucun congé, prêt', () => {
    const base = { periodeRefusee: false, chargement: false, erreur: false };
    expect(etatDuRecap({ ...base, periodeRefusee: true, recap: undefined })).toBe('periode');
    expect(etatDuRecap({ ...base, chargement: true, recap: undefined })).toBe('chargement');
    expect(etatDuRecap({ ...base, erreur: true, recap: undefined })).toBe('erreur');
    expect(etatDuRecap({ ...base, recap: undefined })).toBe('erreur');
    expect(etatDuRecap({ ...base, recap: recap({ cp: 0 }) })).toBe('vide');
    expect(etatDuRecap({ ...base, recap: recap({ cp: 1.5 }) })).toBe('pret');
  });

  it('montre seulement les colonnes qui ont des jours et nomme les autres', () => {
    const { affichees, masquees } = colonnesDuTableau(recap({ cp: 3, rtt: 0, arret_maladie: 2 }));
    expect(affichees.map((c) => c.cle)).toEqual(['cp', 'arret_maladie']);
    expect(masquees.map((c) => c.libelle)).toEqual(['RTT']);
  });

  it('cherche par nom, prénom ou matricule sans les accents', () => {
    const r = recap({ cp: 1 });
    expect(filtrerSalaries(r.salaries, 'elodie').map((s) => s.employee_id)).toEqual(['a']);
    expect(filtrerSalaries(r.salaries, '007').map((s) => s.employee_id)).toEqual(['a']);
    expect(filtrerSalaries(r.salaries, '  ')).toHaveLength(2);
  });

  it('écrit les jours à la française et dit un solde non calculé', () => {
    expect(formatJours(2.5)).toBe('2,5');
    expect(formatJours(0)).toBe('0');
    expect(formatJours(null)).toBe('non calculé');
    expect(libellePeriode({ debut: '2026-11-01', fin: '2026-11-30' })).toBe('du 01/11/2026 au 30/11/2026');
  });
});
