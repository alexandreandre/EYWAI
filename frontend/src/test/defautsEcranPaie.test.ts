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

describe("préréglages de la carte Organisation du temps", () => {
  const texte = lire("features/company/components/ModulationSettingsCard.tsx");

  it("demande confirmation avant d'appliquer un préréglage", () => {
    expect(texte).toContain("AlertDialog");
    expect(texte).toContain("changementsDuPreset");
    expect(texte).toContain("Annuler");
  });

  it("n'applique plus le préréglage directement au clic", () => {
    expect(texte).not.toMatch(/onClick=\{\(\) => applyPresetMutation\.mutate\(p\.id\)\}/);
  });
});

describe("onglet Compte d'heures", () => {
  const texte = lire("features/work-time-tracking/components/HourAccountTab.tsx");

  it("n'affiche plus le statut brut d'un mouvement", () => {
    expect(texte).not.toContain("{m.status}");
  });

  it("marque les chiffres de repli comme estimés", () => {
    expect(texte).toContain("row.estimated");
  });
});
