import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** Gardes du chapitre « Le titre de séjour » (lecture du source, comme les autres gardes de ce dossier). */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("un seul mot pour un titre sans date ([D6-2], 12/10/2026)", () => {
  // Badge « À renseigner », filtre et export « À compléter » : trois mots pour un état.
  for (const fichier of ["components/ResidencePermitBadge.tsx", "features/dashboard/widgets/ResidencePermitCard.tsx"]) {
    it(`${fichier} dit « À compléter »`, () => {
      const texte = lire(fichier);
      expect(texte).not.toContain("À renseigner");
      expect(texte).toContain("À compléter");
    });
  }
});
