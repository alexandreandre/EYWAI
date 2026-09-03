import { describe, expect, it } from "vitest";

import {
  detectAbsenceConflictDays,
  validatedAbsenceDaysInMonth,
} from "./schedulesAbsenceConflict";
import type { PlannedEventData } from "@/api/calendar";
import type { AbsenceRequest } from "@/api/absences";

const arret = (jours: string[]): AbsenceRequest =>
  ({
    id: "req-1",
    employee_id: "emp-1",
    type: "arret_maladie",
    status: "validated",
    selected_days: jours,
  }) as AbsenceRequest;

describe("detectAbsenceConflictDays", () => {
  it("ne flagge PAS les week-ends d'un arrêt restés typés weekend (design bornes calendaires)", () => {
    // Arrêt ven 14/08/2026 → lun 17/08/2026, selected_days calendaires ;
    // au calendrier, sam 15 et dim 16 restent « weekend » : état NORMAL.
    const planned: PlannedEventData[] = [
      { jour: 14, type: "arret_maladie", heures_prevues: 0 },
      { jour: 15, type: "weekend", heures_prevues: 0 },
      { jour: 16, type: "weekend", heures_prevues: 0 },
      { jour: 17, type: "arret_maladie", heures_prevues: 0 },
    ] as PlannedEventData[];
    const days = validatedAbsenceDaysInMonth(
      [arret(["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17"])],
      2026,
      8,
    );
    expect(detectAbsenceConflictDays(planned, days, 2026, 8)).toEqual([]);
  });

  it("ne flagge pas non plus repos, ni un samedi sans ligne planifiée", () => {
    const planned: PlannedEventData[] = [
      { jour: 14, type: "arret_maladie", heures_prevues: 0 },
      { jour: 16, type: "repos", heures_prevues: 0 },
      // 15/08/2026 (samedi) : aucune ligne planifiée
    ] as PlannedEventData[];
    const days = validatedAbsenceDaysInMonth(
      [arret(["2026-08-14", "2026-08-15", "2026-08-16"])],
      2026,
      8,
    );
    expect(detectAbsenceConflictDays(planned, days, 2026, 8)).toEqual([]);
  });

  it("reconnaît les types calendrier écrits par le backend (conges_payes, rtt)", () => {
    const planned: PlannedEventData[] = [
      { jour: 10, type: "conges_payes", heures_prevues: 0 },
      { jour: 11, type: "rtt", heures_prevues: 0 },
    ] as PlannedEventData[];
    const cp = {
      ...arret(["2026-08-10", "2026-08-11"]),
      type: "conge_paye",
    } as AbsenceRequest;
    const days = validatedAbsenceDaysInMonth([cp], 2026, 8);
    expect(detectAbsenceConflictDays(planned, days, 2026, 8)).toEqual([]);
  });

  it("flagge toujours un vrai conflit : jour ouvré d'absence resté typé travail", () => {
    const planned: PlannedEventData[] = [
      { jour: 14, type: "travail", heures_prevues: 8.5 },
    ] as PlannedEventData[];
    const days = validatedAbsenceDaysInMonth([arret(["2026-08-14"])], 2026, 8);
    expect(detectAbsenceConflictDays(planned, days, 2026, 8)).toEqual([14]);
  });

  it("flagge un jour ouvré d'absence sans ligne planifiée", () => {
    const days = validatedAbsenceDaysInMonth([arret(["2026-08-14"])], 2026, 8);
    expect(detectAbsenceConflictDays([], days, 2026, 8)).toEqual([14]);
  });
});
