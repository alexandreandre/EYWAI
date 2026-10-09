import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Garde : aucun texte montré à la gestionnaire n'écrit un pluriel « (s) »
 * (« 3 jour(s) » se lit mal : le nombre décide). Les fichiers listés sont les
 * écrans atteignables en mode paie (lib/payrollFocus.ts) où le motif a été
 * corrigé ; les commentaires sont ignorés. Pendant côté serveur :
 * backend/tests/unit/architecture/test_pas_de_pluriel_entre_parentheses.py.
 */
const SRC = path.resolve(__dirname, "..");
const MOTIF = /[A-Za-zÀ-ÿ]\((s|es|e|x)\)/;
const CODE = /(?:^|[\s.(!])[A-Za-z_$][\w$]*\((s|e|x)\)(?=[\s;,.)\]}&|?:]|$)(?![^"'`]*["'`]\s*[,;)]?\s*$)/;

const FICHIERS = [
  "components/AbsenceRequestModal.tsx",
  "components/SaisieModal.tsx",
  "components/absences/MaintenancePreviewBlock.tsx",
  "components/exits/ExitDetailsPanel.tsx",
  "components/exports/PlanifiesTab.tsx",
  "components/payslip/MaintenanceDetailModal.tsx",
  "components/rates/RatesAdminPanel.tsx",
  "components/rates/RatesManualEditDialog.tsx",
  "components/saisies/ParticipationCampaignPanel.tsx",
  "components/saisies/ParticipationInteressementTab.tsx",
  "components/saisies/PrimesTab.tsx",
  "components/schedules/ApplyModelDialog.tsx",
  "components/schedules/CalendarBulkActionsBar.tsx",
  "components/schedules/PlanningImportBanner.tsx",
  "components/schedules/assisted-fill/PointageImportBanner.tsx",
  "components/schedules/assisted-fill/PointageImportDialog.tsx",
  "components/simulation/ArretMaladieSimulationTab.tsx",
  "components/simulation/SimulationPreview.tsx",
  "features/absences/components/LeaveCampaignSection.tsx",
  "features/absences/components/RttYearEndRhSection.tsx",
  "features/company/components/CompanyMutuelleSection.tsx",
  "features/company/components/CompanyPilotageSection.tsx",
  "features/company/components/CpFractionnementSettingsCard.tsx",
  "features/company/components/DocumentLibraryTab.tsx",
  "features/company/components/JeiSettingsCard.tsx",
  "features/company/components/OethSettingsCard.tsx",
  "features/company/components/PayrollVariableRulesCard.tsx",
  "features/company/components/TimesheetImportSettingsCard.tsx",
  "features/company/components/WorkMedalSettingsCard.tsx",
  "features/pas-rates/components/PasImportDialog.tsx",
  "hooks/planningImportJobStore.ts",
  "hooks/useCalendar.ts",
  "lib/employeeAbsencesUtils.ts",
  "lib/planningAbsenceWarnings.ts",
  "pages/rh/EmployeeDetail.tsx",
  "pages/rh/Employees.tsx",
  "pages/rh/Schedules.tsx",
  "pages/rh/manager/ManagerApprovals.tsx",
];

describe("pluriels écrits à l'ancienne", () => {
  it("aucun « (s) » visible dans les écrans du mode paie corrigés", () => {
    const fautes: string[] = [];
    for (const f of FICHIERS) {
      readFileSync(path.join(SRC, f), "utf8")
        .split("\n")
        .forEach((ligne, i) => {
          const t = ligne.trim();
          if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) return;
          if (MOTIF.test(ligne) && !CODE.test(ligne)) {
            fautes.push(`${f}:${i + 1}: ${t.slice(0, 80)}`);
          }
        });
    }
    expect(fautes).toEqual([]);
  });
});
