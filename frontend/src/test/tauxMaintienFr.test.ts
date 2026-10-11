import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { formatTauxFr } from "@/lib/employeeAbsencesUtils";

/**
 * Pliant « Maintien & subrogation » et fenêtre « Détail du calcul maintien de
 * salaire » : les taux s'écrivaient « Taux appliqué : 50.0 % », « Taux de
 * maintien : 90.0 % ». À la française : « 50 % », « 66,66 % ».
 */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Taux du maintien de salaire, à la française", () => {
  it("sans décimale inutile, avec une virgule sinon", () => {
    expect(formatTauxFr(0.5)).toBe("50 %");
    expect(formatTauxFr(0.6)).toBe("60 %");
    expect(formatTauxFr(0.9)).toBe("90 %");
    expect(formatTauxFr(1)).toBe("100 %");
    expect(formatTauxFr(0.6666)).toBe("66,66 %");
    expect(formatTauxFr(0.783)).toBe("78,3 %");
    expect(formatTauxFr(null)).toBe("0 %");
    expect(formatTauxFr(undefined)).toBe("0 %");
  });

  for (const fichier of [
    "components/absences/MaintenancePreviewBlock.tsx",
    "components/payslip/MaintenanceDetailModal.tsx",
  ]) {
    it(`${fichier} écrit ses taux avec formatTauxFr`, () => {
      const t = lire(fichier);
      expect(t).not.toMatch(/toFixed\(1\)\} %/);
      expect(t).toContain("Taux de maintien : {formatTauxFr(");
      expect(t).toMatch(/Taux (IJSS )?appliqué : \{formatTauxFr\(ijss\.taux_applique\)\}/);
    });
  }
});
