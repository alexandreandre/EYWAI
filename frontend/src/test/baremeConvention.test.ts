import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  AIDE_BAREME,
  CHAMPS_REMPLACES_PAR_LE_BAREME,
  CHOIX_BAREME,
  baremeModifie,
  champVisible,
  choixBaremeDepuisReglage,
  reglageDepuisChoixBareme,
  texteRegleParLeBareme,
} from "@/features/company/components/baremeConvention";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Barème de la convention dans la carte « Maintien de salaire »", () => {
  it("propose « Aucun » et la plasturgie", () => {
    expect(CHOIX_BAREME.map((c) => [c.libelle, c.code])).toEqual([
      ["Aucun : les réglages ci-dessous", null],
      ["Plasturgie (IDCC 0292)", "plasturgie_0292"],
    ]);
    expect(AIDE_BAREME).toContain("Revenir à « Aucun » rend les réglages manuels");
    expect(texteRegleParLeBareme("Plasturgie (IDCC 0292)")).toBe(
      "Réglé par le barème Plasturgie (IDCC 0292).",
    );
  });

  it("le choix affiché suit le réglage, et l'inverse", () => {
    expect(choixBaremeDepuisReglage(null)).toBe("aucun");
    expect(choixBaremeDepuisReglage("plasturgie_0292")).toBe("plasturgie_0292");
    expect(reglageDepuisChoixBareme("aucun")).toBeNull();
    expect(reglageDepuisChoixBareme("plasturgie_0292")).toBe("plasturgie_0292");
    expect(reglageDepuisChoixBareme("autre")).toBeUndefined();
  });

  it("un barème choisi masque les champs qu'il remplace, et eux seuls", () => {
    const sous = { bareme_convention: "plasturgie_0292" as const };
    const sans = { bareme_convention: null };
    for (const cle of CHAMPS_REMPLACES_PAR_LE_BAREME) {
      expect(champVisible(cle, sous)).toBe(false);
      expect(champVisible(cle, sans)).toBe(true);
    }
    for (const cle of [
      "maintain_working_days",
      "maintain_parental_leave",
      "subrogation_mode",
      "deduire_ijss_sans_subrogation",
      "provident_maintenance_rate",
    ] as const) {
      expect(champVisible(cle, sous)).toBe(true);
    }
  });

  it("dit un choix pas encore enregistré", () => {
    const enregistre = { bareme_convention: null };
    expect(baremeModifie({ bareme_convention: "plasturgie_0292" }, enregistre)).toBe(true);
    expect(baremeModifie({ bareme_convention: null }, enregistre)).toBe(false);
    expect(baremeModifie({ bareme_convention: null }, undefined)).toBe(false);
  });

  it("la carte enregistre le barème, montre son tableau et n'a plus les deux champs morts", () => {
    const carte = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(carte).toContain("bareme_convention: form.bareme_convention ?? null");
    expect(carte).toContain("CHOIX_BAREME.map");
    expect(carte).toContain("<TableauDuBareme bareme={baremeChoisi} />");
    expect(carte).toContain("{TEXTE_LEGAL_SOUS_BAREME}");
    expect(carte).toContain("baremeModifie(form, data)");
    expect(carte).toContain("Barème modifié, pas encore enregistré.");
    expect(carte).toContain(".filter(([key]) => visible(key))");
    expect(carte).not.toContain("Maintien par catégorie");
    expect(carte).not.toContain("Prolongation selon ancienneté");
    expect(carte).not.toContain("maintain_by_category");
    expect(carte).not.toContain("seniority_extension_enabled");
    const api = lire("api/maintenanceSettings.ts");
    expect(api).toContain("bareme_convention: BaremeConvention | null;");
    expect(api).toContain("'/api/maintenance-settings/baremes'");
    expect(api).not.toContain("maintain_by_category");
  });
});
