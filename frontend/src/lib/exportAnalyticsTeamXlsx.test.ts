import { describe, expect, it } from "vitest";

import type { AnalyticsAvances } from "@/api/analytics";
import { getAnalyticsTeamWorkbookSheetNames } from "@/lib/exportAnalyticsTeamXlsx";

const sampleData: AnalyticsAvances = {
  turnover: {
    taux_turnover_annuel: 8.4,
    nb_departs_12_mois: 3,
    nb_embauches_12_mois: 5,
    taux_embauches: 6.2,
    taux_departs: 3.7,
  },
  pyramide_ages: [
    { tranche: "< 25 ans", count: 2, pourcentage: 10 },
    { tranche: "25-34 ans", count: 8, pourcentage: 40 },
  ],
  absenteisme: {
    taux_global: 5.12,
    taux_maladie: 3.2,
    taux_at: 0.8,
    taux_autres: 1.12,
    jours_perdus_total: 42,
    jours_perdus_maladie: 28,
    jours_perdus_at: 6,
    jours_perdus_autres: 8,
    evolution_vs_mois_precedent: -0.3,
  },
  effectif_par_service: [
    { service: "Production", count: 12 },
    { service: "Administration", count: 4 },
  ],
  effectif_par_contrat: [
    { type: "CDI", count: 14 },
    { type: "CDD", count: 2 },
  ],
  masse_salariale_par_service: [
    { service: "Production", service_id: "s1", masse_salariale_brute: 36000 },
    { service: "Administration", service_id: "s2", masse_salariale_brute: 14000 },
  ],
  effectif_actif: 16,
  age_moyen: 38.4,
  anciennete_moyenne_annees: 5.2,
  masse_salariale_brute_totale: 50000,
};

describe("exportAnalyticsTeamXlsx", () => {
  it("produit un classeur multi-feuilles structuré", async () => {
    expect(
      await getAnalyticsTeamWorkbookSheetNames("ACME", "Janvier 2026", sampleData),
    ).toEqual(["Synthèse", "Effectifs", "Turnover & absentéisme", "Masse salariale"]);
  });
});
