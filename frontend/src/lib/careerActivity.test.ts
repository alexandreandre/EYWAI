import { describe, expect, it } from "vitest";

import type { GeneratedDocument } from "@/api/documents";
import type { PromotionListItem } from "@/api/promotions";
import {
  avenantToCareerItem,
  computeCareerKpis,
  groupAvenantsBySession,
  promotionToCareerItem,
  sessionGroupKey,
} from "@/lib/careerActivity";

const samplePromotion: PromotionListItem = {
  id: "promo-1",
  employee_id: "emp-1",
  first_name: "Marie",
  last_name: "Dupont",
  promotion_type: "poste",
  new_job_title: "Chef de projet",
  new_salary: { valeur: 42000, devise: "EUR" },
  new_statut: null,
  effective_date: "2026-06-01",
  status: "draft",
  request_date: "2026-05-01",
  requested_by_name: null,
  approved_by_name: null,
  grant_rh_access: false,
  new_rh_access: null,
  performance_review_id: null,
  created_at: "2026-05-01T10:00:00Z",
};

function makeAvenant(
  id: string,
  createdAt: string,
  employeeId: string,
  employeeName: string,
  dateEffet: string,
  motif: string,
  status = "brouillon",
): GeneratedDocument {
  return {
    id,
    company_id: "co-1",
    employee_id: employeeId,
    document_type: "avenant_salaire",
    category: "avenant",
    template_id: null,
    template_version_id: null,
    is_eywai_template: true,
    file_url: "https://example.com/a.pdf",
    file_name: "avenant.pdf",
    status,
    generation_context: { date_effet: dateEffet, motif },
    generated_by: null,
    created_at: createdAt,
    updated_at: createdAt,
    employee_name: employeeName,
  };
}

describe("promotionToCareerItem", () => {
  it("mappe une promotion avec employé et évolution", () => {
    const item = promotionToCareerItem(samplePromotion);
    expect(item.kind).toBe("promotion");
    expect(item.id).toBe("promo-1");
    expect(item.employees[0].name).toBe("Marie Dupont");
    expect(item.detail).toContain("Chef de projet");
    expect(item.status).toBe("draft");
    expect(item.promotionType).toBe("poste");
  });
});

describe("avenantToCareerItem", () => {
  it("mappe un avenant avec date d'effet du contexte", () => {
    const doc = makeAvenant(
      "doc-1",
      "2026-05-15T14:00:00Z",
      "emp-2",
      "Jean Martin",
      "2026-07-01",
      "Revue annuelle",
    );
    const item = avenantToCareerItem(doc);
    expect(item.kind).toBe("avenant");
    expect(item.date).toBe("2026-07-01");
    expect(item.employees[0].name).toBe("Jean Martin");
    expect(item.status).toBe("brouillon");
  });
});

describe("groupAvenantsBySession", () => {
  it("regroupe les avenants par jour, date d'effet et motif", () => {
    const a1 = makeAvenant(
      "d1",
      "2026-05-20T10:00:00Z",
      "emp-a",
      "Alice",
      "2026-06-01",
      "Campagne 2026",
    );
    const a2 = makeAvenant(
      "d2",
      "2026-05-20T11:00:00Z",
      "emp-b",
      "Bob",
      "2026-06-01",
      "Campagne 2026",
    );
    const a3 = makeAvenant(
      "d3",
      "2026-05-21T10:00:00Z",
      "emp-c",
      "Claire",
      "2026-06-01",
      "Autre",
    );

    expect(sessionGroupKey(a1)).toBe(sessionGroupKey(a2));
    expect(sessionGroupKey(a1)).not.toBe(sessionGroupKey(a3));

    const sessions = groupAvenantsBySession([a1, a2, a3]);
    expect(sessions).toHaveLength(2);
    const big = sessions.find((s) => s.employeeCount === 2);
    expect(big?.documents).toHaveLength(2);
    expect(big?.motif).toBe("Campagne 2026");
  });
});

describe("computeCareerKpis", () => {
  it("calcule promotions année, brouillons et avenants à signer", () => {
    const year = new Date().getFullYear();
    const promoDraft: PromotionListItem = {
      ...samplePromotion,
      id: "p-draft",
      status: "draft",
      effective_date: `${year}-08-01`,
    };
    const promoEffective: PromotionListItem = {
      ...samplePromotion,
      id: "p2",
      status: "effective",
      effective_date: `${year}-03-15`,
    };
    const avenants = [
      makeAvenant("x1", `${year}-01-10T10:00:00Z`, "e1", "A", `${year}-02-01`, "m", "brouillon"),
      makeAvenant("x2", `${year}-01-10T11:00:00Z`, "e2", "B", `${year}-02-01`, "m", "envoye"),
      makeAvenant("x3", `${year}-01-10T12:00:00Z`, "e3", "C", `${year}-02-01`, "m", "signe"),
    ];

    const kpis = computeCareerKpis([promoDraft, promoEffective], avenants);
    expect(kpis.promotionsThisYear).toBe(2);
    expect(kpis.draftPromotions).toBe(1);
    expect(kpis.avenantsToSign).toBe(2);
    expect(kpis.reviewSessions12Months).toBeGreaterThanOrEqual(1);
  });
});
