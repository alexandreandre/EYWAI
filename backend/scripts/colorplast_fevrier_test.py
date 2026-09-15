"""Rejeu de février 2026 de Colorplast sur le TEST, janvier d'abord, en bac à
sable dans le temps : l'état des fiches est relevé avant, janvier puis février
sont posés et générés, les bulletins de février sont comparés à Quadra, et les
fiches sont remises comme elles étaient.

Janvier est rejoué en premier parce que le cabinet calcule l'allègement en
cumulé : l'allègement de février vaut l'allègement de janvier+février réunis
moins celui déjà pris en janvier. Vérifié à la main sur Bugny — cumul brut
5 658,30 et cumul heures 358,50 donnent 1 099,4x, moins 569,91 = 529,5x, ce que
Quadra imprime. Le cumul voyage dans `employee_schedules.cumuls` du mois N-1 :
sans janvier juste, février ne peut pas l'être. Janvier est repris tel qu'il a
été validé le 15/09, feuilles de pointage comprises, et sert de porte d'entrée
(brut et compteurs contrôlés) avant qu'on regarde février.

Février vient du setup du backtest, pas des feuilles : les heures sup du mois
sont celles que le cabinet a payées (Espinosa 15 + 4, Gautheron 3,5, personne
d'autre). Les feuilles de février restent à confronter à cette saisie, mais
c'est une question de saisie, pas de moteur.

Deux congés chez Cotte les jeudi 19 et vendredi 20 février, sans effet sur le
brut : Quadra retire 14 h de base et 1,60 h structurelles (2 jours × 7 h et
2 × 0,80 h) puis remet la même somme en indemnité — 207,19 des deux côtés.

Attendus Quadra (brut) : Bugny 2 634,90 ; Cotte 2 398,38 ; Espinosa 3 104,24 ;
Gautheron 2 455,03 ; Girerd 3 799,06.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)
from scripts.backtest.colorplast_setup import apply_month  # noqa: E402
from scripts.colorplast_janvier_feuilles_test import (  # noqa: E402
    QUADRA_BRUT as JANVIER_BRUT,
    QUADRA_HEURES as JANVIER_HEURES,
    _poser_calendriers as poser_calendriers_janvier,
    _restaurer,
    _snapshot,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR, MONTH = 2026, 2
SALARIES = ("BUGNY", "COTTE", "ESPINOSA", "GAUTHERON", "GIRERD")

QUADRA_BRUT = {"BUGNY": 2634.90, "COTTE": 2398.38, "ESPINOSA": 3104.24, "GAUTHERON": 2455.03, "GIRERD": 3799.06}
#: « NET A PAYER AVANT IMPOT SUR LE REVENU » et impôt prélevé à la source du
#: bulletin Quadra. Pas d'acompte en février, contrairement à janvier : ces
#: montants sont directement ce que le salarié reçoit, à l'impôt près.
QUADRA_NET = {"BUGNY": (2741.73, 63.51), "COTTE": (1918.04, 36.22), "ESPINOSA": (2491.84, 0.0),
              "GAUTHERON": (1838.78, 27.09), "GIRERD": (3051.51, 111.81)}
#: Montant net social imprimé. Il exclut le complément de mutuelle famille
#: (98,13 chez Espinosa, Gautheron et Girerd), retenu après lui sur le net à
#: payer, mais il inclut le transport et le remboursement de notes de frais.
QUADRA_NET_SOCIAL = {"BUGNY": 2741.73, "COTTE": 1918.04, "ESPINOSA": 2589.97,
                     "GAUTHERON": 1936.91, "GIRERD": 3149.64}
#: Aucune absence non rémunérée en février : le résidu d'arrondi toléré en
#: janvier chez Cotte et Gautheron n'a plus lieu d'être ici.
TOLERANCE_NET_SOCIAL = 0.05
#: « Montant net des heures compl/suppl exo. » : brut des heures sup moins la
#: seule CSG déductible. Le cumul annuel imprimé à côté vaut janvier + février
#: (Bugny 645,56 + 283,02 = 928,58), ce qui vérifie la chaîne au passage.
QUADRA_NET_HS_EXO = {"BUGNY": 283.02, "COTTE": 261.77, "ESPINOSA": 664.80,
                     "GAUTHERON": 314.63, "GIRERD": 413.31}
TOLERANCE_NET_HS_EXO = 0.05
#: « Cumul heures » et « Cumul h.sup » de l'encadré Quadra, cumulés depuis
#: janvier : Bugny 189,50 + 169,00 = 358,50 et 37,83 + 17,33 = 55,16.
QUADRA_HEURES = {"BUGNY": (358.50, 55.16), "COTTE": (334.50, 34.30), "ESPINOSA": (373.00, 69.66),
                 "GAUTHERON": (330.50, 37.03), "GIRERD": (338.00, 34.66)}
#: Déduction forfaitaire patronale sur les heures sup (1,50 €/h sous 20 salariés).
QUADRA_DEDUCTION_HS = {"BUGNY": -26.00, "COTTE": -26.00, "ESPINOSA": -54.50,
                       "GAUTHERON": -31.25, "GIRERD": -26.00}
TOLERANCE_DEDUCTION_HS = 0.05
#: Plafond Sécu : février est un mois entier pour tout le monde, aucune absence
#: non rémunérée ne le proratise.
QUADRA_PLAFOND_SS = 4005.00
QUADRA_SMIC = 12.02
#: Total « Autres contrib. dues par empl. » : 1,646 % du brut (formation
#: 0,55 %, CSA, FNAL, dialogue social, taxe d'apprentissage et son solde),
#: + 8 % sur prévoyance et mutuelle patronales, + 20 % sur la retraite
#: supplémentaire du cadre. La DSN de février redéclare les mêmes taux que
#: celle de janvier (0,550 et 8,000 sur les cinq salariés).
QUADRA_AUTRES_CONTRIB = {"BUGNY": 46.68, "COTTE": 40.37, "ESPINOSA": 54.58,
                         "GAUTHERON": 43.66, "GIRERD": 89.41}
#: Réduction générale (« EXO., ECRET. ET ALLEG. COTIS ») du bulletin Quadra.
QUADRA_REDUCTION = {"BUGNY": -529.50, "COTTE": -622.61, "ESPINOSA": -531.17,
                    "GAUTHERON": -632.28, "GIRERD": -252.63}
#: Tolérance sur la réduction : février repart du cumul de janvier, où il reste
#: 1,41 chez Cotte et 4,50 chez Gautheron (Quadra compte une fraction d'heure de
#: plus que son propre compteur imprimé quand il y a une absence, question Q3 à
#: Gaëlle). Le report de ce reste est attendu ; le seuil ne laisse pas passer
#: davantage.
TOLERANCE_REDUCTION = 5.0


def _generer(employee_id: str, mois: int):
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id, year=YEAR, month=mois,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_fevrier_test",
            )
        )
    try:
        return _run(False)
    except PayslipCalendarIncompleteError:
        return _run(True)


def _bulletin(employee_id: str, mois: int) -> dict:
    return (
        supabase.table("payslips").select("payslip_data")
        .match({"employee_id": employee_id, "year": YEAR, "month": mois}).single().execute()
    ).data["payslip_data"]


def _ligne_allegement(data: dict, coti_id: str) -> float:
    lignes = (data.get("structure_cotisations") or {}).get("bloc_allegements") or []
    return next(
        (float(c.get("montant_patronal") or 0.0) for c in lignes if c.get("coti_id") == coti_id),
        0.0,
    )


def _rejouer_janvier(emps: dict) -> int:
    """Repose janvier tel qu'il a été validé et contrôle la porte d'entrée."""
    rc = 0
    apply_month("Colorplast", YEAR, 1)
    poser_calendriers_janvier(emps)
    for nom in SALARIES:
        try:
            _generer(emps[nom]["id"], 1)
        except PayslipBadRequestError as exc:
            print(f"::error::{nom} : janvier {exc}")
            rc = 1
            continue
        data = _bulletin(emps[nom]["id"], 1)
        brut = float(data.get("salaire_brut") or 0)
        cumuls = (data.get("cumuls") or {}).get("cumuls") or {}
        h = float(cumuls.get("heures_remunerees") or 0)
        hs = float(cumuls.get("heures_supplementaires_remunerees") or 0)
        q_h, q_hs = JANVIER_HEURES[nom]
        ecart = brut - JANVIER_BRUT[nom]
        print(f"  {nom:10s} brut {brut:.2f} (Quadra {JANVIER_BRUT[nom]:.2f}, écart {ecart:+.2f}) ; "
              f"cumul heures {h:.2f} (Quadra {q_h:.2f}) ; cumul h. sup {hs:.2f} (Quadra {q_hs:.2f})")
        if abs(ecart) > 0.05 or abs(h - q_h) > 0.05 or abs(hs - q_hs) > 0.05:
            print(f"::error::{nom} : janvier ne repart pas juste, février n'a pas de sens")
            rc = 1
    return rc


def _controler_fevrier(nom: str, data: dict, res) -> int:
    rc = 0
    brut = float(data.get("salaire_brut") or 0)
    en_tete = data.get("en_tete") or {}
    ecart = brut - QUADRA_BRUT[nom]
    etat = "OK" if abs(ecart) <= 0.05 else "ECART"
    print(f"\n{etat:5s} {nom:10s} brut {brut:.2f} — Quadra {QUADRA_BRUT[nom]:.2f} — écart {ecart:+.2f} ; "
          f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; {res.status}")
    if etat != "OK":
        rc = 1
    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", ""))
        if "suppl" in lib.lower() and "structur" not in lib.lower():
            print(f"      HS      {lib[:50]:50s} q={ligne.get('quantite')} +{ligne.get('gain')}")
    for cle in ("details_absences", "details_conges"):
        for ligne in data.get(cle) or []:
            print(f"      {cle[8:15]:7s} {str(ligne.get('libelle'))[:50]:50s} "
                  f"q={ligne.get('quantite')} -{ligne.get('perte')} +{ligne.get('gain')}")

    synthese = data.get("synthese_net") or {}
    net_avant = float(synthese.get("net_social_avant_impot") or 0)
    pas = float((synthese.get("impot_prelevement_a_la_source") or {}).get("montant") or 0)
    q_net, q_pas = QUADRA_NET[nom]
    print(f"      net avant impôt {net_avant:.2f} (Quadra {q_net:.2f}, écart {net_avant - q_net:+.2f}) ; "
          f"PAS {pas:.2f} (Quadra {q_pas:.2f}) ; net après impôt {net_avant - pas:.2f} (Quadra {q_net - q_pas:.2f})")
    if abs(net_avant - q_net) > 0.05:
        print(f"::error::{nom} : net à payer avant impôt hors tolérance ({net_avant - q_net:+.2f})")
        rc = 1
    if abs(pas - q_pas) > 0.05:
        print(f"::error::{nom} : impôt à la source hors tolérance ({pas - q_pas:+.2f})")
        rc = 1

    mns = float(synthese.get("montant_net_social") or 0)
    q_mns = QUADRA_NET_SOCIAL[nom]
    print(f"      montant net social {mns:.2f} (Quadra {q_mns:.2f}, écart {mns - q_mns:+.2f})")
    if abs(mns - q_mns) > TOLERANCE_NET_SOCIAL:
        print(f"::error::{nom} : montant net social hors tolérance ({mns - q_mns:+.2f})")
        rc = 1

    net_hs = float(synthese.get("montant_net_hs_exonerees") or 0)
    q_hs_exo = QUADRA_NET_HS_EXO[nom]
    print(f"      net des heures sup exonérées {net_hs:.2f} (Quadra {q_hs_exo:.2f}, écart {net_hs - q_hs_exo:+.2f})")
    if abs(net_hs - q_hs_exo) > TOLERANCE_NET_HS_EXO:
        print(f"::error::{nom} : net des heures sup exonérées hors tolérance ({net_hs - q_hs_exo:+.2f})")
        rc = 1

    parametres = data.get("parametres") or {}
    smic = float(parametres.get("smic_horaire") or 0)
    print(f"      SMIC horaire {smic:.2f} (Quadra {QUADRA_SMIC:.2f}, écart {smic - QUADRA_SMIC:+.2f})")
    if abs(smic - QUADRA_SMIC) > 0.005:
        print(f"::error::{nom} : SMIC horaire hors tolérance ({smic - QUADRA_SMIC:+.2f})")
        rc = 1
    pss = float(parametres.get("pss_mensuel") or 0)
    print(f"      plafond Sécu {pss:.2f} (Quadra {QUADRA_PLAFOND_SS:.2f}, écart {pss - QUADRA_PLAFOND_SS:+.2f})")
    if abs(pss - QUADRA_PLAFOND_SS) > 0.05:
        print(f"::error::{nom} : plafond Sécu hors tolérance ({pss - QUADRA_PLAFOND_SS:+.2f})")
        rc = 1

    cumuls = (data.get("cumuls") or {}).get("cumuls") or {}
    h = float(cumuls.get("heures_remunerees") or 0)
    hs = float(cumuls.get("heures_supplementaires_remunerees") or 0)
    q_h, q_hs_cum = QUADRA_HEURES[nom]
    print(f"      cumul heures {h:.2f} (Quadra {q_h:.2f}, écart {h - q_h:+.2f}) ; "
          f"cumul h. sup {hs:.2f} (Quadra {q_hs_cum:.2f}, écart {hs - q_hs_cum:+.2f})")
    if abs(h - q_h) > 0.05 or abs(hs - q_hs_cum) > 0.05:
        print(f"::error::{nom} : compteurs d'heures hors tolérance")
        rc = 1

    structure = data.get("structure_cotisations") or {}
    autres = float((structure.get("bloc_autres_contributions") or {}).get("total") or 0)
    q_autres = QUADRA_AUTRES_CONTRIB[nom]
    print(f"      autres contributions employeur {autres:.2f} (Quadra {q_autres:.2f}, écart {autres - q_autres:+.2f})")
    if abs(autres - q_autres) > 0.05:
        print(f"::error::{nom} : contributions patronales hors tolérance ({autres - q_autres:+.2f})")
        rc = 1
    for c in (structure.get("bloc_autres_contributions") or {}).get("lignes") or []:
        print(f"        {str(c.get('libelle'))[:46]:46s} {c.get('montant_patronal')}")

    deduction = _ligne_allegement(data, "deduction_hs_patronale")
    q_ded = QUADRA_DEDUCTION_HS[nom]
    print(f"      déduction forfaitaire HS {deduction:.2f} (Quadra {q_ded:.2f}, écart {deduction - q_ded:+.2f})")
    if abs(deduction - q_ded) > TOLERANCE_DEDUCTION_HS:
        print(f"::error::{nom} : déduction forfaitaire HS hors tolérance ({deduction - q_ded:+.2f})")
        rc = 1

    reduction = _ligne_allegement(data, "reduction_generale")
    q_red = QUADRA_REDUCTION[nom]
    print(f"      réduction générale {reduction:.2f} (Quadra {q_red:.2f}, écart {reduction - q_red:+.2f})")
    if abs(reduction - q_red) > TOLERANCE_REDUCTION:
        print(f"::error::{nom} : réduction générale hors tolérance ({reduction - q_red:+.2f})")
        rc = 1

    for w in res.warnings or []:
        print(f"      avertissement : {w}")
    return rc


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name")
                  .eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    if not apply:
        print("SIMULATION : rien n'est écrit. Attendus Quadra de février :")
        for nom in SALARIES:
            net, pas = QUADRA_NET[nom]
            print(f"  {nom:10s} brut {QUADRA_BRUT[nom]:8.2f} ; net avant impôt {net:8.2f} ; impôt {pas:6.2f}")
        return 0

    ids = [e["id"] for e in emps.values()]
    emp_avant, hist_avant = _snapshot(ids)
    print("=== Fiches relevées avant ===")
    for e in emp_avant.values():
        print(f"  {e['last_name']:10s} salaire_de_base={e.get('salaire_de_base')}")
    rc = 0
    try:
        print("\n=== Janvier reposé (porte d'entrée du cumul) ===")
        rc |= _rejouer_janvier(emps)
        print("\n=== Setup de février (backtest) ===")
        apply_month("Colorplast", YEAR, MONTH)
        print("\n=== Génération de février ===")
        for nom in SALARIES:
            try:
                res = _generer(emps[nom]["id"], MONTH)
            except PayslipBadRequestError as exc:
                print(f"::error::{nom} : {exc}")
                rc = 1
                continue
            rc |= _controler_fevrier(nom, _bulletin(emps[nom]["id"], MONTH), res)
    finally:
        print("\n=== Fiches remises comme avant ===")
        _restaurer(emp_avant, hist_avant)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
