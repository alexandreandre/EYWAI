import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { choixIjssModifie } from "@/features/company/components/ijssSansSubrogation";
import {
  libelleIjssDuDetail,
  libelleIjssDuPanneau,
  phraseAppliqueSansEffet,
  phraseDeduitesDuMaintien,
  phraseSalaireJournalierRetenu,
  texteDeductionDuPliant,
} from "@/lib/ijssAffichage";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");
const eur = (n: number) => `${n.toFixed(2).replace(".", ",")} €`;

describe("Suivi IJSS : le panneau d'une ligne", () => {
  it("ne dit « subrogées » que pour un arrêt subrogé", () => {
    expect(libelleIjssDuPanneau(true)).toBe("IJSS bulletin (subrogées)");
    expect(libelleIjssDuPanneau(false)).not.toMatch(/subrog/i);
    expect(libelleIjssDuPanneau(false)).toBe("IJSS versées au salarié par la CPAM");
  });

  it("dit la part déduite du maintien et ses jours quand une déduction a joué", () => {
    expect(
      phraseDeduitesDuMaintien({ ijss_deduites: 687.12, nb_jours_maintenus: 19 }, eur),
    ).toBe("Déduites du maintien : 687,12 € (19 jours maintenus)");
    expect(
      phraseDeduitesDuMaintien({ ijss_deduites: 40, nb_jours_maintenus: 1 }, eur),
    ).toBe("Déduites du maintien : 40,00 € (1 jour maintenu)");
    expect(phraseDeduitesDuMaintien({ ijss_deduites: 40, nb_jours_maintenus: null }, eur)).toBe(
      "Déduites du maintien : 40,00 €",
    );
  });

  it("ne dit rien sans déduction", () => {
    expect(phraseDeduitesDuMaintien({ ijss_deduites: null, nb_jours_maintenus: null }, eur)).toBeNull();
    expect(phraseDeduitesDuMaintien({}, eur)).toBeNull();
  });

  it("dit qu'un montant appliqué ne change plus le bulletin", () => {
    expect(phraseAppliqueSansEffet()).toBe(
      "Appliqué, sans effet : la société verse le garanti en entier",
    );
  });

  it("le panneau s'appuie sur ces textes, garde la fiche ouverte après la validation", () => {
    const t = lire("pages/rh/SuiviIJSS.tsx");
    expect(t).toContain("libelleIjssDuPanneau(row.subrogation_active)");
    expect(t).toContain("phraseDeduitesDuMaintien(row, eur)");
    expect(t).toContain("row.applique_sans_effet");
    expect(t).toContain("phraseAppliqueSansEffet()");
    // La validation ne ferme plus la fiche ; l'application, si.
    expect(t).toContain("onValidated={invalidate}");
    expect(t).toContain("onUpdated={() => { invalidate(); setSelectedRow(null); }}");
    expect(t).toMatch(/validateMut = useMutation\(\{.*onSuccess: \(\) => \{ toast\(\{ title: 'Montant brut validé' \}\); onValidated\(\);/);
    expect(t).toContain("rows.find(");
  });

  it("la ligne du tableau suit le dashboard", () => {
    const t = lire("api/ijssTracking.ts");
    for (const cle of ["ijss_deduites", "ijss_deduites_source", "nb_jours_maintenus", "applique_sans_effet"]) {
      expect(t).toContain(cle);
    }
  });
});

describe("Détail du maintien : d'où vient le montant d'IJSS", () => {
  it("dit « validées (suivi IJSS) » pour un montant du suivi, « estimées » sinon", () => {
    expect(libelleIjssDuDetail(true)).toBe("IJSS validées (suivi IJSS)");
    expect(libelleIjssDuDetail(false)).toBe("IJSS estimées");
    expect(libelleIjssDuDetail(undefined)).toBe("IJSS estimées");
  });

  it("le détail du bulletin et le pliant s'en servent", () => {
    expect(lire("components/payslip/MaintenanceDetailModal.tsx")).toContain(
      "libelleIjssDuDetail(ijss.ijss_brut_override)",
    );
    expect(lire("components/absences/MaintenancePreviewBlock.tsx")).toContain(
      "libelleIjssDuDetail(ijss.ijss_brut_override)",
    );
    expect(lire("api/absences.ts")).toContain("ijss_brut_override?: boolean;");
  });
});

describe("Pliant « Maintien & subrogation » : ce que fait le réglage", () => {
  it("dit le garanti entier quand la société ne déduit pas", () => {
    expect(texteDeductionDuPliant(false, false)).toBe(
      "Aucune déduction : salaire garanti versé en entier (réglage de la société)",
    );
  });

  it("dit la déduction quand la société déduit", () => {
    expect(texteDeductionDuPliant(false, true)).toBe(
      "IJSS déduites du maintien (réglage de la société)",
    );
  });

  it("garde la phrase d'avant pour un arrêt subrogé, et se tait si le réglage est inconnu", () => {
    expect(texteDeductionDuPliant(true, false)).toBe("Déduit du maintien applicable");
    expect(texteDeductionDuPliant(false, undefined)).toBeNull();
  });

  it("le pliant et l'API portent le réglage", () => {
    expect(lire("components/absences/MaintenancePreviewBlock.tsx")).toContain(
      "texteDeductionDuPliant(data.subrogation_active, data.deduire_ijss_sans_subrogation)",
    );
    expect(lire("api/absences.ts")).toContain("deduire_ijss_sans_subrogation?: boolean;");
  });
});

describe("Carte « Maintien de salaire » : enregistrer le choix IJSS", () => {
  it("sait quand le choix n'est pas enregistré", () => {
    const form = { deduire_ijss_sans_subrogation: false };
    expect(choixIjssModifie(form, { deduire_ijss_sans_subrogation: true })).toBe(true);
    expect(choixIjssModifie(form, { deduire_ijss_sans_subrogation: false })).toBe(false);
    expect(choixIjssModifie(form, undefined)).toBe(false);
  });

  it("rappelle le choix modifié et pose un bouton Enregistrer près du choix", () => {
    const t = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(t).toContain("Choix modifié, pas encore enregistré.");
    expect(t).toContain("choixIjssModifie");
    // Le rappel est sous le choix, avant le champ suivant.
    expect(t.indexOf("{AIDE_IJSS_SANS_SUBROGATION}")).toBeLessThan(t.indexOf("Choix modifié, pas encore enregistré."));
    expect(t.indexOf("Choix modifié, pas encore enregistré.")).toBeLessThan(t.indexOf('htmlFor="provident_relay_days"'));
    // Le comportement d'enregistrement reste celui de la carte.
    expect(t).toContain("onClick={handleSave}");
  });
});

describe("Pliant : du salaire journalier à l'indemnité", () => {
  it("dit les 21 % forfaitaires d'un congé de maternité", () => {
    const ijss = { salaire_journalier_base: 69.0411, base_plafonnee: 54.5425, taux_forfaitaire_retire: 0.21 };
    expect(phraseSalaireJournalierRetenu(ijss, eur)).toBe("Moins 21 % forfaitaires : 54,54 € par jour");
  });

  it("dit le plafond quand le salaire journalier est plafonné", () => {
    const ijss = { salaire_journalier_base: 120, base_plafonnee: 98.63, taux_forfaitaire_retire: 0 };
    expect(phraseSalaireJournalierRetenu(ijss, eur)).toBe("Retenu dans la limite du plafond : 98,63 € par jour");
  });

  it("se tait quand le salaire journalier est retenu tel quel, ou inconnu", () => {
    expect(phraseSalaireJournalierRetenu({ salaire_journalier_base: 72.33, base_plafonnee: 72.33, taux_forfaitaire_retire: 0 }, eur)).toBeNull();
    expect(phraseSalaireJournalierRetenu({ salaire_journalier_base: 72.33 }, eur)).toBeNull();
    expect(phraseSalaireJournalierRetenu({ salaire_journalier_base: 72.33, base_plafonnee: 0 }, eur)).toBeNull();
  });

  it("s'affiche dans le pliant et dans le détail du bulletin, sous le salaire journalier", () => {
    for (const f of ["components/absences/MaintenancePreviewBlock.tsx", "components/payslip/MaintenanceDetailModal.tsx"]) {
      const t = lire(f);
      expect(t).toContain("phraseSalaireJournalierRetenu(ijss, eur)");
      expect(t.indexOf("Salaire journalier de base")).toBeLessThan(t.indexOf("phraseSalaireJournalierRetenu(ijss, eur)"));
    }
  });
});
