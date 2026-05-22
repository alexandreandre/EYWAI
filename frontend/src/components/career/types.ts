import type { GeneratedDocument } from "@/api/documents";
import type { PromotionListItem, PromotionType } from "@/api/promotions";

export type CareerActivityKind = "promotion" | "salary_review_session" | "avenant";

export type CareerActivityTab = "all" | "promotion" | "salary_review_session" | "avenant";

export type SalaryReviewSession = {
  id: string;
  createdDay: string;
  effectiveDate: string | null;
  motif: string | null;
  documents: GeneratedDocument[];
  employeeCount: number;
};

export type CareerActivityEmployee = {
  id: string;
  name: string;
};

export type CareerActivityItem = {
  id: string;
  kind: CareerActivityKind;
  date: string;
  title: string;
  detail: string;
  employees: CareerActivityEmployee[];
  promotionType?: PromotionType | null;
  status?: string;
  raw: PromotionListItem | GeneratedDocument | SalaryReviewSession;
};

export type CareerActivityKpis = {
  promotionsThisYear: number;
  draftPromotions: number;
  reviewSessions12Months: number;
  avenantsToSign: number;
};

export type CareerActivityFilters = {
  search: string;
  year: number | "all";
  status: string;
  type: string;
  tab: CareerActivityTab;
};
