import { describe, expect, it } from "vitest";

import { formatPeriodeArret, nbJoursCalendaires } from "./arretPeriode";

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
