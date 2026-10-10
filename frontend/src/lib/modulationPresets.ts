import type { HsRoutingPolicy, ModulationSettings } from "@/api/modulation";

/**
 * Préréglages du temps de travail. Les valeurs reprennent
 * `_MODULATION_PRESETS` (backend/app/modules/modulation/application/commands.py) :
 * elles servent uniquement à montrer à la gestionnaire ce qui va changer avant
 * qu'elle confirme ; c'est le serveur qui applique.
 */
export const MODULATION_PRESETS = [
  { id: "standard", label: "Standard (HS payées)" },
  { id: "metallurgie_hour_account", label: "Métallurgie annualisée" },
  { id: "hour_account_only", label: "Compte HS sans modulation" },
] as const;

export type ModulationPresetId = (typeof MODULATION_PRESETS)[number]["id"];

const VALEURS: Record<ModulationPresetId, Partial<ModulationSettings>> = {
  standard: {
    enabled: false,
    hour_account_enabled: false,
    hs_routing_policy: "pay_all",
    pay_smoothed: false,
  },
  metallurgie_hour_account: {
    enabled: true,
    reference_period_months: 12,
    average_weekly_hours: 35,
    weekly_high_hours: 37,
    weekly_low_hours: 32,
    high_weeks_per_cycle: 1,
    low_weeks_per_cycle: 1,
    pay_smoothed: true,
    weekly_cap_hours: 44,
    hour_account_enabled: true,
    hs_franchise_hours_per_period: 14,
    hs_franchise_period: "month",
    hs_routing_policy: "franchise",
    account_credit_source: "overtime_only",
    recovery_absence_enabled: true,
    recovery_debit_timing: "on_validation",
  },
  hour_account_only: {
    enabled: false,
    hour_account_enabled: true,
    hs_routing_policy: "account_all",
    pay_smoothed: false,
    recovery_absence_enabled: true,
    recovery_debit_timing: "on_validation",
  },
};

const POLITIQUES: Record<HsRoutingPolicy, string> = {
  pay_all: "Tout payer au bulletin",
  account_all: "Tout mettre au compteur",
  franchise: "Franchise (plafond par période)",
  manual: "Validation RH mensuelle",
};

const heures = (v: unknown) => (v == null ? "Non renseigné" : `${String(v).replace(".", ",")} h`);
const actif = (v: unknown) => (v ? "Activé" : "Désactivé");

interface Champ {
  cle: keyof ModulationSettings;
  champ: string;
  format: (v: unknown) => string;
}

const CHAMPS: Champ[] = [
  {
    cle: "hs_routing_policy",
    champ: "Politique des heures supplémentaires",
    format: (v) => POLITIQUES[v as HsRoutingPolicy] ?? String(v),
  },
  { cle: "hour_account_enabled", champ: "Compte d'heures", format: actif },
  { cle: "enabled", champ: "Annualisation", format: (v) => (v ? "Activée" : "Désactivée") },
  { cle: "pay_smoothed", champ: "Lissage de la rémunération", format: (v) => (v ? "Oui" : "Non") },
  {
    cle: "reference_period_months",
    champ: "Période de référence",
    format: (v) => `${String(v)} mois`,
  },
  { cle: "average_weekly_hours", champ: "Moyenne hebdomadaire", format: heures },
  { cle: "weekly_high_hours", champ: "Semaine haute", format: heures },
  { cle: "weekly_low_hours", champ: "Semaine basse", format: heures },
  {
    cle: "high_weeks_per_cycle",
    champ: "Semaines hautes par cycle",
    format: (v) => String(v),
  },
  {
    cle: "low_weeks_per_cycle",
    champ: "Semaines basses par cycle",
    format: (v) => String(v),
  },
  { cle: "weekly_cap_hours", champ: "Plafond hebdomadaire", format: heures },
  {
    cle: "hs_franchise_hours_per_period",
    champ: "Franchise d'heures supplémentaires",
    format: heures,
  },
  {
    cle: "hs_franchise_period",
    champ: "Période de la franchise",
    format: (v) => (v === "month" ? "Mois" : "Période de paie"),
  },
  {
    cle: "account_credit_source",
    champ: "Heures créditées au compte",
    format: (v) => (v === "overtime_only" ? "Heures supplémentaires seules" : "Surplus au-delà du modulé"),
  },
  { cle: "recovery_absence_enabled", champ: "Récupération par absence", format: actif },
  {
    cle: "recovery_debit_timing",
    champ: "Débit de la récupération",
    format: (v) => (v === "on_validation" ? "À la validation" : "À la paie"),
  },
];

export interface ChangementPreset {
  champ: string;
  avant: string;
  apres: string;
}

/** Ce que le préréglage modifie par rapport aux réglages actuels (rien si déjà identique). */
export function changementsDuPreset(
  actuel: ModulationSettings,
  preset: ModulationPresetId,
): ChangementPreset[] {
  const cible = VALEURS[preset];
  const out: ChangementPreset[] = [];
  for (const c of CHAMPS) {
    if (!(c.cle in cible)) continue;
    const apres = cible[c.cle];
    const avant = actuel[c.cle];
    if (avant === apres) continue;
    out.push({ champ: c.champ, avant: c.format(avant), apres: c.format(apres) });
  }
  return out;
}
