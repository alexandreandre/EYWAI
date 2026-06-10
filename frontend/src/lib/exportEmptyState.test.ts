import { describe, expect, it } from "vitest";
import type { ExportPreviewResponse } from "@/api/exports";
import {
  formatExportPeriodLabel,
  getEmptyExportAlertMessage,
  isExportPreviewEmpty,
} from "./exportEmptyState";

const basePreview = (
  overrides: Partial<ExportPreviewResponse> = {},
): ExportPreviewResponse => ({
  export_type: "notes_frais",
  period: "2025-06",
  employees_count: 0,
  totals: { employees_count: 0 },
  anomalies: [
    {
      type: "error",
      message: "Aucune note de frais validée trouvée pour cette période",
      severity: "blocking",
    },
  ],
  warnings: [],
  can_generate: false,
  ...overrides,
});

describe("exportEmptyState", () => {
  it("formate la période en français", () => {
    expect(formatExportPeriodLabel("2025-06")).toBe("Juin 2025");
  });

  it("détecte un export notes de frais vide", () => {
    const preview = basePreview();
    expect(isExportPreviewEmpty(preview, "notes_frais")).toBe(true);
    expect(getEmptyExportAlertMessage(preview, "notes_frais", "2025-06")).toBe(
      "Pas de note de frais pour Juin 2025.",
    );
  });

  it("ne signale pas un export avec des données", () => {
    const preview = basePreview({
      employees_count: 2,
      can_generate: true,
      anomalies: [],
      totals: { employees_count: 2, total_amount: 120 },
    });
    expect(isExportPreviewEmpty(preview, "notes_frais")).toBe(false);
    expect(getEmptyExportAlertMessage(preview, "notes_frais", "2025-06")).toBeNull();
  });
});
