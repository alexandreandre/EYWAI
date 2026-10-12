import { describe, expect, it } from "vitest";
import type { ExportPreviewResponse } from "@/api/exports";
import {
  formatExportPeriodLabel,
  getEmptyExportAlertMessage,
  isEmptyDataMessage,
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

/**
 * Le message réel de l'aperçu DSN (`message_non_deposable()`, dsn_export,
 * relevé le 12/10/2026). Il contient « aucun » au milieu d'une phrase
 * (« …qui ne figurent sur aucun bulletin… ») : ce n'est pas un message de vide.
 */
const MESSAGE_DSN_NON_DEPOSABLE =
  "DSN pas encore déposable : ne déposez pas ce fichier sur net-entreprises.\n" +
  "Déjà produit par Martine :\n" +
  "  - envoi, déclaration, entreprise et établissement\n" +
  "  - salariés et contrats\n" +
  "  - rémunérations et cotisations individuelles\n" +
  "  - bordereau et versements Urssaf, retraite complémentaire et impôt à la source\n" +
  "  - prévoyance et mutuelle : adhésions et affiliations\n" +
  "  - arrêts de travail, fins de contrat et autres suspensions\n" +
  "Reste avant d'ouvrir le dépôt :\n" +
  "  - les versements trimestriels aux organismes de prévoyance et de mutuelle : pas encore produits\n" +
  "  - les cotisations Urssaf qui ne figurent sur aucun bulletin (solde annuel, réduction ponctuelle) : absentes du bordereau\n" +
  "  - une DSN complète contrôlée sans rejet par l'outil officiel DSN-VAL, pour chaque société\n" +
  "En attendant : déposez la DSN du mois comme avant, depuis votre ancien logiciel de paie. Si ce n'est pas possible, ouvrez un ticket (menu Support, module « Paie & Bulletins », urgence « Critique ») avant l'échéance de dépôt.";

describe("aperçu DSN non déposable [I1]", () => {
  const apercuDsn: ExportPreviewResponse = {
    export_type: "dsn_mensuelle",
    period: "2026-09",
    employees_count: 7,
    totals: { employees_count: 7 },
    anomalies: [{ type: "error", message: MESSAGE_DSN_NON_DEPOSABLE, severity: "blocking" }],
    warnings: [],
    can_generate: false,
  };

  it("le message « DSN pas encore déposable » n'est pas un message de vide", () => {
    expect(isEmptyDataMessage(MESSAGE_DSN_NON_DEPOSABLE)).toBe(false);
  });

  it("l'aperçu n'annonce pas « Pas de salarié à inclure dans la DSN »", () => {
    expect(isExportPreviewEmpty(apercuDsn, "dsn_mensuelle")).toBe(false);
    expect(getEmptyExportAlertMessage(apercuDsn, "dsn_mensuelle", "2026-09")).toBeNull();
  });

  it("un message de vide commence par « Aucun », « Aucune » ou « Pas de »", () => {
    expect(isEmptyDataMessage("Aucune note de frais validée trouvée pour cette période")).toBe(true);
    expect(isEmptyDataMessage("Aucun bulletin trouvé pour cette période")).toBe(true);
    expect(isEmptyDataMessage("Pas de bulletin pour cette période")).toBe(true);
    expect(isEmptyDataMessage("Pas d’acompte sur cette période")).toBe(true);
  });

  it("« aucun » ou « pas de » au milieu d'une anomalie ne la masque pas", () => {
    expect(isEmptyDataMessage("Jeanne Essai : pas de NIR sur la fiche")).toBe(false);
    expect(isEmptyDataMessage("Cotisation sans code : aucun organisme rattaché")).toBe(false);
  });
});

describe("exportEmptyState : élision devant une voyelle", () => {
  it("« Pas d'acompte à virer », pas « Pas de acompte »", () => {
    const vide = basePreview({ export_type: "virement_acomptes" });
    expect(getEmptyExportAlertMessage(vide, "virement_acomptes", "2026-10")).toBe(
      "Pas d'acompte à virer pour Octobre 2026.",
    );
  });

  it("« Pas d'écriture… » et « Pas d'absence… »", () => {
    expect(getEmptyExportAlertMessage(basePreview({ export_type: "od_salaires" }), "od_salaires", "2026-10")).toBe(
      "Pas d'écriture salaire pour Octobre 2026.",
    );
    expect(
      getEmptyExportAlertMessage(basePreview({ export_type: "conges_absences" }), "conges_absences", "2026-10"),
    ).toBe("Pas d'absence validée pour Octobre 2026.");
  });

  it("devant une consonne, rien ne change", () => {
    expect(getEmptyExportAlertMessage(basePreview(), "notes_frais", "2026-10")).toBe(
      "Pas de note de frais pour Octobre 2026.",
    );
  });
});
