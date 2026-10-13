import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import type { PlannedEventData } from '@/api/calendar';
import {
  copierMoisPrecedent,
  joursTypesDeLaSemaine,
  noteJoursGardes,
} from './copieMoisPrecedent';

/** Septembre 2026 : le 1er est un mardi. Lundi 7 h, mardi à jeudi 8 h,
 * vendredi 4 h, samedi et dimanche non travaillés. */
function septembre(): PlannedEventData[] {
  const heuresParJour: Record<number, number | null> = {
    1: 7,
    2: 8,
    3: 8,
    4: 8,
    5: 4,
  };
  const jours: PlannedEventData[] = [];
  for (let jour = 1; jour <= 30; jour += 1) {
    const jourSemaine = new Date(2026, 8, jour).getDay();
    jours.push(
      jourSemaine === 0 || jourSemaine === 6
        ? { jour, type: 'weekend', heures_prevues: null }
        : { jour, type: 'travail', heures_prevues: heuresParJour[jourSemaine] ?? null }
    );
  }
  return jours;
}

const jourDe = (jours: PlannedEventData[], jour: number) => jours.find((j) => j.jour === jour);

describe('copierMoisPrecedent — par jour de la semaine', () => {
  it('chaque lundi reçoit le lundi type du mois précédent, pas le même numéro de jour', () => {
    const { jours } = copierMoisPrecedent({
      source: septembre(),
      anneeSource: 2026,
      moisSource: 9,
      cible: [],
      annee: 2026,
      mois: 10,
    });
    expect(jours).toHaveLength(31);
    // Samedi 3 et dimanche 4 octobre : non travaillés.
    expect(jourDe(jours, 3)).toEqual({ jour: 3, type: 'weekend', heures_prevues: null });
    expect(jourDe(jours, 4)).toEqual({ jour: 4, type: 'weekend', heures_prevues: null });
    // Lundi 5 et mardi 6 octobre : travaillés, aux heures du lundi et du mardi.
    expect(jourDe(jours, 5)).toEqual({ jour: 5, type: 'travail', heures_prevues: 7 });
    expect(jourDe(jours, 6)).toEqual({ jour: 6, type: 'travail', heures_prevues: 8 });
    // Lundi 19 et mardi 20 octobre (heures de badgeuse du rejeu) : travaillés.
    expect(jourDe(jours, 19)?.type).toBe('travail');
    expect(jourDe(jours, 20)?.type).toBe('travail');
    // Vendredi 30 octobre : 4 h.
    expect(jourDe(jours, 30)).toEqual({ jour: 30, type: 'travail', heures_prevues: 4 });
  });

  it('une absence ou un férié du mois source ne fait pas le jour type', () => {
    const source = septembre().map((j) => {
      if (j.jour === 7) return { ...j, type: 'conges_payes', heures_prevues: 0, origine: 'absence' };
      if (j.jour === 14) return { ...j, type: 'arret_maladie', heures_prevues: 0 };
      if (j.jour === 21) return { ...j, type: 'ferie', heures_prevues: null };
      return j;
    });
    const types = joursTypesDeLaSemaine(source, 2026, 9);
    // Lundis de septembre : 7 (CP), 14 (arrêt), 21 (férié), 28 (7 h).
    expect(types.get(1)).toEqual({ type: 'travail', heures_prevues: 7 });
  });

  it('le jour type est le plus fréquent du mois source', () => {
    const source = septembre().map((j) =>
      j.jour === 2 || j.jour === 9 ? { ...j, heures_prevues: 6 } : j
    );
    // Mercredis : 2 et 9 à 6 h, 16, 23 et 30 à 8 h.
    expect(joursTypesDeLaSemaine(source, 2026, 9).get(3)).toEqual({
      type: 'travail',
      heures_prevues: 8,
    });
  });

  it('garde les fériés et les absences déjà posés sur le mois copié, et les compte', () => {
    const cible: PlannedEventData[] = [
      { jour: 11, type: 'ferie', heures_prevues: null },
      { jour: 12, type: 'conges_payes', heures_prevues: 0, origine: 'absence' },
      { jour: 13, type: 'arret_maladie', heures_prevues: 0 },
    ];
    const resultat = copierMoisPrecedent({
      source: septembre(),
      anneeSource: 2026,
      moisSource: 9,
      cible,
      annee: 2026,
      mois: 11,
    });
    expect(jourDe(resultat.jours, 11)).toEqual(cible[0]);
    expect(jourDe(resultat.jours, 12)).toEqual(cible[1]);
    expect(jourDe(resultat.jours, 13)).toEqual(cible[2]);
    expect(resultat.feriesGardes).toBe(1);
    expect(resultat.absencesGardees).toBe(2);
    // Lundi 16 novembre : lundi type.
    expect(jourDe(resultat.jours, 16)).toEqual({ jour: 16, type: 'travail', heures_prevues: 7 });
  });

  it('sans jour type pour un jour de la semaine, le jour copié reste tel quel', () => {
    const source = septembre().map((j) =>
      new Date(2026, 8, j.jour).getDay() === 1
        ? { ...j, type: 'conges_payes', heures_prevues: 0 }
        : j
    );
    const { jours } = copierMoisPrecedent({
      source,
      anneeSource: 2026,
      moisSource: 9,
      cible: [{ jour: 5, type: 'travail', heures_prevues: 6 }],
      annee: 2026,
      mois: 10,
    });
    expect(jourDe(jours, 5)).toEqual({ jour: 5, type: 'travail', heures_prevues: 6 });
    expect(jourDe(jours, 12)).toEqual({ jour: 12, type: 'travail', heures_prevues: null });
  });
});

describe('noteJoursGardes', () => {
  it('accorde les fériés et les absences gardés', () => {
    expect(noteJoursGardes(0, 0)).toBe('');
    expect(noteJoursGardes(1, 0)).toBe(' 1 jour férié gardé.');
    expect(noteJoursGardes(2, 1)).toBe(" 2 jours fériés gardés. 1 jour d'absence gardé.");
    expect(noteJoursGardes(0, 3)).toBe(" 3 jours d'absence gardés.");
  });
});

describe('les deux boutons « Copier mois précédent » passent par la copie par jour de la semaine', () => {
  it.each([
    '../components/schedules/CalendarBulkActionsBar.tsx',
    '../hooks/useCalendar.ts',
  ])('%s', (fichier) => {
    const source = fs.readFileSync(path.resolve(__dirname, fichier), 'utf8');
    expect(source).toContain('copierMoisPrecedent(');
  });
});
