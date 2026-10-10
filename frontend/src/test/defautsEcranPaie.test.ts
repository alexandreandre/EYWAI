import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** Garde des textes de réglages de paie (lecture du source, comme les autres gardes de ce dossier). */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("carte Compensation des heures entre semaines", () => {
  const texte = lire("features/company/components/CompensationSemainesSettingsCard.tsx");

  it("ne prétend plus qu'elle ne donne jamais lieu à une retenue", () => {
    expect(texte).not.toContain("jamais lieu à une retenue");
  });

  it("dit que les heures sup absorbent d'abord les absences et que le reste est retenu", () => {
    expect(texte).toMatch(/absorbent d&apos;abord les absences/);
    expect(texte).toMatch(/retenu sur les derniers jours manqués/);
  });
});

describe("synthèse mensuelle du calendrier", () => {
  const texte = lire("components/employee-calendar/EmployeeCalendarMonthSummary.tsx");

  it("n'appelle plus « heures supplémentaires » un excédent calculé jour par jour", () => {
    expect(texte).not.toContain("Heures supplémentaires faites");
    expect(texte).toContain("Heures au-delà du prévu");
  });

  it("explique que les heures sup du bulletin se comptent à la semaine", () => {
    expect(texte).toMatch(/heures supplémentaires du bulletin se comptent à la semaine/);
  });
});

describe("mode RTT par défaut", () => {
  const texte = lire("features/company/components/LeaveSettingsCard.tsx");

  it("ne promet pas 10 j/an : le défaut n'accorde aucun RTT", () => {
    expect(texte).not.toContain("Défaut (10 j/an)");
    expect(texte).toContain("Défaut (aucun RTT)");
  });
});
