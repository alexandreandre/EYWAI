import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import type { MaintenancePreview } from "@/api/absences";
import {
  eurosFr,
  ligneDuPalier,
  lignesDesPaliers,
  pourcentFr,
  titreDesPaliers,
} from "@/lib/paliersAffichage";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

const JUILLET = {
  maintien_applicable: true,
  taux_maintien: 0.7425,
  maintien_cible: 1722.12,
  maintien_verse: 445.23,
  complement_employeur: 445.23,
  nb_jours_maintien: 23,
  conflit_convention: false,
  bareme: "plasturgie_0292",
  bareme_detail: "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus",
  regle_retenue: "convention",
  paliers_en_jours_ouvres: true,
  paliers: [
    { taux: 1, du: "2026-07-01", au: "2026-07-02", jours: 2, garanti: 194.04, ijss_deduites: 82.38 },
    { taux: 0.75, du: "2026-07-03", au: "2026-07-31", jours: 21, garanti: 1528.08, ijss_deduites: 1194.51 },
  ],
} as MaintenancePreview["maintien"];

describe("Paliers de la convention au détail du maintien", () => {
  it("formate les montants et les taux comme le bulletin", () => {
    expect(eurosFr(1722.12)).toBe("1 722,12 €");
    expect(eurosFr(82.38)).toBe("82,38 €");
    expect([1, 0.75, 0.5, 0.9, 0.6667].map(pourcentFr)).toEqual([
      "100 %", "75 %", "50 %", "90 %", "66,67 %",
    ]);
  });

  it("une ligne par palier, avec ses IJSS déduites", () => {
    expect(lignesDesPaliers(JUILLET)).toEqual([
      "Du 01/07 au 02/07 : 2 jours ouvrés à 100 % — 194,04 € (IJSS déduites 82,38 €)",
      "Du 03/07 au 31/07 : 21 jours ouvrés à 75 % — 1 528,08 € (IJSS déduites 1 194,51 €)",
    ]);
    expect(
      ligneDuPalier({ taux: 1, du: "2026-05-04", au: "2026-05-04", jours: 1, garanti: 102.99 }, false),
    ).toBe("Du 04/05 au 04/05 : 1 jour à 100 % — 102,99 €");
  });

  it("le titre dit le barème, ou le légal quand il l'emporte, et rien sans barème", () => {
    expect(titreDesPaliers(JUILLET)).toBe("Plasturgie (IDCC 0292), non-cadres, 5 ans et plus");
    expect(titreDesPaliers({ ...JUILLET, regle_retenue: "legal" })).toBe(
      "Maintien légal, plus favorable ce mois-ci que le barème",
    );
    const { paliers: _p, bareme_detail: _d, ...sans } = JUILLET;
    expect(titreDesPaliers(sans as MaintenancePreview["maintien"])).toBeNull();
    expect(lignesDesPaliers(sans as MaintenancePreview["maintien"])).toEqual([]);
  });

  it("le détail du bulletin et l'aperçu de l'absence montrent la section", () => {
    const modal = lire("components/payslip/MaintenanceDetailModal.tsx");
    expect(modal).toContain("Paliers de la convention");
    expect(modal).toContain("lignesDesPaliers(m).map");
    const apercu = lire("components/absences/MaintenancePreviewBlock.tsx");
    expect(apercu).toContain("lignesDesPaliers(maintien).map");
  });
});
