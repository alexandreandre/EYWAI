import { describe, expect, it } from "vitest";

import { formatPeriodeArret, nbJoursCalendaires, periodeArretEnToutesLettres } from "./arretPeriode";

describe("nbJoursCalendaires", () => {
  it("compte bornes incluses, week-ends compris (17/08 → 18/09 = 33)", () => {
    expect(nbJoursCalendaires(new Date(2026, 7, 17), new Date(2026, 8, 18))).toBe(33);
  });

  it("un seul jour vaut 1", () => {
    expect(nbJoursCalendaires(new Date(2026, 7, 17), new Date(2026, 7, 17))).toBe(1);
  });
});

describe("formatPeriodeArret", () => {
  it("formate la période complète avec le compte calendaire", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17), new Date(2026, 8, 18))).toBe(
      "Du 17/08/2026 au 18/09/2026 (33 jours calendaires)",
    );
  });

  it("formate le singulier", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17), new Date(2026, 7, 17))).toBe(
      "Du 17/08/2026 au 17/08/2026 (1 jour calendaire)",
    );
  });

  it("période en cours de sélection", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17))).toBe("Du 17/08/2026 au …");
  });
});

describe("periodeArretEnToutesLettres (double contrôle avant d'enregistrer)", () => {
  it("nomme les jours de début et de fin et compte les jours calendaires", () => {
    expect(periodeArretEnToutesLettres(new Date(2026, 9, 5), new Date(2026, 9, 16))).toBe(
      "du lundi 05/10/2026 au vendredi 16/10/2026 (12 jours calendaires)",
    );
  });

  it("un arrêt d'un jour", () => {
    expect(periodeArretEnToutesLettres(new Date(2026, 9, 5), new Date(2026, 9, 5))).toBe(
      "le lundi 05/10/2026 (1 jour calendaire)",
    );
  });
});
