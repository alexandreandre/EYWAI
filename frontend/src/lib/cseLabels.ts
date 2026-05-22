import type {
  ElectedMemberRole,
  MeetingStatus,
  MeetingType,
  RecordingStatus,
  BDESDocumentType,
  ElectionCycleStatus,
  TimelineStepStatus,
} from "@/api/cse";

export const ROLE_LABELS: Record<ElectedMemberRole, string> = {
  titulaire: "Titulaire",
  suppleant: "Suppléant",
  secretaire: "Secrétaire",
  tresorier: "Trésorier",
  autre: "Autre",
};

export const ROLE_BADGE_CLASSES: Record<ElectedMemberRole, string> = {
  titulaire: "bg-blue-100 text-blue-800 border-blue-200",
  suppleant: "bg-green-100 text-green-800 border-green-200",
  secretaire: "bg-purple-100 text-purple-800 border-purple-200",
  tresorier: "bg-orange-100 text-orange-800 border-orange-200",
  autre: "bg-muted text-muted-foreground border-border",
};

export const MEETING_STATUS_LABELS: Record<MeetingStatus, string> = {
  a_venir: "À venir",
  en_cours: "En cours",
  terminee: "Terminée",
};

export const MEETING_STATUS_BADGE_CLASSES: Record<MeetingStatus, string> = {
  a_venir: "bg-blue-100 text-blue-800 border-blue-200",
  en_cours: "bg-amber-100 text-amber-800 border-amber-200",
  terminee: "bg-green-100 text-green-800 border-green-200",
};

export const RECORDING_STATUS_LABELS: Record<RecordingStatus, string> = {
  not_started: "Non démarré",
  in_progress: "En cours",
  completed: "Terminé",
  failed: "Échec",
};

export const MEETING_TYPE_LABELS: Record<MeetingType, string> = {
  ordinaire: "Ordinaire",
  extraordinaire: "Extraordinaire",
  cssct: "CSSCT",
  autre: "Autre",
};

export const BDES_TYPE_LABELS: Record<BDESDocumentType, string> = {
  bdes: "BDES",
  pv: "Procès-verbal",
  autre: "Autre",
};

export const ELECTION_CYCLE_STATUS_LABELS: Record<ElectionCycleStatus, string> = {
  in_progress: "En cours",
  completed: "Terminé",
};

export const TIMELINE_STEP_STATUS_LABELS: Record<TimelineStepStatus, string> = {
  pending: "À faire",
  completed: "Terminé",
  overdue: "En retard",
};

export const CSE_TAB_IDS = [
  "meetings",
  "elected",
  "delegation",
  "bdes",
  "elections",
  "exports",
] as const;

export type CseTabId = (typeof CSE_TAB_IDS)[number];

export function isCseTabId(value: string | null): value is CseTabId {
  return value != null && (CSE_TAB_IDS as readonly string[]).includes(value);
}

export function formatPluralAutres(count: number): string {
  return count > 1 ? "s" : "";
}
