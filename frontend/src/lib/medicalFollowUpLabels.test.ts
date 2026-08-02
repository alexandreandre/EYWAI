import { describe, expect, it } from "vitest";
import type { ObligationListItem } from "@/api/medicalFollowUp";
import { hasCurrentWorkplaceAccommodation } from "./medicalFollowUpLabels";

function obligation(over: Partial<ObligationListItem>): ObligationListItem {
  return {
    id: "obl",
    company_id: "co-1",
    employee_id: "emp-1",
    visit_type: "vip",
    trigger_type: "embauche",
    due_date: "2026-09-01",
    priority: 2,
    status: "realisee",
    rule_source: "legal",
    ...over,
  };
}

describe("hasCurrentWorkplaceAccommodation", () => {
  it("retourne false sans aucune obligation", () => {
    expect(hasCurrentWorkplaceAccommodation([])).toBe(false);
  });

  it("retourne false quand aucune visite n'est réalisée", () => {
    const obligations = [
      obligation({ id: "a", status: "a_faire", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("retourne true pour une visite réalisée avec aménagement", () => {
    const obligations = [
      obligation({ id: "a", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("retourne false pour une visite réalisée sans aménagement", () => {
    const obligations = [
      obligation({ id: "a", completed_date: "2026-05-01", amenagement_poste: false }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("ne retient que la visite réalisée la plus récente", () => {
    const obligations = [
      obligation({ id: "vieille", completed_date: "2023-01-10", amenagement_poste: true }),
      obligation({ id: "recente", completed_date: "2026-05-01", amenagement_poste: false }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("affiche l'aménagement posé par la visite la plus récente", () => {
    const obligations = [
      obligation({ id: "vieille", completed_date: "2023-01-10", amenagement_poste: false }),
      obligation({ id: "recente", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("en cas d'ex aequo de dates, l'aménagement l'emporte", () => {
    const obligations = [
      obligation({ id: "sans", completed_date: "2026-05-01", amenagement_poste: false }),
      obligation({ id: "avec", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("ignore les visites réalisées sans date de réalisation", () => {
    const obligations = [
      obligation({ id: "sans-date", completed_date: null, amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });
});
