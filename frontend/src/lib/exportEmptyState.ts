import type { ExportPreviewResponse, ExportType } from "@/api/exports";

const EMPTY_DATA_PATTERN = /aucun(e)?\s|aucune\s|pas de\s|pas d'/i;

const EMPTY_EXPORT_LABELS: Partial<Record<ExportType, string>> = {
  notes_frais: "note de frais",
  conges_absences: "absence validée",
  journal_paie: "bulletin de paie",
  charges_sociales: "charge sociale",
  acomptes: "acompte ni avance",
  virement_salaires: "virement à générer",
  recapitulatif_montants: "montant à récapituler",
  od_salaires: "écriture salaire",
  od_charges_sociales: "écriture de charges sociales",
  od_pas: "écriture PAS",
  od_globale: "écriture comptable de paie",
  export_cabinet_generique: "bulletin à exporter",
  export_cabinet_quadra: "bulletin à exporter",
  export_cabinet_sage: "bulletin à exporter",
  dsn_mensuelle: "salarié à inclure dans la DSN",
};

export function formatExportPeriodLabel(period: string): string {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) return period;
  const label = new Date(year, month - 1, 1).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function isEmptyDataMessage(message: string): boolean {
  return EMPTY_DATA_PATTERN.test(message);
}

export function isExportPreviewEmpty(
  preview: ExportPreviewResponse,
  exportType: ExportType,
): boolean {
  if (preview.employees_count === 0) {
    return true;
  }

  if (exportType === "charges_sociales") {
    const organismes = preview.details?.organismes ?? [];
    if (organismes.length === 0) {
      return preview.warnings.some(isEmptyDataMessage);
    }
  }

  if (preview.details?.expenses_count === 0) {
    return true;
  }

  if (preview.details?.absences_count === 0 && exportType === "conges_absences") {
    return true;
  }

  const hasEmptySignal = [...preview.warnings, ...preview.anomalies.map((a) => a.message)].some(
    isEmptyDataMessage,
  );

  return hasEmptySignal && !preview.can_generate;
}

export function getEmptyExportAlertMessage(
  preview: ExportPreviewResponse,
  exportType: ExportType,
  period: string,
): string | null {
  if (!isExportPreviewEmpty(preview, exportType)) {
    return null;
  }

  const periodLabel = formatExportPeriodLabel(period);
  const subject = EMPTY_EXPORT_LABELS[exportType];

  if (subject) {
    return `Pas de ${subject} pour ${periodLabel}.`;
  }

  const emptyWarning = preview.warnings.find(isEmptyDataMessage);
  if (emptyWarning) {
    return emptyWarning.endsWith(".") ? emptyWarning : `${emptyWarning}.`;
  }

  const emptyAnomaly = preview.anomalies.find(
    (a) => a.severity === "blocking" && isEmptyDataMessage(a.message),
  );
  if (emptyAnomaly) {
    return emptyAnomaly.message.endsWith(".")
      ? emptyAnomaly.message
      : `${emptyAnomaly.message}.`;
  }

  return `Aucune donnée à exporter pour ${periodLabel}.`;
}
