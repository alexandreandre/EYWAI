import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { libelleDeLaDemande, libelleTypeArret, typesArretProposes } from "@/lib/employeeAbsencesUtils";
import { libelleSignalement } from "@/components/exports/signalementsArret";
import { ABSENCE_TYPES_MAINTIEN_PREVIEW } from "@/components/absences/MaintenancePreviewBlock";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Saisie d'un congé de maternité, de paternité ou d'adoption", () => {
  it("un congé maternité propose maternité et adoption, pas les types de la maladie", () => {
    expect(typesArretProposes("arret_maternite")).toEqual([
      { value: "maternite", label: "Maternité" },
      { value: "adoption", label: "Adoption" },
      { value: "conge_supplementaire_naissance", label: "Congé supplémentaire de naissance" },
    ]);
  });

  it("un congé paternité propose paternité et adoption", () => {
    expect(typesArretProposes("arret_paternite")).toEqual([
      { value: "paternite", label: "Paternité et accueil de l'enfant" },
      { value: "adoption", label: "Adoption" },
      { value: "conge_supplementaire_naissance", label: "Congé supplémentaire de naissance" },
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

  it("le pliant de maintien s'ouvre aussi pour ces congés", () => {
    expect(ABSENCE_TYPES_MAINTIEN_PREVIEW.has("arret_maternite")).toBe(true);
    expect(ABSENCE_TYPES_MAINTIEN_PREVIEW.has("arret_paternite")).toBe(true);
  });

  it("la fenêtre de saisie tire ses types de la même liste", () => {
    const t = lire("components/AbsenceRequestModal.tsx");
    expect(t).toContain("typesArretProposes(absenceType)");
    expect(t).not.toContain('<SelectItem value="maladie_simple">');
  });
});

describe("Congé supplémentaire de naissance", () => {
  it("la liste des demandes dit le congé, pas la nature sous laquelle il est saisi", () => {
    expect(libelleDeLaDemande("Congé paternité", "conge_supplementaire_naissance")).toBe(
      "Congé supplémentaire de naissance",
    );
    expect(libelleDeLaDemande("Congé paternité", "paternite")).toBe("Congé paternité");
    expect(libelleDeLaDemande("Congé paternité", null)).toBe("Congé paternité");
  });

  it("le signalement du motif 20 se dit en français", () => {
    const texte = libelleSignalement({
      nature: "04",
      motif: "20",
      debut: "2027-01-04",
      fin_prevue: "2027-01-29",
    } as Parameters<typeof libelleSignalement>[0]);
    expect(texte).toBe("Arrêt congé supplémentaire de naissance du 04/01/2027 au 29/01/2027");
  });

  it("la saisie prévient qu'il n'y a pas de maintien et qu'un formulaire est à déposer", () => {
    const t = lire("components/AbsenceRequestModal.tsx");
    expect(t).toContain('arretType === "conge_supplementaire_naissance"');
    expect(t).toContain("formulaire de demande en PDF");
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

describe("Suivi IJSS en mode paie", () => {
  it("la page Absences montre le lien « Suivi IJSS » en mode paie aussi", () => {
    const t = lire("pages/rh/Absences.tsx");
    expect(t).toContain('<Link to="/suivi-ijss">');
    expect(t).not.toMatch(/isPayrollFocusActive\(user\) && \( <Button variant="outline" size="sm" asChild> <Link to="\/suivi-ijss">/);
  });
});
