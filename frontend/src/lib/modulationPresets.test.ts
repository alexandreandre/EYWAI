import { describe, expect, it } from "vitest";
import { MODULATION_PRESETS, changementsDuPreset } from "@/lib/modulationPresets";
import type { ModulationSettings } from "@/api/modulation";

const ACTUEL: ModulationSettings = {
  company_id: "c",
  enabled: false,
  configured: true,
  reference_period_months: 12,
  average_weekly_hours: 35,
  weekly_high_hours: 35,
  weekly_low_hours: 35,
  high_weeks_per_cycle: 1,
  low_weeks_per_cycle: 1,
  cycle_start_week_iso: null,
  pay_smoothed: false,
  weekly_cap_hours: 44,
  theoretical_annual_hours: null,
  hour_account_enabled: false,
  hs_franchise_hours_per_period: null,
  hs_franchise_period: "month",
  max_account_balance_hours: null,
  account_credit_source: "overtime_only",
  recovery_absence_enabled: false,
  recovery_debit_timing: "on_validation",
  hs_routing_policy: "pay_all",
};

describe("préréglages de modulation", () => {
  it("liste avant -> après pour la métallurgie annualisée", () => {
    const lignes = changementsDuPreset(ACTUEL, "metallurgie_hour_account");
    const dict = Object.fromEntries(lignes.map((l) => [l.champ, l]));
    expect(dict["Politique des heures supplémentaires"]).toMatchObject({
      avant: "Tout payer au bulletin",
      apres: "Franchise (plafond par période)",
    });
    expect(dict["Compte d'heures"]).toMatchObject({ avant: "Désactivé", apres: "Activé" });
    expect(dict["Annualisation"]).toMatchObject({ avant: "Désactivée", apres: "Activée" });
    expect(dict["Lissage de la rémunération"]).toMatchObject({ avant: "Non", apres: "Oui" });
  });

  it("ne liste pas ce qui ne change pas", () => {
    const lignes = changementsDuPreset(ACTUEL, "standard");
    expect(lignes).toEqual([]);
  });

  it("chaque préréglage connu a un libellé", () => {
    expect(MODULATION_PRESETS.map((p) => p.id)).toEqual([
      "standard",
      "metallurgie_hour_account",
      "hour_account_only",
    ]);
  });
});
