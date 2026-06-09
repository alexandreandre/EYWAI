import type ExcelJS from "exceljs";

import type {
  CompareToMode,
  CompanyStats,
  ConsolidatedStats,
  EvolutionDataPoint,
} from "@/api/companyGroups";
import { downloadBlob } from "@/lib/downloadBlob";
import {
  CHARGE_RATE_CRITICAL,
  CHARGE_RATE_WARNING,
  type CompanyKpiRow,
  type DistributionStats,
  type ConsolidatedTotalsLike,
  computeCompanyKpis,
  percentDelta,
  totalEmployerCost,
} from "@/lib/groupConsolidatedKpis";
import { formatMonthLabel } from "@/lib/groupConsolidatedPeriod";
import {
  applyStatusCell,
  type CellValue,
  createReportSheet,
  FMT,
  loadExcelJS,
  num,
  SheetBuilder,
  type StatusKind,
  text as t,
} from "@/lib/excelReport";

const COMPARE_LABELS: Record<CompareToMode, string> = {
  off: "Aucune comparaison",
  previous_month: "Mois précédent",
  previous_year: "Année précédente (même période)",
  ytd_previous_year: "YTD année N-1",
};

export interface GroupDashboardExportPayload {
  groupName: string;
  siren?: string | null;
  periodLabel: string;
  periodExportKey: string;
  compareTo: CompareToMode;
  companies: CompanyStats[];
  totals: ConsolidatedTotalsLike & { company_count: number };
  chargeRate: number;
  avgGrossPerEmployee: number;
  totalEmployerCostValue: number;
  kpiRows: CompanyKpiRow[];
  kpiDeltas?: {
    employees: number | null;
    employerCost: number | null;
    gross: number | null;
    charges: number | null;
  } | null;
  comparison?: ConsolidatedStats["comparison"];
  distributions: {
    charge: DistributionStats;
    cost: DistributionStats;
    rh: DistributionStats;
    salary: DistributionStats;
  };
  evolution: EvolutionDataPoint[];
  generatedAt?: string;
}

/** Taux en points (ex. 45,2 pour 45,2 %) — FMT.PCT ajoute le symbole % sans multiplier. */
function pctRate(value: number, fmt: string = FMT.PCT): CellValue {
  return num(value, fmt);
}

/** Part en fraction 0–1 (ex. 0,25 → 25 %). */
function pctShare(fraction: number): CellValue {
  return num(fraction * 100, FMT.PCT);
}

function statusChargeRate(rate: number): StatusKind {
  if (rate <= CHARGE_RATE_WARNING) return "good";
  if (rate <= CHARGE_RATE_CRITICAL) return "warn";
  return "bad";
}

function statusDelta(delta: number | null | undefined, worseIfPositive: boolean): StatusKind | undefined {
  if (delta == null) return undefined;
  const abs = Math.abs(delta);
  if (abs < 2) return "good";
  const worsening = worseIfPositive ? delta > 0 : delta < 0;
  if (worsening) return abs >= 10 ? "bad" : "warn";
  return "good";
}

function deltaText(delta: number | null | undefined): CellValue {
  if (delta == null) return t("—");
  const sign = delta >= 0 ? "+" : "";
  return t(`${sign}${delta.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`);
}

function comparisonCompany(
  comparison: ConsolidatedStats["comparison"],
  companyId: string,
): CompanyStats | undefined {
  return comparison?.by_company?.find((c) => c.company_id === companyId);
}

function aggregateEvolutionMonthly(
  points: EvolutionDataPoint[],
): Array<{
  monthKey: string;
  monthLabel: string;
  gross: number;
  charges: number;
  total: number;
  employees: number;
}> {
  const byMonth = new Map<
    string,
    { monthKey: string; monthLabel: string; gross: number; charges: number; employees: number }
  >();

  for (const point of points) {
    const monthKey = `${point.year}-${String(point.month).padStart(2, "0")}`;
    const monthLabel = `${formatMonthLabel(point.month).substring(0, 3)} ${point.year}`;
    const existing = byMonth.get(monthKey);
    if (existing) {
      existing.gross += point.total_gross;
      existing.charges += point.total_employer_charges;
      existing.employees += point.employee_count;
    } else {
      byMonth.set(monthKey, {
        monthKey,
        monthLabel,
        gross: point.total_gross,
        charges: point.total_employer_charges,
        employees: point.employee_count,
      });
    }
  }

  return Array.from(byMonth.values())
    .sort((a, b) => a.monthKey.localeCompare(b.monthKey))
    .map((row) => ({ ...row, total: row.gross + row.charges }));
}

function buildSyntheseSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Synthèse", [24, 56, 22, 22]);
  const b = new SheetBuilder(ws, "D");
  const generatedAt = payload.generatedAt
    ? new Date(payload.generatedAt).toLocaleString("fr-FR")
    : new Date().toLocaleString("fr-FR");

  const subtitleParts = [
    payload.groupName,
    payload.siren ? `SIREN ${payload.siren}` : null,
    `Période : ${payload.periodLabel}`,
    `${payload.totals.company_count} entreprise${payload.totals.company_count > 1 ? "s" : ""}`,
    `Comparaison : ${COMPARE_LABELS[payload.compareTo]}`,
    `Généré le ${generatedAt}`,
  ].filter(Boolean);

  b.titleBand("Vue consolidée groupe — Pilotage paie", subtitleParts.join("  ·  "));

  b.sectionHeader("Indicateurs consolidés du groupe");
  b.synthesisTableHeader(["Domaine", "Indicateur", "Valeur", "Statut"]);

  const netRetention =
    payload.totals.total_gross_salary > 0
      ? (payload.totals.total_net_salary / payload.totals.total_gross_salary) * 100
      : 0;
  const rhRatio =
    payload.totals.total_employees > 0
      ? (payload.totals.total_rh / payload.totals.total_employees) * 100
      : 0;

  const consolidatedRows: {
    domaine: string;
    indicateur: string;
    value: CellValue;
    status?: StatusKind;
  }[] = [
    {
      domaine: "Effectifs",
      indicateur: "Total employés (dont RH)",
      value: t(
        `${payload.totals.total_employees.toLocaleString("fr-FR")} (${payload.totals.total_employees_excluding_rh.toLocaleString("fr-FR")} hors-RH · ${payload.totals.total_rh.toLocaleString("fr-FR")} RH)`,
      ),
      status: statusDelta(payload.kpiDeltas?.employees, false),
    },
    {
      domaine: "Effectifs",
      indicateur: "Bulletins de paie",
      value: num(payload.totals.total_payslip_count, FMT.INT),
    },
    {
      domaine: "Masse salariale",
      indicateur: "Masse salariale brute",
      value: num(payload.totals.total_gross_salary, FMT.EUR),
      status: statusDelta(payload.kpiDeltas?.gross, true),
    },
    {
      domaine: "Masse salariale",
      indicateur: "Masse salariale nette",
      value: num(payload.totals.total_net_salary, FMT.EUR),
    },
    {
      domaine: "Masse salariale",
      indicateur: "Taux de rétention nette (net / brut)",
      value: pctRate(netRetention),
    },
    {
      domaine: "Charges",
      indicateur: "Charges patronales",
      value: num(payload.totals.total_employer_charges, FMT.EUR),
      status: statusDelta(payload.kpiDeltas?.charges, true),
    },
    {
      domaine: "Charges",
      indicateur: "Taux de charges (charges / brut)",
      value: pctRate(payload.chargeRate),
      status: statusChargeRate(payload.chargeRate),
    },
    {
      domaine: "Coût employeur",
      indicateur: "Coût employeur total (brut + charges)",
      value: num(payload.totalEmployerCostValue, FMT.EUR),
      status: statusDelta(payload.kpiDeltas?.employerCost, true),
    },
    {
      domaine: "Coût employeur",
      indicateur: "Masse brute moyenne par employé",
      value: num(payload.avgGrossPerEmployee, FMT.EUR),
    },
    {
      domaine: "Structure RH",
      indicateur: "Ratio RH (RH / effectif total)",
      value: pctRate(rhRatio),
    },
    {
      domaine: "Structure RH",
      indicateur: "Masse brute moyenne par entreprise",
      value: num(payload.totals.average_gross_per_company, FMT.EUR),
    },
    {
      domaine: "Structure RH",
      indicateur: "Effectif moyen par entreprise",
      value: num(payload.totals.average_employees_per_company, FMT.DEC1),
    },
  ];

  for (const row of consolidatedRows) {
    b.synthesisTableRow(row.domaine, row.indicateur, row.value, row.status);
  }

  if (payload.kpiDeltas) {
    b.blank(4);
    b.sectionHeader("Évolution groupe vs période de comparaison");
    b.tableHeader(["Indicateur", "Variation"]);
    b.tableRow([t("Effectifs"), deltaText(payload.kpiDeltas.employees)], 0);
    b.tableRow([t("Coût employeur total"), deltaText(payload.kpiDeltas.employerCost)], 1);
    b.tableRow([t("Masse salariale brute"), deltaText(payload.kpiDeltas.gross)], 2);
    b.tableRow([t("Charges patronales"), deltaText(payload.kpiDeltas.charges)], 3);
  }

  b.blank(4);
  b.sectionHeader("Récapitulatif par entité du groupe");
  b.tableHeader([
    "Entreprise",
    "Effectifs",
    "Bulletins",
    "Masse brute",
    "Coût employeur",
    "Taux charges",
    "Part masse brute",
  ]);

  for (const company of payload.companies) {
    const k = computeCompanyKpis(company);
    const grossShare =
      payload.totals.total_gross_salary > 0
        ? company.gross_salary / payload.totals.total_gross_salary
        : 0;
    b.tableRow(
      [
        t(company.company_name),
        num(company.total_employee_count, FMT.INT),
        num(company.payslip_count, FMT.INT),
        num(company.gross_salary, FMT.EUR),
        num(k.totalEmployerCost, FMT.EUR),
        pctRate(k.chargeRate),
        pctShare(grossShare),
      ],
      0,
    );
  }

  b.blank(4);
  b.note(
    `Seuils taux de charges : OK ≤ ${CHARGE_RATE_WARNING} % · à surveiller ≤ ${CHARGE_RATE_CRITICAL} % · critique > ${CHARGE_RATE_CRITICAL} %.`,
  );
  b.note(
    "Montants basés sur les bulletins de paie validés sur la période sélectionnée. Voir les feuilles « Détail complet » et « Fiches entreprises » pour le détail par entité.",
  );

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

function buildDetailCompletSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const hasComparison = payload.compareTo !== "off" && !!payload.comparison?.by_company?.length;
  const ws = createReportSheet(
    wb,
    "Détail complet",
    [26, 15, 9, 7, 9, 10, 13, 13, 13, 13, 11, 11, 11, 12, 12, 12, 10, 12, 11, 11, 11],
  );
  const b = new SheetBuilder(ws, "U");
  b.titleBand(
    "Détail complet par entreprise",
    `${payload.groupName}  ·  ${payload.periodLabel}  ·  Tous les indicateurs paie & effectifs`,
  );

  const headers = [
    "Entreprise",
    "SIRET",
    "Emp. hors-RH",
    "RH",
    "Total emp.",
    "Bulletins",
    "Masse brute",
    "Masse nette",
    "Charges patron.",
    "Coût employeur",
    "Taux charges",
    "Rétention nette",
    "Coût / emp.",
    "Masse / emp.",
    "Charges / emp.",
    "Ratio RH",
    "Coût / bulletin",
    "Part effectifs",
    "Part masse brute",
    "Part coût employ.",
    ...(hasComparison
      ? ["Évol. effectifs", "Évol. masse brute", "Évol. charges", "Évol. coût employ."]
      : []),
  ];
  b.tableHeader(headers);

  for (const company of payload.companies) {
    const k = computeCompanyKpis(company);
    const prev = hasComparison
      ? comparisonCompany(payload.comparison, company.company_id)
      : undefined;

    const cells: CellValue[] = [
      t(company.company_name),
      t(company.siret ?? "—"),
      num(company.employee_count, FMT.INT),
      num(company.rh_count, FMT.INT),
      num(company.total_employee_count, FMT.INT),
      num(company.payslip_count, FMT.INT),
      num(company.gross_salary, FMT.EUR),
      num(company.net_salary, FMT.EUR),
      num(company.employer_charges, FMT.EUR),
      num(k.totalEmployerCost, FMT.EUR),
      pctRate(k.chargeRate),
      pctRate(k.netRetentionRate),
      num(k.totalCostPerEmployee, FMT.EUR),
      num(k.grossPerEmployee, FMT.EUR),
      num(k.chargesPerEmployee, FMT.EUR),
      pctRate(k.rhRatio),
      num(k.costPerPayslip, FMT.EUR),
      pctShare(
        payload.totals.total_employees > 0
          ? company.total_employee_count / payload.totals.total_employees
          : 0,
      ),
      pctShare(
        payload.totals.total_gross_salary > 0
          ? company.gross_salary / payload.totals.total_gross_salary
          : 0,
      ),
      pctShare(
        payload.totalEmployerCostValue > 0
          ? k.totalEmployerCost / payload.totalEmployerCostValue
          : 0,
      ),
    ];

    if (hasComparison && prev) {
      cells.push(
        deltaText(percentDelta(company.total_employee_count, prev.total_employee_count)),
        deltaText(percentDelta(company.gross_salary, prev.gross_salary)),
        deltaText(percentDelta(company.employer_charges, prev.employer_charges)),
        deltaText(
          percentDelta(k.totalEmployerCost, totalEmployerCost(prev)),
        ),
      );
    } else if (hasComparison) {
      cells.push(t("—"), t("—"), t("—"), t("—"));
    }

    b.tableRow(cells, 0);
  }

  const totalCells: CellValue[] = [
    t("TOTAL GROUPE"),
    t("—"),
    num(payload.totals.total_employees_excluding_rh, FMT.INT),
    num(payload.totals.total_rh, FMT.INT),
    num(payload.totals.total_employees, FMT.INT),
    num(payload.totals.total_payslip_count, FMT.INT),
    num(payload.totals.total_gross_salary, FMT.EUR),
    num(payload.totals.total_net_salary, FMT.EUR),
    num(payload.totals.total_employer_charges, FMT.EUR),
    num(payload.totalEmployerCostValue, FMT.EUR),
    pctRate(payload.chargeRate),
    pctRate(netRetentionGroup(payload.totals)),
    num(
      payload.totals.total_employees > 0
        ? payload.totalEmployerCostValue / payload.totals.total_employees
        : 0,
      FMT.EUR,
    ),
    num(payload.avgGrossPerEmployee, FMT.EUR),
    num(
      payload.totals.total_employees > 0
        ? payload.totals.total_employer_charges / payload.totals.total_employees
        : 0,
      FMT.EUR,
    ),
    pctRate(
      payload.totals.total_employees > 0
        ? (payload.totals.total_rh / payload.totals.total_employees) * 100
        : 0,
    ),
    num(
      payload.totals.total_payslip_count > 0
        ? payload.totalEmployerCostValue / payload.totals.total_payslip_count
        : 0,
      FMT.EUR,
    ),
    pctShare(1),
    pctShare(1),
    pctShare(1),
  ];
  if (hasComparison) {
    totalCells.push(t("—"), t("—"), t("—"), t("—"));
  }
  b.tableRow(totalCells, payload.companies.length, { bold: true });

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

function netRetentionGroup(totals: ConsolidatedTotalsLike): number {
  return totals.total_gross_salary > 0
    ? (totals.total_net_salary / totals.total_gross_salary) * 100
    : 0;
}

function buildFichesEntreprisesSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Fiches entreprises", [32, 22, 16]);
  const b = new SheetBuilder(ws, "C");
  b.titleBand(
    "Fiches détaillées par entreprise",
    `${payload.groupName}  ·  ${payload.periodLabel}  ·  ${payload.companies.length} entité${payload.companies.length > 1 ? "s" : ""}`,
  );

  const hasComparison = payload.compareTo !== "off" && !!payload.comparison?.by_company?.length;

  for (let i = 0; i < payload.companies.length; i += 1) {
    const company = payload.companies[i];
    const k = computeCompanyKpis(company);
    const prev = hasComparison
      ? comparisonCompany(payload.comparison, company.company_id)
      : undefined;

    b.sectionHeader(
      `${company.company_name}${company.siret ? `  ·  SIRET ${company.siret}` : ""}`,
    );

    b.kpi("Effectif total (hors-RH + RH)", t(`${company.total_employee_count} (${company.employee_count} + ${company.rh_count} RH)`));
    b.kpi("Bulletins de paie", num(company.payslip_count, FMT.INT));
    b.kpi("Masse salariale brute", num(company.gross_salary, FMT.EUR));
    b.kpi("Masse salariale nette", num(company.net_salary, FMT.EUR));
    b.kpi("Charges patronales", num(company.employer_charges, FMT.EUR));
    b.kpi("Coût employeur total", num(k.totalEmployerCost, FMT.EUR));

    const chargeStatusRow = b.currentRow;
    b.kpi("Taux de charges", pctRate(k.chargeRate));
    applyStatusCell(ws.getRow(chargeStatusRow).getCell(3), statusChargeRate(k.chargeRate));

    b.kpi("Rétention nette (net / brut)", pctRate(k.netRetentionRate));
    b.kpi("Coût total par employé", num(k.totalCostPerEmployee, FMT.EUR));
    b.kpi("Masse brute par employé", num(k.grossPerEmployee, FMT.EUR));
    b.kpi("Charges par employé", num(k.chargesPerEmployee, FMT.EUR));
    b.kpi("Ratio RH", pctRate(k.rhRatio));
    b.kpi("Coût par bulletin", num(k.costPerPayslip, FMT.EUR));

    b.kpi(
      "Part dans le groupe — effectifs",
      pctShare(
        payload.totals.total_employees > 0
          ? company.total_employee_count / payload.totals.total_employees
          : 0,
      ),
    );
    b.kpi(
      "Part dans le groupe — masse brute",
      pctShare(
        payload.totals.total_gross_salary > 0
          ? company.gross_salary / payload.totals.total_gross_salary
          : 0,
      ),
    );
    b.kpi(
      "Part dans le groupe — coût employeur",
      pctShare(
        payload.totalEmployerCostValue > 0
          ? k.totalEmployerCost / payload.totalEmployerCostValue
          : 0,
      ),
    );

    if (prev) {
      b.blank(2);
      b.sectionHeader("Comparaison vs période précédente");
      b.kpi(
        "Variation effectifs",
        deltaText(percentDelta(company.total_employee_count, prev.total_employee_count)),
      );
      b.kpi(
        "Variation masse brute",
        deltaText(percentDelta(company.gross_salary, prev.gross_salary)),
      );
      b.kpi(
        "Variation charges",
        deltaText(percentDelta(company.employer_charges, prev.employer_charges)),
      );
      b.kpi(
        "Variation coût employeur",
        deltaText(percentDelta(k.totalEmployerCost, totalEmployerCost(prev))),
      );
    }

    if (i < payload.companies.length - 1) {
      b.blank(6);
    }
  }

  ws.views = [{ state: "frozen", ySplit: 2, showGridLines: true }];
}

function buildComparatifSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Comparatif N-1", [26, 14, 14, 12]);
  const b = new SheetBuilder(ws, "D");
  b.titleBand(
    "Comparatif période courante vs référence",
    `${payload.groupName}  ·  ${payload.periodLabel}  ·  Référence : ${COMPARE_LABELS[payload.compareTo]}`,
  );

  if (!payload.comparison?.by_company?.length) {
    b.note("Aucune comparaison activée pour cet export.");
    return;
  }

  b.tableHeader(["Entreprise", "Indicateur", "Période courante", "Période réf.", "Variation"]);

  for (const company of payload.companies) {
    const k = computeCompanyKpis(company);
    const prev = comparisonCompany(payload.comparison, company.company_id);
    if (!prev) continue;

    const kPrev = computeCompanyKpis(prev);
    const metrics: { label: string; current: CellValue; previous: CellValue; delta: number | null }[] = [
      {
        label: "Effectif total",
        current: num(company.total_employee_count, FMT.INT),
        previous: num(prev.total_employee_count, FMT.INT),
        delta: percentDelta(company.total_employee_count, prev.total_employee_count),
      },
      {
        label: "Masse salariale brute",
        current: num(company.gross_salary, FMT.EUR),
        previous: num(prev.gross_salary, FMT.EUR),
        delta: percentDelta(company.gross_salary, prev.gross_salary),
      },
      {
        label: "Masse salariale nette",
        current: num(company.net_salary, FMT.EUR),
        previous: num(prev.net_salary, FMT.EUR),
        delta: percentDelta(company.net_salary, prev.net_salary),
      },
      {
        label: "Charges patronales",
        current: num(company.employer_charges, FMT.EUR),
        previous: num(prev.employer_charges, FMT.EUR),
        delta: percentDelta(company.employer_charges, prev.employer_charges),
      },
      {
        label: "Coût employeur total",
        current: num(k.totalEmployerCost, FMT.EUR),
        previous: num(kPrev.totalEmployerCost, FMT.EUR),
        delta: percentDelta(k.totalEmployerCost, kPrev.totalEmployerCost),
      },
      {
        label: "Taux de charges",
        current: pctRate(k.chargeRate),
        previous: pctRate(kPrev.chargeRate),
        delta: percentDelta(k.chargeRate, kPrev.chargeRate),
      },
    ];

    for (const m of metrics) {
      b.tableRow([t(company.company_name), t(m.label), m.current, m.previous, deltaText(m.delta)], 0);
    }
    b.blank(2);
  }

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

function buildRepartitionSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Répartition", [28, 16, 14]);
  const b = new SheetBuilder(ws, "C");
  b.titleBand("Répartition inter-entreprises", `${payload.groupName}  ·  ${payload.periodLabel}`);

  const sections: { title: string; total: number; valueOf: (c: CompanyStats) => number; fmt: string }[] = [
    {
      title: "Effectifs",
      total: payload.totals.total_employees,
      valueOf: (c) => c.total_employee_count,
      fmt: FMT.INT,
    },
    {
      title: "Masse salariale brute",
      total: payload.totals.total_gross_salary,
      valueOf: (c) => c.gross_salary,
      fmt: FMT.EUR,
    },
    {
      title: "Masse salariale nette",
      total: payload.totals.total_net_salary,
      valueOf: (c) => c.net_salary,
      fmt: FMT.EUR,
    },
    {
      title: "Charges patronales",
      total: payload.totals.total_employer_charges,
      valueOf: (c) => c.employer_charges,
      fmt: FMT.EUR,
    },
    {
      title: "Coût employeur total",
      total: payload.totalEmployerCostValue,
      valueOf: (c) => totalEmployerCost(c),
      fmt: FMT.EUR,
    },
  ];

  for (const section of sections) {
    b.sectionHeader(section.title);
    b.tableHeader(["Entreprise", "Valeur", "Part du groupe"]);
    for (const company of payload.companies) {
      const value = section.valueOf(company);
      const part = section.total > 0 ? value / section.total : 0;
      b.tableRow([t(company.company_name), num(value, section.fmt), pctShare(part)], 0);
    }
    b.tableRow(
      [t("Total"), num(section.total, section.fmt), pctShare(section.total > 0 ? 1 : 0)],
      payload.companies.length,
      { bold: true },
    );
    b.blank();
  }
}

function buildStatistiquesSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Statistiques KPI", [28, 14, 14, 14, 14, 14]);
  const b = new SheetBuilder(ws, "F");
  b.titleBand(
    "Distribution des indicateurs",
    `${payload.groupName}  ·  Dispersion min / médiane / moyenne / max entre les entreprises`,
  );

  b.tableHeader(["Indicateur", "Minimum", "Médiane", "Moyenne", "Maximum", "Écart (max − min)"]);

  const distRows: { label: string; dist: DistributionStats; fmt: string; isPct?: boolean }[] = [
    { label: "Taux de charges (%)", dist: payload.distributions.charge, fmt: FMT.PCT, isPct: true },
    { label: "Coût total / employé", dist: payload.distributions.cost, fmt: FMT.EUR },
    { label: "Ratio RH (%)", dist: payload.distributions.rh, fmt: FMT.PCT, isPct: true },
    { label: "Masse brute / employé", dist: payload.distributions.salary, fmt: FMT.EUR },
  ];

  for (const row of distRows) {
    b.tableRow(
      [
        t(row.label),
        num(row.isPct ? row.dist.min : row.dist.min, row.fmt),
        num(row.isPct ? row.dist.median : row.dist.median, row.fmt),
        num(row.isPct ? row.dist.avg : row.dist.avg, row.fmt),
        num(row.isPct ? row.dist.max : row.dist.max, row.fmt),
        row.isPct ? pctRate(row.dist.spread) : num(row.dist.spread, row.fmt),
      ],
      0,
    );
  }

  b.blank(4);
  b.note(
    "Les statistiques excluent les valeurs nulles. L'écart mesure la dispersion entre entités du groupe.",
  );
}

function buildEvolutionSheet(wb: ExcelJS.Workbook, payload: GroupDashboardExportPayload): void {
  const ws = createReportSheet(wb, "Évolution mensuelle", [16, 16, 16, 16, 12]);
  const b = new SheetBuilder(ws, "E");
  b.titleBand("Évolution mensuelle", `${payload.groupName}  ·  ${payload.periodLabel}`);

  const monthly = aggregateEvolutionMonthly(payload.evolution);

  if (monthly.length === 0) {
    b.note("Aucune donnée d'évolution disponible sur la période sélectionnée.");
    return;
  }

  b.sectionHeader("Vue agrégée groupe");
  b.tableHeader(["Mois", "Masse brute", "Charges patronales", "Coût employeur", "Effectifs"]);
  for (const row of monthly) {
    b.tableRow(
      [
        t(row.monthLabel),
        num(row.gross, FMT.EUR),
        num(row.charges, FMT.EUR),
        num(row.total, FMT.EUR),
        num(row.employees, FMT.INT),
      ],
      0,
    );
  }

  const companyNames = [...new Set(payload.evolution.map((p) => p.company_name))].sort();
  const monthKeys = monthly.map((m) => m.monthKey);
  const monthLabels = monthly.map((m) => m.monthLabel);

  const pivotSections: {
    title: string;
    valueOf: (p: EvolutionDataPoint) => number;
    fmt: string;
  }[] = [
    { title: "Masse salariale brute", valueOf: (p) => p.total_gross, fmt: FMT.EUR },
    { title: "Charges patronales", valueOf: (p) => p.total_employer_charges, fmt: FMT.EUR },
    {
      title: "Coût employeur",
      valueOf: (p) => p.total_gross + p.total_employer_charges,
      fmt: FMT.EUR,
    },
    { title: "Effectifs", valueOf: (p) => p.employee_count, fmt: FMT.INT },
  ];

  for (const section of pivotSections) {
    b.blank();
    b.sectionHeader(`${section.title} par entreprise et par mois`);
    b.tableHeader(["Entreprise", ...monthLabels]);

    for (const name of companyNames) {
      const companyPoints = payload.evolution.filter((p) => p.company_name === name);
      const byMonth = new Map<string, number>();
      for (const p of companyPoints) {
        const key = `${p.year}-${String(p.month).padStart(2, "0")}`;
        byMonth.set(key, (byMonth.get(key) ?? 0) + section.valueOf(p));
      }
      b.tableRow(
        [t(name), ...monthKeys.map((key) => num(byMonth.get(key) ?? 0, section.fmt))],
        0,
      );
    }
  }

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

export async function buildGroupDashboardWorkbook(
  payload: GroupDashboardExportPayload,
): Promise<ExcelJS.Workbook> {
  const ExcelJSRuntime = await loadExcelJS();
  const wb = new ExcelJSRuntime.Workbook();
  wb.creator = "EYWAI";
  wb.created = new Date();

  buildSyntheseSheet(wb, payload);
  buildDetailCompletSheet(wb, payload);
  buildFichesEntreprisesSheet(wb, payload);
  if (payload.compareTo !== "off" && payload.comparison?.by_company?.length) {
    buildComparatifSheet(wb, payload);
  }
  buildRepartitionSheet(wb, payload);
  buildStatistiquesSheet(wb, payload);
  buildEvolutionSheet(wb, payload);

  return wb;
}

function sanitizeFilenamePart(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase()
    .slice(0, 48);
}

export async function exportGroupDashboardXlsx(payload: GroupDashboardExportPayload): Promise<void> {
  const wb = await buildGroupDashboardWorkbook(payload);
  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const groupPart = sanitizeFilenamePart(payload.groupName || "groupe");
  downloadBlob(blob, `groupe-${groupPart}-${payload.periodExportKey}.xlsx`);
}

/** Utilitaire de test : noms des feuilles du classeur. */
export async function getGroupDashboardWorkbookSheetNames(
  payload: GroupDashboardExportPayload,
): Promise<string[]> {
  const wb = await buildGroupDashboardWorkbook(payload);
  return wb.worksheets.map((ws) => ws.name);
}

/** Utilitaire de test : vérifie le formatage des pourcentages (valeur brute stockée). */
export async function getSyntheseChargeRateDisplayValue(
  payload: GroupDashboardExportPayload,
): Promise<number | undefined> {
  const wb = await buildGroupDashboardWorkbook(payload);
  const ws = wb.getWorksheet("Synthèse");
  if (!ws) return undefined;
  for (let r = 1; r <= ws.rowCount; r += 1) {
    const indicateur = ws.getRow(r).getCell(2).value;
    if (indicateur === "Taux de charges (charges / brut)") {
      const val = ws.getRow(r).getCell(3).value;
      return typeof val === "number" ? val : undefined;
    }
  }
  return undefined;
}
