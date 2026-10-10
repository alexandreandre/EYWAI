import { describe, expect, it } from "vitest";
import { libelleStatutMouvement } from "@/features/work-time-tracking/lib/hourAccountLabels";

describe("statuts des mouvements du compte d'heures", () => {
  it("traduit les statuts en français", () => {
    expect(libelleStatutMouvement("validated")).toBe("Validé");
    expect(libelleStatutMouvement("applied_payroll")).toBe("Appliqué à la paie");
    expect(libelleStatutMouvement("pending")).toBe("En attente");
    expect(libelleStatutMouvement("rejected")).toBe("Refusé");
  });

  it("n'affiche jamais un identifiant brut pour un statut inconnu", () => {
    expect(libelleStatutMouvement("zz_inconnu")).toBe("Statut inconnu");
    expect(libelleStatutMouvement("")).toBe("—");
  });
});
