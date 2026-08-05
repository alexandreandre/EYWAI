import { describe, expect, it } from "vitest";
import { computeTrialPeriodEndDate } from "./trialPeriodUtils";

const iso = (d: Date | null) =>
  d
    ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
      ).padStart(2, "0")}`
    : null;

describe("computeTrialPeriodEndDate", () => {
  it("termine la veille du quantième", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-01", 2, "mois"))).toBe("2026-04-30");
  });

  it("va au dernier jour du mois quand le quantième n'existe pas", () => {
    expect(iso(computeTrialPeriodEndDate("2026-01-31", 1, "mois"))).toBe("2026-02-28");
    expect(iso(computeTrialPeriodEndDate("2028-01-31", 1, "mois"))).toBe("2028-02-29");
  });

  it("compte le jour d'embauche dans les jours", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-02", 8, "jours"))).toBe("2026-03-09");
    expect(iso(computeTrialPeriodEndDate("2026-03-02", 1, "jours"))).toBe("2026-03-02");
  });

  it("compte les semaines", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-02", 2, "semaines"))).toBe("2026-03-15");
  });

  it("refuse une durée nulle", () => {
    expect(computeTrialPeriodEndDate("2026-03-01", 0, "mois")).toBeNull();
  });
});
