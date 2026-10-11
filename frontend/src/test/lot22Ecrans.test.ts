import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { avertissementSoldeInsuffisantRh } from "@/lib/employeeAbsencesUtils";

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
