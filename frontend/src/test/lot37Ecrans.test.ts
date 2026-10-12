import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { libelleTypeArret, typesArretProposes } from "@/lib/employeeAbsencesUtils";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Saisie d'un congé de maternité, de paternité ou d'adoption", () => {
  it("un congé maternité propose maternité et adoption, pas les types de la maladie", () => {
    expect(typesArretProposes("arret_maternite")).toEqual([
      { value: "maternite", label: "Maternité" },
      { value: "adoption", label: "Adoption" },
    ]);
  });

  it("un congé paternité propose paternité et adoption", () => {
    expect(typesArretProposes("arret_paternite")).toEqual([
      { value: "paternite", label: "Paternité et accueil de l'enfant" },
      { value: "adoption", label: "Adoption" },
    ]);
  });

  it("un arrêt maladie garde ses huit types", () => {
    const valeurs = typesArretProposes("arret_maladie").map((t) => t.value);
    expect(valeurs).toEqual([
      "maladie_simple",
      "accident_travail",
      "maladie_professionnelle",
      "accident_trajet",
      "mi_temps_therapeutique",
      "ald",
      "rechute_at",
      "arret_exceptionnel",
    ]);
  });

  it("les nouveaux types se disent en français partout", () => {
    expect(libelleTypeArret("maternite")).toBe("Maternité");
    expect(libelleTypeArret("paternite")).toBe("Paternité et accueil de l'enfant");
    expect(libelleTypeArret("adoption")).toBe("Adoption");
  });

  it("la fenêtre de saisie tire ses types de la même liste", () => {
    const t = lire("components/AbsenceRequestModal.tsx");
    expect(t).toContain("typesArretProposes(absenceType)");
    expect(t).not.toContain('<SelectItem value="maladie_simple">');
  });
});

describe("Réglage du maintien pendant les congés de parentalité", () => {
  it("la carte du maintien porte l'interrupteur, éteint par défaut côté serveur", () => {
    const t = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(t).toContain('id="maintain_parental_leave"');
    expect(t).toContain("Maintien pendant les congés de maternité, de paternité et d’adoption");
    expect(t).toContain("maintain_parental_leave: form.maintain_parental_leave");
    expect(lire("api/maintenanceSettings.ts")).toContain("maintain_parental_leave: boolean;");
  });
});
