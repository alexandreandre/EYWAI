import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import type { AbsenceRequest } from "@/api/absences";
import { getCalendarTypeLabel, MOTIF_CONGE_PARENTAL } from "@/lib/calendarTypes";
import {
  bornesDesJours,
  estCongeParental,
  getAbsenceTypeLabel,
  joursDeLaPeriode,
  LIBELLE_CONGE_PARENTAL,
  refusPeriodeCongeParental,
  SOUS_TYPE_CONGE_PARENTAL,
} from "@/lib/employeeAbsencesUtils";

/**
 * Retour d'Elsa du 26/11 : « il manque la possibilité de mettre un congé
 * parental ». Il se saisit comme un congé sans solde de sous-type
 * `conge_parental_education`, du premier jour à la fin prévue, et se nomme
 * « Congé parental d'éducation » partout.
 */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

function demande(partiel: Partial<AbsenceRequest>): AbsenceRequest {
  return {
    id: "a-1",
    employee_id: "e-1",
    type: "sans_solde",
    status: "validated",
    selected_days: [],
    ...partiel,
  } as AbsenceRequest;
}

describe("Congé parental d'éducation : libellés", () => {
  it("la liste des absences le nomme, un sans solde ordinaire garde son nom", () => {
    expect(SOUS_TYPE_CONGE_PARENTAL).toBe("conge_parental_education");
    const parental = demande({ event_subtype: SOUS_TYPE_CONGE_PARENTAL });
    expect(estCongeParental(parental)).toBe(true);
    expect(getAbsenceTypeLabel(parental)).toBe(LIBELLE_CONGE_PARENTAL);
    expect(LIBELLE_CONGE_PARENTAL).toBe("Congé parental d'éducation");
    expect(getAbsenceTypeLabel(demande({}))).toBe("Congé sans solde");
    expect(estCongeParental(demande({ type: "rtt", event_subtype: SOUS_TYPE_CONGE_PARENTAL }))).toBe(false);
  });

  it("le calendrier nomme le jour d'après le motif posé par le serveur", () => {
    expect(getCalendarTypeLabel("absence_non_remuneree", MOTIF_CONGE_PARENTAL)).toBe(
      "Congé parental d'éducation",
    );
    expect(getCalendarTypeLabel("absence_non_remuneree")).toBe("Absence non rémunérée");
    expect(getCalendarTypeLabel("absence_non_remuneree", null)).toBe("Absence non rémunérée");
    // Le motif ne requalifie jamais un autre type de jour.
    expect(getCalendarTypeLabel("travail", MOTIF_CONGE_PARENTAL)).toBe("Travail");
  });

  it("la page Absences et les cellules du calendrier passent par ces libellés", () => {
    expect(lire("pages/rh/Absences.tsx")).toContain("estCongeParental(req) ? ( LIBELLE_CONGE_PARENTAL");
    expect(lire("components/CalendarDayCell.tsx")).toContain(
      "getCalendarTypeLabel(plannedDay.type, plannedDay.motif_absence)",
    );
    expect(lire("components/EmployeeCalendarDayCell.tsx")).toContain(
      "getCalendarTypeLabel(dayType, dayData?.motif_absence)",
    );
    for (const vue of [
      "components/employee-calendar/EmployeePlanningWeekView.tsx",
      "components/employee-calendar/EmployeeCalendarMonthList.tsx",
      "components/employee-calendar/EmployeeCalendarDaySheet.tsx",
      "components/schedules/JourVoisinCell.tsx",
    ]) {
      expect(lire(vue)).toMatch(/getCalendarTypeLabel\([^)]*motif_absence\)/);
      expect(lire(vue)).not.toMatch(/getCalendarTypeLabel\((dayType|type)\)/);
    }
  });
});

describe("Congé parental d'éducation : période", () => {
  it("les jours de la période, week-ends compris, et ses bornes", () => {
    const jours = joursDeLaPeriode("2026-07-01", "2026-07-31");
    expect(jours).toHaveLength(31);
    expect(jours[0]).toBe("2026-07-01");
    expect(jours[30]).toBe("2026-07-31");
    // Passage à l'heure d'hiver : pas de jour perdu ni doublé.
    expect(joursDeLaPeriode("2026-10-24", "2026-10-27")).toEqual([
      "2026-10-24",
      "2026-10-25",
      "2026-10-26",
      "2026-10-27",
    ]);
    expect(joursDeLaPeriode("2026-07-02", "2026-07-01")).toEqual([]);
    expect(bornesDesJours(["2026-08-03", "2026-07-01", "2026-07-02"])).toEqual({
      debut: "2026-07-01",
      fin: "2026-08-03",
    });
    expect(bornesDesJours([])).toBeNull();
  });

  it("la fin prévue est obligatoire et suit le premier jour", () => {
    expect(refusPeriodeCongeParental("", "2027-06-30")).toMatch(/premier jour/);
    expect(refusPeriodeCongeParental("2026-07-01", "")).toMatch(/fin prévue/);
    expect(refusPeriodeCongeParental("2026-07-01", "2026-06-30")).toMatch(/antérieure/);
    expect(refusPeriodeCongeParental("2026-07-01", "2030-07-01")).toMatch(/3 ans/);
    expect(refusPeriodeCongeParental("2026-07-01", "2027-06-30")).toBeNull();
  });

  it("la saisie RH l'envoie en sans solde de sous-type, par période", () => {
    const t = lire("components/AbsenceRequestModal.tsx");
    expect(t).toContain("{ value: CHOIX_CONGE_PARENTAL, label: LIBELLE_CONGE_PARENTAL }");
    expect(t).toContain('type: estChoixCongeParental ? "sans_solde"');
    expect(t).toContain("payload.event_subtype = SOUS_TYPE_CONGE_PARENTAL;");
    expect(t).toContain("payload.date_debut = parentalDebut; payload.date_fin = parentalFin;");
    expect(t).toContain("La DSN le déclare en suspension 632.");
  });
});
