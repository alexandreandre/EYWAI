import { describe, expect, it } from "vitest";
import {
  chargeRateColorClass,
  chargeRatePercent,
  computeCompanyKpis,
  computeDistribution,
  percentDelta,
  totalEmployerCost,
} from "./groupConsolidatedKpis";

const sampleCompany = {
  company_id: "c1",
  company_name: "Acme",
  total_employee_count: 10,
  employee_count: 8,
  rh_count: 2,
  payslip_count: 10,
  gross_salary: 100_000,
  net_salary: 75_000,
  employer_charges: 42_000,
};

describe("groupConsolidatedKpis", () => {
  it("calcule le coût employeur total", () => {
    expect(totalEmployerCost(sampleCompany)).toBe(142_000);
  });

  it("calcule le taux de charges", () => {
    expect(chargeRatePercent(sampleCompany)).toBeCloseTo(42, 5);
  });

  it("calcule les KPI par entreprise", () => {
    const kpis = computeCompanyKpis(sampleCompany);
    expect(kpis.chargeRate).toBeCloseTo(42, 5);
    expect(kpis.netRetentionRate).toBeCloseTo(75, 5);
    expect(kpis.totalCostPerEmployee).toBeCloseTo(14_200, 5);
    expect(kpis.rhRatio).toBeCloseTo(20, 5);
  });

  it("calcule la distribution", () => {
    const dist = computeDistribution([10, 20, 30, 40]);
    expect(dist.min).toBe(10);
    expect(dist.max).toBe(40);
    expect(dist.avg).toBe(25);
    expect(dist.median).toBe(25);
    expect(dist.spread).toBe(30);
  });

  it("calcule le delta en pourcentage", () => {
    expect(percentDelta(110, 100)).toBeCloseTo(10, 5);
    expect(percentDelta(0, 0)).toBe(0);
    expect(percentDelta(100, 0)).toBeNull();
  });

  it("applique les classes de couleur selon le taux de charges", () => {
    expect(chargeRateColorClass(50)).toContain("red");
    expect(chargeRateColorClass(42)).toContain("amber");
    expect(chargeRateColorClass(35)).toContain("green");
  });
});
