import { describe, expect, it } from "vitest";

import type { CompanyStats } from "@/api/companyGroups";
import { computeCompanyKpis } from "@/lib/groupConsolidatedKpis";
import {
  getGroupDashboardWorkbookSheetNames,
  getGroupDashboardTableWorkbookSheetNames,
  getSyntheseChargeRateDisplayValue,
} from "@/lib/exportGroupDashboardXlsx";

const sampleCompanies: CompanyStats[] = [
  {
    company_id: "c1",
    company_name: "ACME Paris",
    siret: "12345678901234",
    total_employee_count: 20,
    employee_count: 18,
    rh_count: 2,
    payslip_count: 20,
    gross_salary: 85000,
    net_salary: 62000,
    employer_charges: 34000,
  },
  {
    company_id: "c2",
    company_name: "ACME Lyon",
    siret: "98765432109876",
    total_employee_count: 12,
    employee_count: 11,
    rh_count: 1,
    payslip_count: 12,
    gross_salary: 48000,
    net_salary: 35000,
    employer_charges: 19200,
  },
];

const kpiRows = sampleCompanies.map((c) => computeCompanyKpis(c));

const basePayload = {
  groupName: "Groupe ACME",
  siren: "123456789",
  periodLabel: "Janvier 2026",
  periodExportKey: "2026-01",
  compareTo: "previous_month" as const,
  companies: sampleCompanies,
  totals: {
    total_employees: 32,
    total_employees_excluding_rh: 29,
    total_rh: 3,
    total_payslip_count: 32,
    total_gross_salary: 133000,
    total_net_salary: 97000,
    total_employer_charges: 53200,
    average_gross_per_company: 66500,
    average_employees_per_company: 16,
    company_count: 2,
  },
  chargeRate: 40,
  avgGrossPerEmployee: 4156.25,
  totalEmployerCostValue: 186200,
  kpiRows,
  kpiDeltas: { employees: 3.2, employerCost: 1.5, gross: 2.1, charges: 0.8 },
  comparison: {
    totals: {
      total_employees: 30,
      total_employees_excluding_rh: 27,
      total_rh: 3,
      total_payslip_count: 30,
      total_gross_salary: 120000,
      total_net_salary: 88000,
      total_employer_charges: 48000,
      average_gross_per_company: 60000,
      average_employees_per_company: 15,
    },
    by_company: sampleCompanies.map((c) => ({
      ...c,
      gross_salary: c.gross_salary * 0.95,
      net_salary: c.net_salary * 0.95,
      employer_charges: c.employer_charges * 0.95,
    })),
  },
  distributions: {
    charge: { min: 38, max: 42, avg: 40, median: 40, spread: 4 },
    cost: { min: 5000, max: 5950, avg: 5475, median: 5475, spread: 950 },
    rh: { min: 8.3, max: 10, avg: 9.15, median: 9.15, spread: 1.7 },
    salary: { min: 4000, max: 4250, avg: 4125, median: 4125, spread: 250 },
  },
  evolution: [
    {
      company_id: "c1",
      company_name: "ACME Paris",
      year: 2026,
      month: 1,
      total_gross: 85000,
      total_net: 62000,
      total_employer_charges: 34000,
      employee_count: 20,
    },
  ],
};

describe("exportGroupDashboardXlsx", () => {
  it("produit un classeur multi-feuilles avec détail par entreprise", async () => {
    expect(await getGroupDashboardWorkbookSheetNames(basePayload)).toEqual([
      "Synthèse",
      "Détail complet",
      "Fiches entreprises",
      "Comparatif N-1",
      "Répartition",
      "Statistiques KPI",
      "Évolution mensuelle",
    ]);
  });

  it("formate les pourcentages en points (45,2 et non 0,452)", async () => {
    const stored = await getSyntheseChargeRateDisplayValue({
      ...basePayload,
      chargeRate: 45.2,
    });
    expect(stored).toBeCloseTo(45.2, 1);
  });

  it("n'inclut pas la feuille comparatif sans comparaison", async () => {
    expect(
      await getGroupDashboardWorkbookSheetNames({
        ...basePayload,
        compareTo: "off",
        comparison: undefined,
        kpiDeltas: null,
      }),
    ).toEqual([
      "Synthèse",
      "Détail complet",
      "Fiches entreprises",
      "Répartition",
      "Statistiques KPI",
      "Évolution mensuelle",
    ]);
  });
});

describe("exportGroupDashboardTableXlsx", () => {
  const tablePayload = {
    groupName: "Groupe ACME",
    periodLabel: "Janvier 2026",
    periodExportKey: "2026-01",
    compareTo: "previous_month" as const,
    companies: sampleCompanies,
    totals: basePayload.totals,
    totalEmployerCostValue: basePayload.totalEmployerCostValue,
    chargeRate: basePayload.chargeRate,
    comparison: basePayload.comparison,
  };

  it("produit une feuille Tableau des charges", async () => {
    expect(await getGroupDashboardTableWorkbookSheetNames(tablePayload)).toEqual([
      "Tableau des charges",
    ]);
  });

  it("n'inclut pas la colonne évolution sans comparaison", async () => {
    const { buildGroupDashboardTableWorkbook } = await import("@/lib/exportGroupDashboardXlsx");
    const wb = await buildGroupDashboardTableWorkbook({
      ...tablePayload,
      compareTo: "off",
      comparison: undefined,
    });
    const ws = wb.getWorksheet("Tableau des charges");
    expect(ws).toBeDefined();
    const headerRow = ws!.getRow(4);
    expect(headerRow.getCell(1).value).toBe("Entreprise");
    expect(headerRow.getCell(10).value).toBe("Taux charges");
    expect(headerRow.getCell(11).value).not.toBe("Évol. masse brute");
    const totalRow = ws!.getRow(4 + sampleCompanies.length + 1);
    expect(totalRow.getCell(1).value).toBe("TOTAL");
  });
});
