import {
  ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS,
  INTERVIEW_TYPE_LABELS,
  type AnnualReview,
  type AnnualReviewListItem,
  type AnnualReviewStatus,
  type InterviewType,
} from "@/api/annualReviews";

/** Champs minimaux pour tri / retard sur liste globale RH. */
export type AnnualReviewListLike = Pick<
  AnnualReviewListItem,
  | "id"
  | "status"
  | "planned_date"
  | "completed_date"
  | "year"
  | "created_at"
  | "interview_type"
  | "employee_acceptance_status"
  | "signature_status"
>;

const ACTIONABLE_STATUSES: AnnualReviewStatus[] = [
  "planifie",
  "en_attente_acceptation",
  "accepte",
];

export function isActionableAnnualReviewStatus(status: AnnualReviewStatus): boolean {
  return ACTIONABLE_STATUSES.includes(status);
}

/** Entretiens supprimables par le RH avant réalisation / clôture du cycle. */
export function canRhDeleteAnnualReview(status: AnnualReviewStatus): boolean {
  return status === "planifie" || status === "en_attente_acceptation";
}

export function formatAnnualReviewDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    const d = value.includes("T") ? new Date(value) : new Date(`${value}T12:00:00`);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

const INTERVIEW_TYPE_SHORT_LABELS: Record<InterviewType, string> = {
  annual_performance: "Annuel",
  professional_2ans: "Pro. 2 ans",
  competency_6ans: "Comp. 6 ans",
  return_absence: "Retour abs.",
  mid_year: "Mi-année",
  other: "Autre",
};

export function interviewTypeLabel(type: string | undefined | null): string {
  if (!type) return "—";
  return INTERVIEW_TYPE_LABELS[type as InterviewType] ?? type;
}

/** Libellé court pour listes et tableaux. */
export function interviewTypeShortLabel(type: string | undefined | null): string {
  if (!type) return "—";
  return INTERVIEW_TYPE_SHORT_LABELS[type as InterviewType] ?? interviewTypeLabel(type);
}

export function signatureStatusLabel(status: string | null | undefined): string | null {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "pending") return "Signature en attente";
  if (s === "signed") return "Signé";
  if (s === "refused") return "Signature refusée";
  if (s === "expired") return "Signature expirée";
  return status;
}

export function signatureStatusShortLabel(status: string | null | undefined): string | null {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "pending") return "Sign. att.";
  if (s === "signed") return "Signé";
  if (s === "refused") return "Sign. refusée";
  if (s === "expired") return "Expiré";
  return status;
}

function parseDateOnly(value: string): Date {
  const d = value.includes("T") ? new Date(value) : new Date(`${value}T12:00:00`);
  d.setHours(0, 0, 0, 0);
  return d;
}

function sortKeyDate(review: AnnualReview): number {
  const raw = review.planned_date ?? review.completed_date ?? review.created_at;
  if (!raw) return 0;
  return parseDateOnly(raw).getTime();
}

export function sortReviewsForDisplay(reviews: AnnualReview[]): AnnualReview[] {
  return [...reviews].sort((a, b) => {
    if (b.year !== a.year) return b.year - a.year;
    return sortKeyDate(b) - sortKeyDate(a);
  });
}

export interface AnnualReviewStatusCounts {
  planifie: number;
  en_attente_acceptation: number;
  accepte: number;
  refuse: number;
  realise: number;
  cloture: number;
  actionable: number;
}

export function countReviewsByStatus(reviews: AnnualReview[]): AnnualReviewStatusCounts {
  const counts: AnnualReviewStatusCounts = {
    planifie: 0,
    en_attente_acceptation: 0,
    accepte: 0,
    refuse: 0,
    realise: 0,
    cloture: 0,
    actionable: 0,
  };
  for (const r of reviews) {
    switch (r.status) {
      case "planifie":
        counts.planifie += 1;
        break;
      case "en_attente_acceptation":
        counts.en_attente_acceptation += 1;
        break;
      case "accepte":
        counts.accepte += 1;
        break;
      case "refuse":
        counts.refuse += 1;
        break;
      case "realise":
        counts.realise += 1;
        break;
      case "cloture":
        counts.cloture += 1;
        break;
      default:
        break;
    }
    if (isActionableAnnualReviewStatus(r.status)) {
      counts.actionable += 1;
    }
  }
  return counts;
}

/** Tous les entretiens nécessitant une action RH, triés par priorité. */
export function sortActionableReviews(reviews: AnnualReview[]): AnnualReview[] {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const actionable = reviews.filter((r) => isActionableAnnualReviewStatus(r.status));

  return [...actionable].sort((a, b) => {
    const da = a.planned_date ? parseDateOnly(a.planned_date) : null;
    const db = b.planned_date ? parseDateOnly(b.planned_date) : null;
    if (da && db) {
      const aOverdue = da < now;
      const bOverdue = db < now;
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
      if (da.getTime() !== db.getTime()) return da.getTime() - db.getTime();
    } else if (da && !db) return -1;
    else if (!da && db) return 1;
    if (b.year !== a.year) return b.year - a.year;
    return sortKeyDate(b) - sortKeyDate(a);
  });
}

/** Entretien prioritaire pour le bandeau synthèse (côté front). */
export function getNextActionableReview(reviews: AnnualReview[]): AnnualReview | null {
  const currentYear = new Date().getFullYear();
  const now = new Date();
  now.setHours(0, 0, 0, 0);

  const actionable = sortActionableReviews(reviews);
  if (actionable.length === 0) {
    const currentYearReviews = reviews
      .filter((r) => r.year === currentYear && r.status !== "cloture")
      .sort((a, b) => sortKeyDate(b) - sortKeyDate(a));
    return currentYearReviews[0] ?? null;
  }

  return actionable[0] ?? null;
}

/** Pastille onglet : entretien actionnable à traiter (échéance passée ou sous 14 jours). */
export function hasAnnualReviewTabAlert(reviews: AnnualReview[]): boolean {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const maxDate = new Date(now);
  maxDate.setDate(maxDate.getDate() + ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS);

  return reviews.some((review) => {
    if (!isActionableAnnualReviewStatus(review.status)) return false;
    if (!review.planned_date) {
      return (
        review.status === "en_attente_acceptation" || review.status === "accepte"
      );
    }
    const planned = parseDateOnly(review.planned_date);
    return planned <= maxDate;
  });
}

export function filterReviewsForDisplay(
  reviews: AnnualReview[],
  options: {
    year: number | "all";
    status: AnnualReviewStatus | "all";
    hideClosed: boolean;
  },
): AnnualReview[] {
  return reviews.filter((r) => {
    if (options.hideClosed && r.status === "cloture") return false;
    if (options.year !== "all" && r.year !== options.year) return false;
    if (options.status !== "all" && r.status !== options.status) return false;
    return true;
  });
}

export function getReviewYearOptions(reviews: AnnualReview[]): number[] {
  const years = new Set(reviews.map((r) => r.year));
  return Array.from(years).sort((a, b) => b - a);
}

/** Entretien actionnable dont la date prévue est dépassée. */
export function isAnnualReviewOverdue(
  review: AnnualReview | AnnualReviewListLike,
): boolean {
  if (!isActionableAnnualReviewStatus(review.status) || !review.planned_date) return false;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return parseDateOnly(review.planned_date) < now;
}

export function countOverdueActionableReviews(
  reviews: (AnnualReview | AnnualReviewListLike)[],
): number {
  return reviews.filter(isAnnualReviewOverdue).length;
}

function listSortKeyDate(item: AnnualReviewListLike): number {
  const raw = item.planned_date ?? item.completed_date ?? item.created_at;
  if (!raw) return 0;
  return parseDateOnly(raw).getTime();
}

/** Tri priorité RH pour la liste consolidée. */
export function sortListItemsForDisplay(items: AnnualReviewListLike[]): AnnualReviewListLike[] {
  const now = new Date();
  now.setHours(0, 0, 0, 0);

  return [...items].sort((a, b) => {
    const aAction = isActionableAnnualReviewStatus(a.status);
    const bAction = isActionableAnnualReviewStatus(b.status);
    if (aAction !== bAction) return aAction ? -1 : 1;

    if (aAction && bAction) {
      const aOver = isAnnualReviewOverdue(a);
      const bOver = isAnnualReviewOverdue(b);
      if (aOver !== bOver) return aOver ? -1 : 1;
      const da = a.planned_date ? parseDateOnly(a.planned_date) : null;
      const db = b.planned_date ? parseDateOnly(b.planned_date) : null;
      if (da && db && da.getTime() !== db.getTime()) return da.getTime() - db.getTime();
      if (da && !db) return -1;
      if (!da && db) return 1;
    }

    if (b.year !== a.year) return b.year - a.year;
    return listSortKeyDate(b) - listSortKeyDate(a);
  });
}

export function countListItemsByStatus(
  items: AnnualReviewListLike[],
): AnnualReviewStatusCounts {
  const counts: AnnualReviewStatusCounts = {
    planifie: 0,
    en_attente_acceptation: 0,
    accepte: 0,
    refuse: 0,
    realise: 0,
    cloture: 0,
    actionable: 0,
  };
  for (const r of items) {
    switch (r.status) {
      case "planifie":
        counts.planifie += 1;
        break;
      case "en_attente_acceptation":
        counts.en_attente_acceptation += 1;
        break;
      case "accepte":
        counts.accepte += 1;
        break;
      case "refuse":
        counts.refuse += 1;
        break;
      case "realise":
        counts.realise += 1;
        break;
      case "cloture":
        counts.cloture += 1;
        break;
      default:
        break;
    }
    if (isActionableAnnualReviewStatus(r.status)) {
      counts.actionable += 1;
    }
  }
  return counts;
}

export function getListItemDateDisplay(item: AnnualReviewListLike): {
  label: string;
  value: string;
} {
  if (item.completed_date) {
    return { label: "Réalisé le", value: formatAnnualReviewDate(item.completed_date) };
  }
  return { label: "Prévu le", value: formatAnnualReviewDate(item.planned_date) };
}

export function listItemExtraMetaLines(item: AnnualReviewListLike): string[] {
  const lines: string[] = [];
  const sig = signatureStatusShortLabel(item.signature_status);
  const acc = employeeAcceptanceShortLabel(item.employee_acceptance_status);
  if (sig) lines.push(sig);
  if (acc) lines.push(acc);
  if (item.status === "refuse" && !acc) lines.push("Refusé");
  return lines;
}

export function employeeAcceptanceShortLabel(
  status: string | null | undefined,
): string | null {
  if (status === "accepte") return "Salarié : accepté";
  if (status === "refuse") return "Salarié : refusé";
  return null;
}

export function getReviewDateDisplay(review: AnnualReview): { label: string; value: string } {
  if (review.completed_date) {
    return { label: "Réalisé le", value: formatAnnualReviewDate(review.completed_date) };
  }
  return { label: "Prévu le", value: formatAnnualReviewDate(review.planned_date) };
}

export function findExistingReviewSameTypeYear(
  reviews: AnnualReview[],
  interviewType: string,
  year: number,
): AnnualReview | undefined {
  return reviews.find((r) => r.interview_type === interviewType && r.year === year);
}

const HISTORICAL_GROUP_BY_YEAR_THRESHOLD = 8;

/** Regroupe l'historique par année si le volume dépasse le seuil. */
export function groupHistoricalReviewsByYear(
  reviews: AnnualReview[],
): { grouped: boolean; sections: { year: number; items: AnnualReview[] }[] } {
  if (reviews.length <= HISTORICAL_GROUP_BY_YEAR_THRESHOLD) {
    return { grouped: false, sections: [{ year: 0, items: reviews }] };
  }
  const byYear = new Map<number, AnnualReview[]>();
  for (const r of reviews) {
    const list = byYear.get(r.year) ?? [];
    list.push(r);
    byYear.set(r.year, list);
  }
  const sections = Array.from(byYear.entries())
    .sort(([a], [b]) => b - a)
    .map(([year, items]) => ({ year, items }));
  return { grouped: true, sections };
}
