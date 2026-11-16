import { describe, expect, it } from "vitest";
import {
  detailMouvement,
  libelleStatutMouvement,
} from "@/features/work-time-tracking/lib/hourAccountLabels";

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

describe("detailMouvement", () => {
  it("dit les heures sup par taux, le repos et ce qui est payé", () => {
    expect(
      detailMouvement({
        movement_type: "credit_hs",
        hours: 13,
        metadata: {
          heures_par_type: { travail_hs50: 2, travail_hs25: 8 },
          hs_paid: 6,
        },
      }),
    ).toBe("8 h sup à 25 %, 2 h sup à 50 % → 13 h de repos ; 6 h sup payées sur le bulletin");
  });

  it("reste lisible sans détail", () => {
    expect(detailMouvement({ movement_type: "credit_hs", hours: 1.25 })).toBe("1,25 h de repos");
    expect(detailMouvement({ movement_type: "debit_recovery", hours: 7 })).toBe(
      "Repos pris, salaire maintenu",
    );
    expect(detailMouvement({ movement_type: "adjustment", hours: 2, note: "Reprise Quadra" })).toBe(
      "Reprise Quadra",
    );
  });
});
