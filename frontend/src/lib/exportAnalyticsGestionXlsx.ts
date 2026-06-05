import type ExcelJS from "exceljs";

import type { AnalyticsGestionResponse } from "@/api/analyticsGestion";
import { MONTH_NAMES_FR } from "@/lib/analyticsPeriod";
import { downloadBlob } from "@/lib/downloadBlob";
import {
  type CellValue,
  createReportSheet,
  FMT,
  formatDateFr,
  loadExcelJS,
  num,
  SheetBuilder,
  type StatusKind,
  text as t,
} from "@/lib/excelReport";

const ENTRETIEN_STATUS_LABELS: Record<string, string> = {
  planifie: "Planifié",
  en_attente_acceptation: "En attente acceptation",
  accepte: "Accepté",
  refuse: "Refusé",
  realise: "Réalisé",
  cloture: "Clôturé",
};

const BUDGET_ALERT_LABELS: Record<string, string> = {
  none: "Normal",
  warning: "Attention",
  critical: "Critique",
};

function statusEntretiens(d: AnalyticsGestionResponse): StatusKind {
  if (d.entretiens.overdue_count > 0) return "bad";
  if (d.entretiens.actionable_count > 0) return "warn";
  return "good";
}

function statusConformite(d: AnalyticsGestionResponse): StatusKind {
  if (d.conformite.certifications_expired > 0 || d.conformite.legal_obligations_overdue > 0)
    return "bad";
  if (d.conformite.certifications_expiring > 0 || d.conformite.legal_obligations_due_soon > 0)
    return "warn";
  return "good";
}

function statusFormation(d: AnalyticsGestionResponse): StatusKind {
  if (d.formation.budget_envelope <= 0) return "neutral";
  if (d.formation.budget_alert_level === "critical") return "bad";
  if (d.formation.budget_alert_level === "warning") return "warn";
  return "good";
}

function statusCalendriers(d: AnalyticsGestionResponse): StatusKind {
  if (d.calendriers.avec_ecart > 0 || d.calendriers.conflits_absences > 0) return "bad";
  if (d.calendriers.a_saisir > 0) return "warn";
  return "good";
}

function statusMedical(d: AnalyticsGestionResponse): StatusKind {
  if (d.medical.overdue_count > 0) return "bad";
  if (d.medical.due_within_30_count > 0) return "warn";
  return "good";
}

function statusCarriere(d: AnalyticsGestionResponse): StatusKind {
  if (d.carriere.avenants_pending_signature > 0) return "warn";
  return "good";
}

function statusCse(d: AnalyticsGestionResponse): StatusKind {
  if (d.cse.election_critical_count > 0 || d.cse.delegation_over_quota_count > 0) return "bad";
  if (d.cse.mandate_alerts_count > 0 || d.cse.election_alerts_count > 0) return "warn";
  return "good";
}

function statusObjectives(d: AnalyticsGestionResponse): StatusKind {
  const rate = d.objectives.achievement_rate_pct;
  if (rate == null) return "neutral";
  if (rate >= 80) return "good";
  if (rate >= 50) return "warn";
  return "bad";
}

function buildSyntheseSheet(
  wb: ExcelJS.Workbook,
  companyName: string,
  periodLabel: string,
  d: AnalyticsGestionResponse,
): void {
  const ws = createReportSheet(wb, "Synthèse", [24, 56, 22, 22]);
  const b = new SheetBuilder(ws, "D");
  b.titleBand(
    "Analytics Gestion — Cockpit RH",
    `${companyName}  ·  Période : ${periodLabel}  ·  Généré le ${new Date().toLocaleString("fr-FR")}`,
  );

  b.sectionHeader("Indicateurs clés par domaine");
  b.synthesisTableHeader(["Domaine", "Indicateur clé", "Valeur", "Statut"]);

  const rows: { domaine: string; indicateur: string; value: CellValue; status: StatusKind }[] = [
    {
      domaine: "Entretiens",
      indicateur: "Entretiens à traiter (dont en retard)",
      value: t(`${d.entretiens.actionable_count} (${d.entretiens.overdue_count} en retard)`),
      status: statusEntretiens(d),
    },
    {
      domaine: "Objectifs",
      indicateur: "Taux de réalisation des objectifs",
      value: d.objectives.achievement_rate_pct == null ? t("—") : num(d.objectives.achievement_rate_pct, FMT.PCT),
      status: statusObjectives(d),
    },
    {
      domaine: "Conformité",
      indicateur: "Habilitations expirées + obligations en retard",
      value: num(d.conformite.certifications_expired + d.conformite.legal_obligations_overdue, FMT.INT),
      status: statusConformite(d),
    },
    {
      domaine: "Formation",
      indicateur: "Budget formation consommé",
      value: d.formation.budget_envelope > 0 ? num(d.formation.budget_consumption_pct, FMT.PCT_INT) : t("Non défini"),
      status: statusFormation(d),
    },
    {
      domaine: "Calendriers",
      indicateur: "À saisir + avec écart",
      value: num(d.calendriers.a_saisir + d.calendriers.avec_ecart, FMT.INT),
      status: statusCalendriers(d),
    },
    {
      domaine: "Médical",
      indicateur: "En retard + échéance sous 30 j",
      value: num(d.medical.overdue_count + d.medical.due_within_30_count, FMT.INT),
      status: statusMedical(d),
    },
    {
      domaine: "Carrière",
      indicateur: "Avenants en attente de signature",
      value: num(d.carriere.avenants_pending_signature, FMT.INT),
      status: statusCarriere(d),
    },
    {
      domaine: "CSE",
      indicateur: "Alertes mandats + élections critiques",
      value: num(d.cse.mandate_alerts_count + d.cse.election_critical_count, FMT.INT),
      status: statusCse(d),
    },
  ];

  for (const entry of rows) {
    b.synthesisTableRow(entry.domaine, entry.indicateur, entry.value, entry.status);
  }

  b.blank(4);
  b.note(
    "Légende statut : OK = sous contrôle · À surveiller = action recommandée · Critique = action immédiate. Objectifs : OK ≥ 80 % · à surveiller ≥ 50 %.",
  );
  b.note(
    `Périmètres : entretiens, objectifs, promotions et budget formation = année ${d.period.year} · calendriers = ${MONTH_NAMES_FR[d.period.calendar_month - 1] ?? ""} ${d.period.calendar_year} · médical, CSE et délégation = état au jour le plus récent.`,
  );

  ws.views = [{ state: "frozen", ySplit: 3, showGridLines: true }];
}

function newDetailSheet(wb: ExcelJS.Workbook, name: string, widths: number[] = [52, 24, 22]): SheetBuilder {
  const ws = createReportSheet(wb, name, widths);
  return new SheetBuilder(ws, "C");
}

function buildEntretiensSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "Entretiens");
  b.titleBand("Entretiens & objectifs", `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader("Indicateurs");
  b.kpi("À traiter", num(d.entretiens.actionable_count, FMT.INT));
  b.kpi("En retard", num(d.entretiens.overdue_count, FMT.INT), d.entretiens.overdue_count > 0 ? "bad" : "good");
  b.kpi("À venir sous 14 jours", num(d.entretiens.upcoming_14d_count, FMT.INT));
  b.kpi("Taux de clôture", num(d.entretiens.closure_rate_pct, FMT.PCT));
  b.kpi(
    "Taux de réalisation des objectifs",
    d.objectives.achievement_rate_pct == null ? t("—") : num(d.objectives.achievement_rate_pct, FMT.PCT),
    statusObjectives(d),
  );
  b.blank();
  b.sectionHeader("Répartition par statut");
  b.tableHeader(["Statut", "Nombre"]);
  const entries = Object.entries(d.entretiens.by_status)
    .filter(([, c]) => c > 0)
    .sort(([, a], [, c]) => c - a);
  if (entries.length === 0) {
    b.tableRow([t("Aucun entretien sur la période"), num(0, FMT.INT)], 0);
  } else {
    const total = entries.reduce((sum, [, count]) => sum + count, 0);
    entries.forEach(([status, count], idx) => {
      b.tableRow([t(ENTRETIEN_STATUS_LABELS[status] ?? status), num(count, FMT.INT)], idx);
    });
    b.tableRow([t("Total"), num(total, FMT.INT)], entries.length, { bold: true });
  }
}

function buildFormationSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "Formation");
  b.titleBand("Formation & conformité", `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader("Budget formation");
  b.kpi(
    "Budget consommé",
    d.formation.budget_envelope > 0 ? num(d.formation.budget_consumption_pct, FMT.PCT_INT) : t("—"),
    statusFormation(d),
  );
  b.kpi("Montant consommé", d.formation.budget_envelope > 0 ? num(d.formation.budget_consumed, FMT.EUR) : t("—"));
  b.kpi("Enveloppe budgétaire", d.formation.budget_envelope > 0 ? num(d.formation.budget_envelope, FMT.EUR) : t("Non définie"));
  b.kpi("Formations consommées (année)", num(d.formation.training_consumed_year, FMT.EUR));
  b.kpi("Niveau d'alerte budget", t(BUDGET_ALERT_LABELS[d.formation.budget_alert_level] ?? d.formation.budget_alert_level));
  b.kpi("Évaluations de formations", num(d.formation.evaluations_count, FMT.INT));
  b.kpi(
    "Note moyenne de satisfaction",
    d.formation.evaluations_average != null ? t(`${d.formation.evaluations_average.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} / 5`) : t("—"),
  );
  b.blank();
  b.sectionHeader("Conformité & habilitations");
  b.kpi("Habilitations expirées", num(d.conformite.certifications_expired, FMT.INT), d.conformite.certifications_expired > 0 ? "bad" : "good");
  b.kpi("Habilitations expirant bientôt", num(d.conformite.certifications_expiring, FMT.INT), d.conformite.certifications_expiring > 0 ? "warn" : "good");
  b.kpi("Obligations légales en retard", num(d.conformite.legal_obligations_overdue, FMT.INT), d.conformite.legal_obligations_overdue > 0 ? "bad" : "good");
  b.kpi("Obligations légales à échéance", num(d.conformite.legal_obligations_due_soon, FMT.INT), d.conformite.legal_obligations_due_soon > 0 ? "warn" : "good");
  b.kpi("Obligations légales à jour", num(d.conformite.legal_obligations_up_to_date, FMT.INT), "good");
}

function buildCalendriersSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "Calendriers");
  b.titleBand("Calendriers paie", `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader(`Mois de paie — ${MONTH_NAMES_FR[d.period.calendar_month - 1] ?? ""} ${d.period.calendar_year}`);
  b.kpi("Salariés suivis", num(d.calendriers.total, FMT.INT));
  b.kpi("Calendriers saisis", num(d.calendriers.saisis, FMT.INT), "good");
  b.kpi("À saisir", num(d.calendriers.a_saisir, FMT.INT), d.calendriers.a_saisir > 0 ? "warn" : "good");
  b.kpi("Avec écart", num(d.calendriers.avec_ecart, FMT.INT), d.calendriers.avec_ecart > 0 ? "bad" : "good");
  b.kpi("Conflits absences", num(d.calendriers.conflits_absences, FMT.INT), d.calendriers.conflits_absences > 0 ? "bad" : "good");
  b.kpi("Progression de saisie", num(d.calendriers.progress_percent, FMT.PCT_INT));
}

function buildMedicalSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "Médical", [56, 14, 22]);
  b.titleBand("Suivi médical", `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader("Indicateurs");
  b.kpi("Salariés actifs suivis", num(d.medical.active_total, FMT.INT));
  b.kpi("Obligations en retard", num(d.medical.overdue_count, FMT.INT), d.medical.overdue_count > 0 ? "bad" : "good");
  b.kpi("Échéance sous 30 jours", num(d.medical.due_within_30_count, FMT.INT), d.medical.due_within_30_count > 0 ? "warn" : "good");
  b.kpi("Visites réalisées ce mois", num(d.medical.completed_this_month, FMT.INT));
  b.kpi("Taux de conformité", num(d.medical.compliance_rate_pct, FMT.PCT), statusMedical(d));
  b.blank();
  b.sectionHeader("Salariés prioritaires (retards médicaux)");
  b.tableHeader(["Salarié", "Retards", "Échéance la plus urgente"]);
  if (d.medical.employees_overdue_top.length === 0) {
    b.tableRow([t("Aucun retard médical"), num(0, FMT.INT), t("—")], 0);
  } else {
    d.medical.employees_overdue_top.forEach((emp, idx) => {
      b.tableRow(
        [t(String(emp.employee_name)), num(Number(emp.obligations_overdue) || 0, FMT.INT), t(formatDateFr(String(emp.most_urgent_due_date)))],
        idx,
      );
    });
  }
}

function buildCarriereSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "Carrière");
  b.titleBand(`Carrière — année ${d.period.year}`, `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader("Indicateurs");
  b.kpi("Promotions sur l'année", num(d.carriere.total_promotions, FMT.INT));
  b.kpi("Taux d'approbation", num(d.carriere.approval_rate_pct, FMT.PCT_INT));
  b.kpi(
    "Augmentation salariale moyenne",
    d.carriere.average_salary_increase_pct != null ? num(d.carriere.average_salary_increase_pct, FMT.PCT) : t("—"),
  );
  b.kpi("Promotions en brouillon", num(d.carriere.promotions_draft_count, FMT.INT));
  b.kpi("Avenants en attente de signature", num(d.carriere.avenants_pending_signature, FMT.INT), statusCarriere(d));
  b.blank();
  b.sectionHeader("Promotions par mois");
  b.tableHeader(["Mois", "Nombre"]);
  const months = Object.entries(d.carriere.promotions_by_month).sort(([a], [c]) => a.localeCompare(c));
  if (months.length === 0) {
    b.tableRow([t("Aucune promotion"), num(0, FMT.INT)], 0);
  } else {
    const total = months.reduce((sum, [, count]) => sum + count, 0);
    months.forEach(([month, count], idx) => {
      const monthNum = Number(month.split("-")[1]);
      const label = `${MONTH_NAMES_FR[monthNum - 1] ?? month} ${month.slice(0, 4)}`;
      b.tableRow([t(label), num(count, FMT.INT)], idx);
    });
    b.tableRow([t("Total"), num(total, FMT.INT)], months.length, { bold: true });
  }
}

function buildCseSheet(wb: ExcelJS.Workbook, companyName: string, periodLabel: string, d: AnalyticsGestionResponse): void {
  const b = newDetailSheet(wb, "CSE", [56, 18, 14]);
  b.titleBand("CSE & dialogue social", `${companyName}  ·  ${periodLabel}`);
  b.sectionHeader("Indicateurs");
  b.kpi("Alertes mandats", num(d.cse.mandate_alerts_count, FMT.INT), d.cse.mandate_alerts_count > 0 ? "warn" : "good");
  b.kpi("Alertes électorales", num(d.cse.election_alerts_count, FMT.INT), d.cse.election_alerts_count > 0 ? "warn" : "good");
  b.kpi("Élections critiques", num(d.cse.election_critical_count, FMT.INT), d.cse.election_critical_count > 0 ? "bad" : "good");
  b.kpi("Élus en dépassement de quota", num(d.cse.delegation_over_quota_count, FMT.INT), d.cse.delegation_over_quota_count > 0 ? "bad" : "good");
  b.kpi("Heures de délégation consommées", num(d.cse.delegation_consumed_hours, FMT.HOURS));
  b.kpi("Quota mensuel de délégation", num(d.cse.delegation_quota_hours, FMT.HOURS));
  b.blank();
  b.sectionHeader("Réunions à venir");
  b.tableHeader(["Titre", "Date", "Heure"]);
  if (d.cse.upcoming_meetings.length === 0) {
    b.tableRow([t("Aucune réunion planifiée"), t("—"), t("—")], 0);
  } else {
    d.cse.upcoming_meetings.forEach((m, idx) => {
      b.tableRow([t(m.title), t(formatDateFr(m.meeting_date)), t(m.meeting_time ?? "—")], idx);
    });
  }
}

export async function buildAnalyticsGestionWorkbook(
  companyName: string,
  periodLabel: string,
  data: AnalyticsGestionResponse,
): Promise<ExcelJS.Workbook> {
  const ExcelJSRuntime = await loadExcelJS();
  const wb = new ExcelJSRuntime.Workbook();
  wb.creator = "EYWAI";
  wb.created = new Date();
  buildSyntheseSheet(wb, companyName, periodLabel, data);
  buildEntretiensSheet(wb, companyName, periodLabel, data);
  buildFormationSheet(wb, companyName, periodLabel, data);
  buildCalendriersSheet(wb, companyName, periodLabel, data);
  buildMedicalSheet(wb, companyName, periodLabel, data);
  buildCarriereSheet(wb, companyName, periodLabel, data);
  buildCseSheet(wb, companyName, periodLabel, data);
  return wb;
}

export async function exportAnalyticsGestionXlsx(
  companyName: string,
  periodLabel: string,
  periodExportKey: string,
  data: AnalyticsGestionResponse | undefined,
): Promise<void> {
  if (!data) return;
  const wb = await buildAnalyticsGestionWorkbook(companyName, periodLabel, data);
  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  downloadBlob(blob, `analytics-gestion-${periodExportKey}.xlsx`);
}

/** Utilitaire de test : noms des feuilles du classeur. */
export async function getAnalyticsGestionWorkbookSheetNames(
  companyName: string,
  periodLabel: string,
  data: AnalyticsGestionResponse,
): Promise<string[]> {
  const wb = await buildAnalyticsGestionWorkbook(companyName, periodLabel, data);
  return wb.worksheets.map((ws) => ws.name);
}
