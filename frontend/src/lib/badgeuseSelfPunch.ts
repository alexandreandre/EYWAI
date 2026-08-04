import { formatTimeFr } from "@/lib/badgeuseFormat";

export type PunchEvent = {
  timestamp: string;
  event_type: "ENTREE" | "SORTIE";
};

export type SelfPunchState = {
  /** Le prochain pointage sera-t-il une entrée ? */
  isEntry: boolean;
  label: string;
  /** Heure du dernier pointage de la journée, null si aucun. */
  lastPunchLabel: string | null;
};

/**
 * État d'affichage du bouton de badgeage du salarié.
 *
 * Le serveur reste seul maître de la nature du pointage : `next_action` ne
 * sert qu'au libellé. Sans valeur, on suppose une entrée — c'est le cas d'une
 * journée qui n'a pas encore commencé.
 */
export function resolveSelfPunchState(
  nextAction: "ENTREE" | "SORTIE" | undefined,
  events: PunchEvent[] | undefined
): SelfPunchState {
  const isEntry = nextAction !== "SORTIE";
  const list = events ?? [];
  const last = list.length > 0 ? list[list.length - 1] : null;
  return {
    isEntry,
    label: isEntry ? "Je pointe mon entrée" : "Je pointe ma sortie",
    lastPunchLabel: last ? formatTimeFr(last.timestamp) : null,
  };
}

/**
 * Le bouton n'a de sens que sur la journée du jour, et seulement si la société
 * autorise le badgeage depuis le téléphone.
 *
 * Le réglage absent vaut autorisé : c'est la valeur par défaut côté serveur.
 */
export function shouldShowSelfPunchButton(options: {
  isToday: boolean;
  allowSelfToggle: boolean | undefined;
  isEligible: boolean;
}): boolean {
  return (
    options.isToday && options.isEligible && options.allowSelfToggle !== false
  );
}
