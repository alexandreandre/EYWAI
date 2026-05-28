/** Routage onglets page RH /formation (hash URL + rétrocompatibilité Pack Talent). */

export type FormationTabId =
  | "pilotage"
  | "formations"
  | "conformite"
  | "entretiens"
  | "developpement"
  | "parametres";

export type FormationLegacySub =
  | "habilitations"
  | "obligations"
  | "trames"
  | "catalogue"
  | "budget"
  | "inscriptions"
  | "objectifs"
  | "competences";

const TAB_IDS: FormationTabId[] = [
  "pilotage",
  "formations",
  "conformite",
  "entretiens",
  "developpement",
  "parametres",
];

export const HASH_BY_TAB: Record<FormationTabId, string> = {
  pilotage: "pilotage",
  formations: "formations",
  conformite: "conformite",
  entretiens: "entretiens",
  developpement: "developpement",
  parametres: "parametres",
};

const LEGACY_HASH_TO_TAB: Record<string, FormationTabId> = {
  pilotage: "pilotage",
  formations: "formations",
  conformite: "conformite",
  entretiens: "entretiens",
  developpement: "developpement",
  parametres: "parametres",
  habilitations: "conformite",
  obligations: "conformite",
  catalogue: "formations",
  budget: "formations",
  trames: "parametres",
  objectifs: "developpement",
  competences: "developpement",
};

const LEGACY_HASH_TO_SUB: Record<string, FormationLegacySub> = {
  habilitations: "habilitations",
  obligations: "obligations",
  catalogue: "catalogue",
  budget: "budget",
  trames: "trames",
  objectifs: "objectifs",
  competences: "competences",
};

export type FormationRoute = {
  tab: FormationTabId;
  legacySub?: FormationLegacySub;
};

export function parseFormationRoute(): FormationRoute {
  const raw = window.location.hash.replace(/^#/, "").trim().toLowerCase();
  if (!raw) return { tab: "pilotage" };
  const tab = LEGACY_HASH_TO_TAB[raw];
  if (!tab) return { tab: "pilotage" };
  const legacySub = LEGACY_HASH_TO_SUB[raw];
  return { tab, legacySub };
}

export function isFormationTabId(value: string): value is FormationTabId {
  return TAB_IDS.includes(value as FormationTabId);
}

/** Anciens hash pour redirections routes legacy (formationRedirects). */
export const RH_LEGACY_PATH_TO_HASH: Record<string, string> = {
  "/habilitations": "conformite",
  "/objectives": "developpement",
  "/catalogue-formations": "formations",
};
