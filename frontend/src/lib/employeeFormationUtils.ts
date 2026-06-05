import type { AnnualReview, AnnualReviewStatus } from "@/api/annualReviews";
import type { ComputedStatus, EmployeeCertification } from "@/api/certifications";
import type { LegalObligationStatus } from "@/api/legalObligations";
import type { TrainingEnrollment } from "@/api/training";

export type EmployeeFormationTabId =
  | "entretiens"
  | "objectifs"
  | "habilitations"
  | "formations"
  | "obligations"
  | "competences"
  | "onboarding";

export const EMPLOYEE_FORMATION_TAB_IDS: EmployeeFormationTabId[] = [
  "entretiens",
  "objectifs",
  "habilitations",
  "formations",
  "obligations",
  "competences",
  "onboarding",
];

export const EMPLOYEE_HASH_BY_TAB: Record<EmployeeFormationTabId, string> = {
  entretiens: "entretiens",
  objectifs: "objectifs",
  habilitations: "habilitations",
  formations: "formations",
  obligations: "obligations",
  competences: "competences",
  onboarding: "onboarding",
};

export const EMPLOYEE_TAB_BY_HASH: Record<string, EmployeeFormationTabId> = Object.fromEntries(
  EMPLOYEE_FORMATION_TAB_IDS.map((id) => [EMPLOYEE_HASH_BY_TAB[id], id]),
) as Record<string, EmployeeFormationTabId>;

const LAST_TAB_STORAGE_KEY = "employee-formation-last-tab";

export function parseEmployeeFormationHashTab(): EmployeeFormationTabId {
  const raw = window.location.hash.replace(/^#/, "").trim().toLowerCase();
  if (raw && EMPLOYEE_TAB_BY_HASH[raw]) return EMPLOYEE_TAB_BY_HASH[raw];
  const stored = sessionStorage.getItem(LAST_TAB_STORAGE_KEY);
  if (stored && EMPLOYEE_TAB_BY_HASH[stored]) return EMPLOYEE_TAB_BY_HASH[stored];
  return "entretiens";
}

export function persistEmployeeFormationTab(tab: EmployeeFormationTabId) {
  sessionStorage.setItem(LAST_TAB_STORAGE_KEY, EMPLOYEE_HASH_BY_TAB[tab]);
}

const COMPETENCY_LEVEL_LABELS: Record<number, string> = {
  0: "Non évalué",
  1: "Notions de base",
  2: "Opérationnel",
  3: "Maîtrise",
  4: "Expert",
};

export function competencyLevelLabel(level: number | null | undefined): string {
  if (level == null || Number.isNaN(level)) return "—";
  return COMPETENCY_LEVEL_LABELS[level] ?? String(level);
}

const CERT_URGENCY_ORDER: Record<ComputedStatus, number> = {
  expired: 0,
  expiring_soon: 1,
  valid: 2,
  no_expiry: 3,
};

export function sortCertificationsByUrgency(rows: EmployeeCertification[]): EmployeeCertification[] {
  return [...rows].sort((a, b) => {
    const ua = CERT_URGENCY_ORDER[a.computed_status] ?? 9;
    const ub = CERT_URGENCY_ORDER[b.computed_status] ?? 9;
    if (ua !== ub) return ua - ub;
    if (!a.expiry_date && !b.expiry_date) return 0;
    if (!a.expiry_date) return 1;
    if (!b.expiry_date) return -1;
    return new Date(a.expiry_date).getTime() - new Date(b.expiry_date).getTime();
  });
}

export type CertFilter = "all" | "watch" | "valid";

export function filterCertifications(
  rows: EmployeeCertification[],
  filter: CertFilter,
): EmployeeCertification[] {
  if (filter === "all") return rows;
  if (filter === "watch") {
    return rows.filter(
      (r) => r.computed_status === "expiring_soon" || r.computed_status === "expired",
    );
  }
  return rows.filter((r) => r.computed_status === "valid" || r.computed_status === "no_expiry");
}

export function reviewNeedsAction(status: AnnualReviewStatus | string | null | undefined): boolean {
  return status === "en_attente_acceptation" || status === "accepte";
}

export function reviewIsClosed(status: AnnualReviewStatus | string | null | undefined): boolean {
  return status === "cloture" || status === "refuse";
}

export type ReviewFilter = "all" | "action" | "closed";

export function sortAndFilterReviews(
  reviews: AnnualReview[],
  filter: ReviewFilter,
): AnnualReview[] {
  let list = [...reviews];
  if (filter === "action") {
    list = list.filter((r) => reviewNeedsAction(r.status));
  } else if (filter === "closed") {
    list = list.filter((r) => reviewIsClosed(r.status));
  }
  return list.sort((a, b) => {
    const aAction = reviewNeedsAction(a.status) ? 0 : 1;
    const bAction = reviewNeedsAction(b.status) ? 0 : 1;
    if (aAction !== bAction) return aAction - bAction;
    const da = a.planned_date ? new Date(a.planned_date).getTime() : 0;
    const db = b.planned_date ? new Date(b.planned_date).getTime() : 0;
    return db - da;
  });
}

export type EnrollmentGroup = "pending" | "active" | "done";

export function enrollmentGroup(status: string): EnrollmentGroup {
  const s = status.toLowerCase();
  if (s === "demande_salarie" || s === "approuve_manager") return "pending";
  if (
    s === "realise" ||
    s === "completed" ||
    s === "annule" ||
    s === "cancelled" ||
    s === "rejete_manager" ||
    s === "rejete_rh"
  ) {
    return "done";
  }
  return "active";
}

export const ENROLLMENT_GROUP_LABELS: Record<EnrollmentGroup, string> = {
  pending: "En attente RH",
  active: "À venir ou en cours",
  done: "Terminées",
};

export function enrollmentRejectionMessage(e: TrainingEnrollment): string | null {
  const s = e.status.toLowerCase();
  if (s === "rejete_manager" && e.manager_rejection_reason?.trim()) {
    return e.manager_rejection_reason.trim();
  }
  if (s === "rejete_rh" && e.rh_rejection_reason?.trim()) {
    return e.rh_rejection_reason.trim();
  }
  return null;
}

export function enrollmentPendingCount(enrollments: TrainingEnrollment[]): number {
  return enrollments.filter((e) => enrollmentGroup(e.status) === "pending").length;
}

export function certWatchCount(certs: EmployeeCertification[]): number {
  return certs.filter(
    (c) => c.computed_status === "expiring_soon" || c.computed_status === "expired",
  ).length;
}

export function reviewsActionCount(reviews: AnnualReview[]): number {
  return reviews.filter((r) => reviewNeedsAction(r.status)).length;
}

export function sixYearCriteriaMetCount(s: LegalObligationStatus): number {
  let n = 0;
  if (s.criteria_training_completed) n += 1;
  if (s.criteria_certification_obtained) n += 1;
  if (s.criteria_career_evolution) n += 1;
  return n;
}

export function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen).trim()}…`;
}
