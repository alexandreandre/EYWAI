import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  NATURE_DU_TYPE_ARRET,
  TYPES_ARRET_PAR_NATURE,
  natureAccordeeAuTypeArret,
  phraseNatureReglee,
  phraseTypeArretRetire,
  typesArretProposes,
} from "@/lib/employeeAbsencesUtils";

/**
 * L20 (capture du 27/11) : sous la nature « Arrêt maladie », la liste des types
 * proposait « Maladie professionnelle », que le serveur refuse pour cette
 * nature. Choisir un type d'une autre nature règle la nature, et le dit.
 */
const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

const NATURES_MALADIE_ACCIDENT = ["arret_maladie", "arret_at", "arret_maladie_pro"] as const;

describe("La nature d'un arrêt suit le type choisi", () => {
  it("« Maladie professionnelle » sous « Arrêt maladie » règle la nature sur maladie professionnelle", () => {
    expect(natureAccordeeAuTypeArret("arret_maladie", "maladie_professionnelle")).toBe("arret_maladie_pro");
  });

  it("un accident du travail, de trajet ou une rechute sous « Arrêt maladie » passent en accident du travail", () => {
    expect(natureAccordeeAuTypeArret("arret_maladie", "accident_travail")).toBe("arret_at");
    expect(natureAccordeeAuTypeArret("arret_maladie", "accident_trajet")).toBe("arret_at");
    expect(natureAccordeeAuTypeArret("arret_maladie", "rechute_at")).toBe("arret_at");
  });

  it("une maladie simple sous « Accident du travail » repasse en arrêt maladie", () => {
    expect(natureAccordeeAuTypeArret("arret_at", "maladie_simple")).toBe("arret_maladie");
    expect(natureAccordeeAuTypeArret("arret_maladie_pro", "ald")).toBe("arret_maladie");
  });

  it("un type déjà permis garde la nature (mi-temps, rechute d'une maladie professionnelle)", () => {
    for (const nature of NATURES_MALADIE_ACCIDENT) {
      expect(natureAccordeeAuTypeArret(nature, "mi_temps_therapeutique")).toBe(nature);
    }
    expect(natureAccordeeAuTypeArret("arret_maladie_pro", "rechute_at")).toBe("arret_maladie_pro");
    expect(natureAccordeeAuTypeArret("arret_at", "accident_trajet")).toBe("arret_at");
  });

  it("aucun type proposé ne mène à une combinaison refusée", () => {
    for (const nature of [...NATURES_MALADIE_ACCIDENT, "arret_maternite", "arret_paternite"]) {
      for (const { value } of typesArretProposes(nature)) {
        const reglee = natureAccordeeAuTypeArret(nature, value);
        expect(TYPES_ARRET_PAR_NATURE[reglee], `${nature} / ${value}`).toContain(value);
      }
    }
  });

  it("la phrase visible dit la nature réglée", () => {
    expect(phraseNatureReglee("arret_maladie_pro")).toBe(
      "Nature réglée sur « Maladie professionnelle », qui va avec ce type d'arrêt.",
    );
    expect(phraseTypeArretRetire("maladie_professionnelle", "arret_maladie")).toBe(
      "Le type « Maladie professionnelle » ne va pas avec la nature « Arrêt maladie » : choisissez le type d'arrêt.",
    );
  });

  it("les types permis par nature sont ceux que le serveur accepte (parité avec nature_arret.py)", () => {
    const py = readFileSync(
      path.resolve(SRC, "../../backend/app/modules/absences/domain/nature_arret.py"),
      "utf8",
    );
    const bloc = py.split("TYPES_D_ARRET_PAR_NATURE: dict[str, tuple[str, ...]] = {")[1].split("\n}\n")[0];
    const serveur: Record<string, string[]> = {};
    for (const m of bloc.matchAll(/"(arret_[a-z_]+)":\s*\(([^)]*)\)/g)) {
      serveur[m[1]] = [...m[2].matchAll(/"([a-z_]+)"/g)].map((t) => t[1]);
    }
    expect(Object.keys(serveur).sort()).toEqual(Object.keys(TYPES_ARRET_PAR_NATURE).sort());
    for (const [nature, types] of Object.entries(serveur)) {
      expect([...TYPES_ARRET_PAR_NATURE[nature]].sort(), nature).toEqual([...types].sort());
    }
    const blocNature = py.split("NATURE_DU_TYPE_D_ARRET: dict[str, str] = {")[1].split("\n}\n")[0];
    const natureServeur = Object.fromEntries(
      [...blocNature.matchAll(/"([a-z_]+)":\s*"([a-z_]+)"/g)].map((m) => [m[1], m[2]]),
    );
    expect(NATURE_DU_TYPE_ARRET).toEqual(natureServeur);
  });

  it("passer d'accident du travail à maladie professionnelle par le type vide la date, et le dit", () => {
    expect(phraseNatureReglee("arret_maladie_pro", { dateVidee: true })).toBe(
      "Nature réglée sur « Maladie professionnelle », qui va avec ce type d'arrêt. " +
        "La date saisie est vidée : indiquez celle de la première constatation, si vous l'avez.",
    );
    expect(phraseNatureReglee("arret_at", { dateVidee: true })).toBe(
      "Nature réglée sur « Accident du travail », qui va avec ce type d'arrêt. " +
        "La date saisie est vidée : indiquez celle de l'accident, si vous l'avez.",
    );
  });
});

describe("La fenêtre d'arrêt règle la nature (Arrêts & IJ et calendrier)", () => {
  const modal = lire("components/AbsenceRequestModal.tsx");

  it("le choix du type passe par la nature accordée et affiche la phrase", () => {
    expect(modal).toContain("natureAccordeeAuTypeArret(absenceType, suivant)");
    expect(modal).toContain('data-testid="nature-reglee"');
    expect(modal).toContain('data-testid="type-arret-retire"');
  });

  it("la nature réglée par le type vide la date de l'accident déjà saisie", () => {
    expect(modal).toContain('setDateAccident("")');
    expect(modal).toContain("phraseNatureReglee(nature, { dateVidee })");
  });

  it("la subrogation ne part que si son choix est affiché (pas sous le congé supplémentaire de naissance)", () => {
    expect(modal).toContain('subrogationVisible && subrogation !== "societe"');
    expect(modal).toContain("{subrogationVisible && (");
    expect(modal).not.toContain('isRhArret && isArretPrincipalType(absenceType) && subrogation !== "societe"');
  });

  it("un type qui ne va plus avec la nature changée à la main est retiré, et c'est dit", () => {
    expect(modal).toContain("TYPES_ARRET_PAR_NATURE[absenceType]");
    expect(modal).toContain("phraseTypeArretRetire(");
  });
});
