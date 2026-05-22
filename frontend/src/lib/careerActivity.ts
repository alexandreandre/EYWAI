import type { GeneratedDocument } from "@/api/documents";
import type { PromotionListItem, PromotionType } from "@/api/promotions";

import type {
  CareerActivityFilters,
  CareerActivityItem,
  CareerActivityKpis,
  CareerActivityTab,
  SalaryReviewSession,
} from "@/components/career/types";
import { formatCurrency } from "@/lib/careerFormat";

const PROMOTION_TYPE_LABELS: Record<PromotionType, string> = {
  poste: "Promotion poste",
  salaire: "Promotion salaire",
  statut: "Promotion statut",
  classification: "Promotion classification",
  mixte: "Promotion mixte",
};

function docDateEffet(doc: GeneratedDocument): string | null {
  const ctx = doc.generation_context;
  if (!ctx || typeof ctx !== "object") return null;
  const raw = (ctx as Record<string, unknown>).date_effet;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
}

function docMotif(doc: GeneratedDocument): string | null {
  const ctx = doc.generation_context;
  if (!ctx || typeof ctx !== "object") return null;
  const raw = (ctx as Record<string, unknown>).motif;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
}

function createdDayKey(iso: string): string {
  return iso.slice(0, 10);
}

export function sessionGroupKey(doc: GeneratedDocument): string {
  const day = createdDayKey(doc.created_at);
  const eff = docDateEffet(doc) ?? "";
  const motif = docMotif(doc) ?? "";
  return `${day}|${eff}|${motif}`;
}

export function groupAvenantsBySession(documents: GeneratedDocument[]): SalaryReviewSession[] {
  const groups = new Map<string, GeneratedDocument[]>();

  for (const doc of documents) {
    const key = sessionGroupKey(doc);
    const list = groups.get(key) ?? [];
    list.push(doc);
    groups.set(key, list);
  }

  const sessions: SalaryReviewSession[] = [];

  for (const [key, docs] of groups) {
    const sorted = [...docs].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    const first = sorted[0];
    const createdDay = createdDayKey(first.created_at);
    const effectiveDate = docDateEffet(first);
    const motif = docMotif(first);
    const employeeIds = new Set(
      sorted.map((d) => d.employee_id).filter((id): id is string => Boolean(id)),
    );

    sessions.push({
      id: `session-${key}`,
      createdDay,
      effectiveDate,
      motif,
      documents: sorted,
      employeeCount: employeeIds.size || sorted.length,
    });
  }

  return sessions.sort(
    (a, b) =>
      new Date(b.documents[0].created_at).getTime() -
      new Date(a.documents[0].created_at).getTime(),
  );
}

function getPromotionEvolution(promotion: PromotionListItem): string {
  const parts: string[] = [];
  if (promotion.new_job_title) parts.push(promotion.new_job_title);
  if (promotion.new_salary) parts.push(formatCurrency(promotion.new_salary));
  if (promotion.new_statut) parts.push(promotion.new_statut);
  return parts.length > 0 ? parts.join(" • ") : "—";
}

export function promotionToCareerItem(promotion: PromotionListItem): CareerActivityItem {
  const name = `${promotion.first_name} ${promotion.last_name}`.trim();
  return {
    id: promotion.id,
    kind: "promotion",
    date: promotion.effective_date,
    title: PROMOTION_TYPE_LABELS[promotion.promotion_type] ?? "Promotion",
    detail: getPromotionEvolution(promotion),
    employees: [{ id: promotion.employee_id, name }],
    promotionType: promotion.promotion_type,
    status: promotion.status,
    raw: promotion,
  };
}

export function avenantToCareerItem(doc: GeneratedDocument): CareerActivityItem {
  const eff = docDateEffet(doc);
  return {
    id: doc.id,
    kind: "avenant",
    date: eff ?? doc.created_at,
    title: "Avenant salaire",
    detail: doc.employee_name ?? "—",
    employees: doc.employee_id
      ? [{ id: doc.employee_id, name: doc.employee_name ?? "Salarié" }]
      : [],
    status: doc.status,
    raw: doc,
  };
}

export function sessionToCareerItem(session: SalaryReviewSession): CareerActivityItem {
  const monthYear = session.createdDay
    ? new Date(`${session.createdDay}T12:00:00`).toLocaleDateString("fr-FR", {
        month: "long",
        year: "numeric",
      })
    : "";
  const motifPart = session.motif ? ` — ${session.motif}` : "";
  const countLabel =
    session.employeeCount === 1
      ? "1 salarié"
      : `${session.employeeCount} salariés`;

  return {
    id: session.id,
    kind: "salary_review_session",
    date: session.documents[0]?.created_at ?? session.createdDay,
    title: `Augmentation collective${monthYear ? ` — ${monthYear}` : ""}`,
    detail: `${countLabel}${motifPart}`,
    employees: session.documents
      .filter((d) => d.employee_id)
      .map((d) => ({
        id: d.employee_id as string,
        name: d.employee_name ?? "Salarié",
      })),
    status: undefined,
    raw: session,
  };
}

export function buildCareerActivityItems(
  promotions: PromotionListItem[],
  avenants: GeneratedDocument[],
): CareerActivityItem[] {
  const sessions = groupAvenantsBySession(avenants);
  return [
    ...promotions.map(promotionToCareerItem),
    ...sessions.map(sessionToCareerItem),
    ...avenants.map(avenantToCareerItem),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

export function filterItemsByTab(
  items: CareerActivityItem[],
  tab: CareerActivityTab,
): CareerActivityItem[] {
  if (tab === "all") {
    return items.filter((i) => i.kind !== "avenant");
  }
  if (tab === "promotion") {
    return items.filter((i) => i.kind === "promotion");
  }
  if (tab === "salary_review_session") {
    return items.filter((i) => i.kind === "salary_review_session");
  }
  return items.filter((i) => i.kind === "avenant");
}

export function applyClientFilters(
  items: CareerActivityItem[],
  filters: Pick<CareerActivityFilters, "search" | "year" | "status" | "type">,
): CareerActivityItem[] {
  let result = items;

  if (filters.year !== "all") {
    const y = filters.year;
    result = result.filter((item) => {
      const d = new Date(item.date);
      return !Number.isNaN(d.getTime()) && d.getFullYear() === y;
    });
  }

  if (filters.status !== "all") {
    result = result.filter((item) => {
      if (item.kind === "promotion") return item.status === filters.status;
      if (item.kind === "avenant") return item.status === filters.status;
      return true;
    });
  }

  if (filters.type !== "all") {
    result = result.filter(
      (item) => item.kind === "promotion" && item.promotionType === filters.type,
    );
  }

  const term = filters.search.trim().toLowerCase();
  if (term) {
    result = result.filter((item) => {
      const haystack = [
        item.title,
        item.detail,
        ...item.employees.map((e) => e.name),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }

  return result;
}

export function computeCareerKpis(
  promotions: PromotionListItem[],
  avenants: GeneratedDocument[],
): CareerActivityKpis {
  const now = new Date();
  const currentYear = now.getFullYear();
  const twelveMonthsAgo = new Date(now);
  twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);

  const sessions = groupAvenantsBySession(avenants);

  return {
    promotionsThisYear: promotions.filter((p) => {
      const d = new Date(p.effective_date);
      return !Number.isNaN(d.getTime()) && d.getFullYear() === currentYear;
    }).length,
    draftPromotions: promotions.filter((p) => p.status === "draft").length,
    reviewSessions12Months: sessions.filter((s) => {
      const d = new Date(s.documents[0]?.created_at ?? s.createdDay);
      return !Number.isNaN(d.getTime()) && d >= twelveMonthsAgo;
    }).length,
    avenantsToSign: avenants.filter((d) => d.status === "brouillon" || d.status === "envoye")
      .length,
  };
}

export function countItemsByTab(
  items: CareerActivityItem[],
  filters: Pick<CareerActivityFilters, "search" | "year" | "status" | "type">,
): Record<CareerActivityTab, number> {
  const filtered = applyClientFilters(items, filters);
  return {
    all: filterItemsByTab(filtered, "all").length,
    promotion: filterItemsByTab(filtered, "promotion").length,
    salary_review_session: filterItemsByTab(filtered, "salary_review_session").length,
    avenant: filterItemsByTab(filtered, "avenant").length,
  };
}

export const AVENANTS_QUERY_KEY = ["documents", "avenant_salaire"] as const;
