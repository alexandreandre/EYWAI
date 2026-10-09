import { describe, expect, it } from "vitest";
import { planningWarningsToast } from "@/lib/planningAbsenceWarnings";

const base = {
  requalifiedCount: 0,
  createdCount: 0,
  cancelledCount: 0,
  notices: [],
  hasSyncFailure: false,
};

describe("planningWarningsToast", () => {
  it("accorde au singulier quand un seul élément est touché", () => {
    const t = planningWarningsToast({ ...base, createdCount: 1, cancelledCount: 1, requalifiedCount: 1 });
    expect(t?.description).toBe(
      "1 demande de congé validée créée depuis le calendrier. " +
        "1 demande issue du calendrier annulée. " +
        "1 jour d'absence validée requalifié.",
    );
  });

  it("accorde au pluriel dès deux éléments", () => {
    const t = planningWarningsToast({ ...base, createdCount: 3, cancelledCount: 2, requalifiedCount: 4 });
    expect(t?.description).toBe(
      "3 demandes de congé validées créées depuis le calendrier. " +
        "2 demandes issues du calendrier annulées. " +
        "4 jours d'absence validée requalifiés.",
    );
  });
});
