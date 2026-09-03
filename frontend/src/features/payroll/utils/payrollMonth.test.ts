import { describe, expect, it } from "vitest";

import { moisDePaieParDefaut } from "./payrollMonth";

describe("moisDePaieParDefaut", () => {
  it("jusqu'au 15, on prépare encore la paie du mois précédent", () => {
    expect(moisDePaieParDefaut(new Date(2026, 8, 3))).toEqual({
      year: 2026,
      month: 8,
    });
    expect(moisDePaieParDefaut(new Date(2026, 8, 15))).toEqual({
      year: 2026,
      month: 8,
    });
  });

  it("après le 15, la paie du mois courant", () => {
    expect(moisDePaieParDefaut(new Date(2026, 8, 16))).toEqual({
      year: 2026,
      month: 9,
    });
    expect(moisDePaieParDefaut(new Date(2026, 7, 28))).toEqual({
      year: 2026,
      month: 8,
    });
  });

  it("passe l'année en janvier", () => {
    expect(moisDePaieParDefaut(new Date(2027, 0, 5))).toEqual({
      year: 2026,
      month: 12,
    });
  });
});
