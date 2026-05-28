import type { AnalyticsAvances } from "@/api/analytics";
import type { AnalyticsGestionSnapshot } from "@/api/analyticsGestion";
import { downloadBlob } from "@/lib/downloadBlob";

function escapeCsvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function downloadCsv(filename: string, rows: string[][]): void {
  const csv = rows.map((r) => r.map(escapeCsvCell).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, filename);
}

export function exportAnalyticsTeamCsv(
  companyName: string,
  period: string,
  data: AnalyticsAvances | undefined,
): void {
  const rows: string[][] = [
    ["Rapport Analytics Team", companyName, period],
    [],
    ["Indicateur", "Valeur"],
  ];
  if (data) {
    rows.push(
      ["Effectif actif", String(data.effectif_actif)],
      [
        "Turnover annuel (%)",
        data.turnover.taux_turnover_annuel.toLocaleString("fr-FR", { maximumFractionDigits: 1 }),
      ],
      ["Embauches 12 mois", String(data.turnover.nb_embauches_12_mois)],
      ["Départs 12 mois", String(data.turnover.nb_departs_12_mois)],
      [
        "Absentéisme 30j (%)",
        data.absenteisme.taux_global.toLocaleString("fr-FR", { maximumFractionDigits: 2 }),
      ],
      ["Masse salariale brute", String(data.masse_salariale_brute_totale)],
      ["Âge moyen", String(data.age_moyen)],
      ["Ancienneté moyenne (ans)", String(data.anciennete_moyenne_annees)],
    );
  }
  downloadCsv(`analytics-team-${period}.csv`, rows);
}

export function exportAnalyticsGestionCsv(
  companyName: string,
  period: string,
  data: AnalyticsGestionSnapshot | undefined,
): void {
  const rows: string[][] = [
    ["Rapport Analytics Gestion", companyName, period],
    [],
    ["Indicateur", "Valeur"],
  ];
  if (data) {
    rows.push(
      ["Entretiens à traiter", String(data.entretiens.actionable_count)],
      ["Entretiens en retard", String(data.entretiens.overdue_count)],
      ["Entretiens à venir (14j)", String(data.entretiens.upcoming_14d_count)],
      ["Taux clôture entretiens (%)", String(data.entretiens.closure_rate_pct)],
      ["Habilitations expirées", String(data.conformite.certifications_expired)],
      ["Habilitations expire bientôt", String(data.conformite.certifications_expiring)],
      ["Obligations légales en retard", String(data.conformite.legal_obligations_overdue)],
      ["Médical en retard", String(data.medical.overdue_count)],
      ["Médical échéance 30j", String(data.medical.due_within_30_count)],
      ["Taux conformité médical (%)", String(data.medical.compliance_rate_pct)],
      ["Calendriers à saisir", String(data.calendriers.a_saisir)],
      ["Calendriers avec écart", String(data.calendriers.avec_ecart)],
      ["Conflits absences calendrier", String(data.calendriers.conflits_absences)],
      [
        "Budget formation consommé (%)",
        String(data.formation.budget_consumption_pct),
      ],
      ["Promotions année", String(data.carriere.total_promotions)],
      ["Taux approbation promotions (%)", String(data.carriere.approval_rate_pct)],
      ["Alertes mandats CSE", String(data.cse.mandate_alerts_count)],
      ["Alertes électorales CSE", String(data.cse.election_alerts_count)],
      [
        "Taux réalisation objectifs (%)",
        String(data.objectives.achievement_rate_pct),
      ],
    );
  }
  downloadCsv(`analytics-gestion-${period}.csv`, rows);
}
