import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { avertissementSoldeInsuffisantRh, libelleTypeArret, formatQuantiteFr } from "@/lib/employeeAbsencesUtils";
import { pluriel } from "@/lib/pluriel";

/** Défauts d'écran relevés au rejeu (lot 22). Les gardes lisent le source. */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Nouveau congé : avertissement de solde avant l'enregistrement", () => {
  it("RTT : parle à la RH, avec les nombres au format français", () => {
    expect(
      avertissementSoldeInsuffisantRh({ type: "rtt", prenom: "Léa", solde: 10, demande: 11 }),
    ).toBe("Le solde de RTT de Léa est de 10 j pour 11 j demandés ; le congé sera enregistré malgré tout.");
    expect(
      avertissementSoldeInsuffisantRh({ type: "rtt", prenom: "Léa", solde: 0.5, demande: 1 }),
    ).toBe("Le solde de RTT de Léa est de 0,50 j pour 1 j demandé ; le congé sera enregistré malgré tout.");
  });

  it("pas d'avertissement quand le solde suffit", () => {
    expect(avertissementSoldeInsuffisantRh({ type: "rtt", prenom: "Léa", solde: 11, demande: 11 })).toBeNull();
  });

  it("repos compensateur : en heures, et une journée entière sans crédit avertit", () => {
    expect(
      avertissementSoldeInsuffisantRh({ type: "repos_compensateur", prenom: "Léa", solde: 0, demande: 0, joursSansHeures: 1 }),
    ).toBe(
      "Le solde de repos compensateur de Léa est de 0 h pour 1 journée entière ; le repos sera enregistré malgré tout et le solde deviendra négatif.",
    );
    expect(
      avertissementSoldeInsuffisantRh({ type: "repos_compensateur", prenom: "Léa", solde: 3, demande: 7 }),
    ).toBe(
      "Le solde de repos compensateur de Léa est de 3 h pour 7 h demandées ; le repos sera enregistré malgré tout et le solde deviendra négatif.",
    );
  });

  it("la fenêtre l'affiche avant d'enregistrer", () => {
    const t = lire("components/AbsenceRequestModal.tsx");
    expect(t).toContain("avertissementSoldeInsuffisantRh(");
  });
});

describe("Temps de travail & HS : onglet du contingent", () => {
  const t = lire("features/work-time-tracking/components/ContingentHsTab.tsx");

  it("l'info-bulle de l'entête s'ouvre au survol de toute la case", () => {
    expect(t).toMatch(/<TooltipTrigger asChild> <TableHead[^>]*data-testid="hs-comptabilisees-entete"/);
  });

  it("la ligne des pauses n'apparaît que si elle est non nulle", () => {
    expect(t).not.toMatch(/\{" ?\}?<p>Pauses/);
    expect(t).toMatch(/Math\.abs\(row\.pause_deduction\) >= 0\.005 && \( <p>Pauses/);
  });
});

describe("Carte Compensation des heures entre semaines", () => {
  it("dit que l'option ne s'applique pas au temps partiel (heures complémentaires)", () => {
    const t = lire("features/company/components/CompensationSemainesSettingsCard.tsx");
    expect(t).toMatch(/temps partiel/);
    expect(t).toMatch(/heures complémentaires/);
  });
});

describe("Page des absences : colonne des soldes", () => {
  const t = lire("pages/rh/Absences.tsx");
  it("le libellé dit ce qu'il montre : le solde d'aujourd'hui", () => {
    expect(t).not.toContain("Solde Restant");
    expect(t).toContain("<TableHead>Solde aujourd&apos;hui</TableHead>");
  });
  it("les soldes s'écrivent à la française (40,50 j), jamais avec un point", () => {
    expect(t).not.toMatch(/\{remaining\} (j|h)/);
    expect(t).not.toMatch(/\{balanceAfterApproval\} j/);
    expect(t).toContain("formatQuantiteFr(remaining");
    expect(formatQuantiteFr(40.5)).toBe("40,50 j");
  });
});

describe("Détail du maintien de salaire", () => {
  it("affiche le nombre de jours de carence, accordé", () => {
    expect(pluriel(3, "jour")).toBe("3 jours");
    expect(pluriel(1, "jour")).toBe("1 jour");
    expect(pluriel(0, "jour")).toBe("0 jour");
    for (const f of ["components/payslip/MaintenanceDetailModal.tsx", "components/absences/MaintenancePreviewBlock.tsx"]) {
      const t = lire(f);
      expect(t).not.toMatch(/Carence (SS|employeur) : \{accord\(/);
      expect(t).toMatch(/Carence SS : \{pluriel\(carence\.carence_ss_jours, 'jour'\)\}/);
      expect(t).toMatch(/Carence employeur : \{pluriel\(carence\.carence_employeur_jours, 'jour'\)\}/);
    }
  });
  it("affiche le type d'arrêt en français, celui de la fenêtre de saisie", () => {
    expect(libelleTypeArret("maladie_simple")).toBe("Maladie simple");
    expect(libelleTypeArret("accident_trajet")).toBe("Accident de trajet");
    expect(libelleTypeArret("code_inconnu")).toBe("code_inconnu");
    expect(lire("components/payslip/MaintenanceDetailModal.tsx")).toContain("libelleTypeArret(maintien.type_arret)");
  });
});
