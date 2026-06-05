import type ExcelJS from "exceljs";

import type { AnalyticsAvances } from "@/api/analytics";
import { downloadBlob } from "@/lib/downloadBlob";
import {
  type CellValue,
  createReportSheet,
  FMT,
  loadExcelJS,
  num,
  SheetBuilder,
  type StatusKind,
  text as t,
} from "@/lib/excelReport";

function statusTurnover(taux: number): StatusKind {
  if (taux <= 5) return "good";
  if (taux <= 15) return "warn";
  return "bad";
}

function statusAbsenteisme(taux: number): StatusKind {
  if (taux <= 4) return "good";
  if (taux <= 8) return "warn";
  return "bad";
}

function buildSyntheseSheet(
  wb: ExcelJS.Workbook,
  companyName: string,
  periodLabel: string,
  d: AnalyticsAvances,
): void {
  const ws = createReportSheet(wb, "Synthèse", [24, 56, 22, 22]);
  const b = new SheetBuilder(ws, "D");
  b.titleBand(
    "Analytics Team — Pilotage RH",
    `${companyName}  ·  Période : ${periodLabel}  ·  Généré le ${new Date().toLocaleString("fr-FR")}`,
  );

  b.sectionHeader("Indicateurs clés");
  b.synthesisTableHeader(["Domaine", "Indicateur", "Valeur", "Statut"]);

  const rows: { domaine: string; indicateur: string; value: CellValue; status?: StatusKind }[] = [
    {
      domaine: "Effectif",
      indicateur: "Effectif actif (salariés en poste)",
      value: num(d.effectif_actif, FMT.INT),
    },
    {
      domaine: "Turnover",
      indicateur: "Taux de turnover annuel",
      value: num(d.turnover.taux_turnover_annuel, FMT.PCT),
      status: statusTurnover(d.turnover.taux_turnover_annuel),
    },
    {
      domaine: "Mouvements",
      indicateur: "Embauches / départs (12 mois)",
      value: t(`${d.turnover.nb_embauches_12_mois} / ${d.turnover.nb_departs_12_mois}`),
    },
    {
      domaine: "Absentéisme",
      indicateur: "Taux d'absentéisme (30 jours)",
      value: num(d.absenteisme.taux_global, FMT.PCT2),
      status: statusAbsenteisme(d.absenteisme.taux_global),
    },
    {
      domaine: "Masse salariale",
      indicateur: "Masse salariale brute (base)",
      value: num(d.masse_salariale_brute_totale, FMT.EUR),
    },
    {
      domaine: "Démographie",
      indicateur: "Âge moyen",
      value: d.age_moyen > 0 ? t(`${d.age_moyen.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`) : t("—"),
    },
    {
      domaine: "Fidélisation",
      indicateur: "Ancienneté moyenne",
      value:
        d.anciennete_moyenne_annees > 0
          ? t(`${d.anciennete_moyenne_annees.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`)
          : t("—"),
    },
  ];

  for (const entry of rows) {
    b.synthesisTableRow(entry.domaine, entry.indicateur, entry.value, entry.status);
  }

  b.blank(4);
  b.note(
    "Seuils indicatifs — turnover : OK ≤ 5 % · à surveiller ≤ 15 % · critique > 15 %. Absentéisme : OK ≤ 4 % · à surveiller ≤ 8 % · critique > 8 %.",
  );
  b.note(
    "Périmètres : turnover et mouvements = 12 mois glissants · absentéisme = 30 derniers jours · effectif, masse salariale et démographie = salariés actifs.",
  );

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

function newDetailSheet(wb: ExcelJS.Workbook, name: string, widths: number[] = [52, 24, 22]): SheetBuilder {
  const ws = createReportSheet(wb, name, widths);
  return new SheetBuilder(ws, "C");
}

function buildEffectifsSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsAvances): void {
  const b = newDetailSheet(wb, "Effectifs");
  b.titleBand("Effectifs & démographie", `${companyName}  ·  ${periodLabel}`);

  b.sectionHeader("Vue d'ensemble");
  b.kpi("Effectif actif", num(d.effectif_actif, FMT.INT));
  b.kpi("Âge moyen", d.age_moyen > 0 ? num(d.age_moyen, FMT.DEC1) : t("—"));
  b.kpi("Ancienneté moyenne (ans)", d.anciennete_moyenne_annees > 0 ? num(d.anciennete_moyenne_annees, FMT.DEC1) : t("—"));
  b.blank();

  b.sectionHeader("Effectif par service");
  b.tableHeader(["Service", "Effectif", "Part"]);
  const totalService = d.effectif_par_service.reduce((s, r) => s + (Number(r.count) || 0), 0);
  if (d.effectif_par_service.length === 0) {
    b.tableRow([t("Aucune donnée"), num(0, FMT.INT), t("—")], 0);
  } else {
    d.effectif_par_service.forEach((r, idx) => {
      const count = Number(r.count) || 0;
      const part = totalService > 0 ? count / totalService : 0;
      b.tableRow([t(String(r.service ?? "—")), num(count, FMT.INT), num(part, FMT.PCT_INT)], idx);
    });
  }
  b.blank();

  b.sectionHeader("Effectif par type de contrat");
  b.tableHeader(["Type de contrat", "Effectif", "Part"]);
  const totalContrat = d.effectif_par_contrat.reduce((s, r) => s + (Number(r.count) || 0), 0);
  if (d.effectif_par_contrat.length === 0) {
    b.tableRow([t("Aucune donnée"), num(0, FMT.INT), t("—")], 0);
  } else {
    d.effectif_par_contrat.forEach((r, idx) => {
      const count = Number(r.count) || 0;
      const part = totalContrat > 0 ? count / totalContrat : 0;
      b.tableRow([t(String(r.type ?? "—")), num(count, FMT.INT), num(part, FMT.PCT_INT)], idx);
    });
  }
  b.blank();

  b.sectionHeader("Pyramide des âges");
  b.tableHeader(["Tranche d'âge", "Effectif", "Part"]);
  if (d.pyramide_ages.length === 0 || d.pyramide_ages.every((p) => p.count === 0)) {
    b.tableRow([t("Aucune donnée (renseigner les dates de naissance)"), num(0, FMT.INT), t("—")], 0);
  } else {
    d.pyramide_ages.forEach((p, idx) => {
      b.tableRow([t(p.tranche), num(p.count, FMT.INT), num((p.pourcentage || 0) / 100, FMT.PCT_INT)], idx);
    });
  }
}

function buildMouvementsSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsAvances): void {
  const b = newDetailSheet(wb, "Turnover & absentéisme");
  b.titleBand("Turnover & absentéisme", `${companyName}  ·  ${periodLabel}`);

  b.sectionHeader("Turnover (12 mois glissants)");
  b.kpi("Taux de turnover annuel", num(d.turnover.taux_turnover_annuel, FMT.PCT), statusTurnover(d.turnover.taux_turnover_annuel));
  b.kpi("Embauches (12 mois)", num(d.turnover.nb_embauches_12_mois, FMT.INT));
  b.kpi("Départs (12 mois)", num(d.turnover.nb_departs_12_mois, FMT.INT));
  b.kpi("Taux d'embauche", num(d.turnover.taux_embauches, FMT.PCT));
  b.kpi("Taux de départ", num(d.turnover.taux_departs, FMT.PCT));
  b.blank();

  b.sectionHeader("Absentéisme (30 derniers jours)");
  b.kpi("Taux global", num(d.absenteisme.taux_global, FMT.PCT2), statusAbsenteisme(d.absenteisme.taux_global));
  b.kpi("Taux maladie", num(d.absenteisme.taux_maladie, FMT.PCT2));
  b.kpi("Taux accident du travail", num(d.absenteisme.taux_at, FMT.PCT2));
  b.kpi("Taux autres motifs", num(d.absenteisme.taux_autres, FMT.PCT2));
  b.kpi(
    "Évolution vs mois précédent",
    num(d.absenteisme.evolution_vs_mois_precedent, FMT.PCT2),
    d.absenteisme.evolution_vs_mois_precedent > 0 ? "warn" : "good",
  );
  b.blank();

  b.sectionHeader("Jours perdus par motif");
  b.tableHeader(["Motif", "Jours perdus", "Part"]);
  const total = d.absenteisme.jours_perdus_total || 0;
  const motifs: { label: string; jours: number }[] = [
    { label: "Maladie", jours: d.absenteisme.jours_perdus_maladie || 0 },
    { label: "Accident du travail", jours: d.absenteisme.jours_perdus_at || 0 },
    { label: "Autres", jours: d.absenteisme.jours_perdus_autres || 0 },
  ];
  motifs.forEach((m, idx) => {
    const part = total > 0 ? m.jours / total : 0;
    b.tableRow([t(m.label), num(m.jours, FMT.INT), num(part, FMT.PCT_INT)], idx);
  });
  b.tableRow([t("Total"), num(total, FMT.INT), num(total > 0 ? 1 : 0, FMT.PCT_INT)], motifs.length, { bold: true });
}

function buildMasseSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsAvances): void {
  const b = newDetailSheet(wb, "Masse salariale", [52, 26, 18]);
  b.titleBand("Masse salariale", `${companyName}  ·  ${periodLabel}`);
  b.note("Brut mensuel de base par service (hors variables et charges patronales).");
  b.blank();

  b.sectionHeader("Masse salariale par service");
  b.tableHeader(["Service", "Masse salariale brute", "Part"]);
  const total = d.masse_salariale_par_service.reduce(
    (s, r) => s + (Number(r.masse_salariale_brute) || 0),
    0,
  );
  if (d.masse_salariale_par_service.length === 0) {
    b.tableRow([t("Aucune donnée"), num(0, FMT.EUR), t("—")], 0);
  } else {
    d.masse_salariale_par_service.forEach((r, idx) => {
      const brut = Number(r.masse_salariale_brute) || 0;
      const part = total > 0 ? brut / total : 0;
      b.tableRow([t(String(r.service ?? "—")), num(brut, FMT.EUR), num(part, FMT.PCT_INT)], idx);
    });
  }
  b.tableRow([t("Total"), num(total, FMT.EUR), num(total > 0 ? 1 : 0, FMT.PCT_INT)], d.masse_salariale_par_service.length, { bold: true });
}

export async function buildAnalyticsTeamWorkbook(
  companyName: string,
  periodLabel: string,
  data: AnalyticsAvances,
): Promise<ExcelJS.Workbook> {
  const ExcelJSRuntime = await loadExcelJS();
  const wb = new ExcelJSRuntime.Workbook();
  wb.creator = "EYWAI";
  wb.created = new Date();
  buildSyntheseSheet(wb, companyName, periodLabel, data);
  buildEffectifsSheet(wb, companyName, periodLabel, data);
  buildMouvementsSheet(wb, companyName, periodLabel, data);
  buildMasseSheet(wb, companyName, periodLabel, data);
  return wb;
}

export async function exportAnalyticsTeamXlsx(
  companyName: string,
  periodLabel: string,
  periodExportKey: string,
  data: AnalyticsAvances | undefined,
): Promise<void> {
  if (!data) return;
  const wb = await buildAnalyticsTeamWorkbook(companyName, periodLabel, data);
  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  downloadBlob(blob, `analytics-team-${periodExportKey}.xlsx`);
}

/** Utilitaire de test : noms des feuilles du classeur. */
export async function getAnalyticsTeamWorkbookSheetNames(
  companyName: string,
  periodLabel: string,
  data: AnalyticsAvances,
): Promise<string[]> {
  const wb = await buildAnalyticsTeamWorkbook(companyName, periodLabel, data);
  return wb.worksheets.map((ws) => ws.name);
}
