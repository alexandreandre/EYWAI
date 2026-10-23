import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  AIDE_IJSS_SANS_SUBROGATION,
  CHOIX_IJSS_SANS_SUBROGATION,
  choixIjssDepuisReglage,
  reglageDepuisChoixIjss,
} from "@/features/company/components/ijssSansSubrogation";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Réglage « sans subrogation : IJSS déduites ou non »", () => {
  it("propose les deux choix, dans les mots de la conception", () => {
    expect(CHOIX_IJSS_SANS_SUBROGATION.map((c) => [c.libelle, c.deduire])).toEqual([
      ["Verser le salaire garanti en entier", false],
      ["Verser le complément, IJSS déduites (règle légale)", true],
    ]);
  });

  it("le texte d'aide explique le choix", () => {
    expect(AIDE_IJSS_SANS_SUBROGATION).toBe(
      "Sans subrogation, la CPAM paie les IJSS directement au salarié. Martine peut les déduire du maintien, comme le prévoit la loi, ou verser le salaire garanti en entier."
    );
  });

  it("le bouton coché suit le réglage, et l'inverse", () => {
    expect(choixIjssDepuisReglage(true)).toBe("complement");
    expect(choixIjssDepuisReglage(false)).toBe("garanti");
    expect(reglageDepuisChoixIjss("complement")).toBe(true);
    expect(reglageDepuisChoixIjss("garanti")).toBe(false);
    expect(reglageDepuisChoixIjss("autre")).toBeNull();
  });

  it("la carte pose les deux boutons et l'aide sous le mode de subrogation, et enregistre le choix", () => {
    const t = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(t).toContain("deduire_ijss_sans_subrogation: form.deduire_ijss_sans_subrogation");
    expect(t).toContain("CHOIX_IJSS_SANS_SUBROGATION.map");
    expect(t).toContain("{AIDE_IJSS_SANS_SUBROGATION}");
    expect(t.indexOf("Mode de subrogation")).toBeLessThan(t.indexOf("CHOIX_IJSS_SANS_SUBROGATION.map"));
    expect(t).toContain("Paramètres de maintien de salaire mis à jour.");
    expect(lire("api/maintenanceSettings.ts")).toContain("deduire_ijss_sans_subrogation: boolean;");
  });
});
