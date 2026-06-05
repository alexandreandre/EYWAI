import { describe, expect, it } from "vitest";

import type { AnalyticsGestionResponse } from "@/api/analyticsGestion";
import { getAnalyticsGestionWorkbookSheetNames } from "@/lib/exportAnalyticsGestionXlsx";

const sampleData: AnalyticsGestionResponse = {
  period: {
    period_start: "2026-01-01",
    period_end: "2026-01-31",
    year: 2026,
    calendar_year: 2026,
    calendar_month: 1,
  },
  entretiens: {
    actionable_count: 3,
    overdue_count: 1,
    upcoming_14d_count: 2,
    closure_rate_pct: 42.5,
    by_status: { planifie: 2, cloture: 5 },
  },
  conformite: {
    certifications_expired: 1,
    certifications_expiring: 2,
    legal_obligations_overdue: 0,
    legal_obligations_due_soon: 1,
    legal_obligations_up_to_date: 10,
  },
  formation: {
    budget_consumption_pct: 55,
    budget_alert_level: "warning",
    budget_consumed: 5500,
    budget_envelope: 10000,
    training_consumed_year: 5500,
    evaluations_count: 2,
    evaluations_average: 4.2,
  },
  calendriers: {
    total: 20,
    saisis: 15,
    a_saisir: 3,
    avec_ecart: 2,
    conflits_absences: 1,
    progress_percent: 75,
  },
  medical: {
    overdue_count: 1,
    due_within_30_count: 2,
    active_total: 18,
    completed_this_month: 4,
    compliance_rate_pct: 88.5,
    employees_overdue_top: [
      {
        employee_id: "e1",
        employee_name: "Dupont Jean",
        obligations_overdue: 2,
        most_urgent_due_date: "2026-02-01",
      },
    ],
  },
  objectives: { achievement_rate_pct: 61 },
  carriere: {
    total_promotions: 2,
    approval_rate_pct: 100,
    average_salary_increase_pct: 3.5,
    promotions_by_month: { "2026-01": 1, "2026-03": 1 },
    promotions_draft_count: 0,
    avenants_pending_signature: 1,
  },
  cse: {
    mandate_alerts_count: 1,
    election_alerts_count: 0,
    election_critical_count: 0,
    delegation_over_quota_count: 0,
    delegation_consumed_hours: 12,
    delegation_quota_hours: 20,
    upcoming_meetings: [
      {
        id: "m1",
        title: "Réunion ordinaire",
        meeting_date: "2026-02-15",
        meeting_time: "14:00",
      },
    ],
  },
};

describe("exportAnalyticsGestionXlsx", () => {
  it("produit un classeur multi-feuilles structuré", async () => {
    expect(
      await getAnalyticsGestionWorkbookSheetNames("ACME", "Janvier 2026", sampleData),
    ).toEqual([
      "Synthèse",
      "Entretiens",
      "Formation",
      "Calendriers",
      "Médical",
      "Carrière",
      "CSE",
    ]);
  });
});
