"""Rejeu de Colorplast 2026 sur le TEST, mois après mois, comparé à Quadra.

Le cabinet calcule l'allègement en cumulé : celui d'un mois vaut l'allègement dû
sur tous les mois écoulés moins celui déjà pris. Le cumul voyage de mois en mois
dans `employee_schedules.cumuls`, donc **un mois ne peut être juste que si les
précédents le sont**. Ce script déroule donc les mois dans l'ordre depuis
janvier, en bac à sable dans le temps : l'état des fiches est relevé avant et
remis après, et chaque mois est comparé au bulletin du cabinet.

Janvier vient des feuilles de pointage (`data/colorplast/pointages/2026-01/`,
règle de Gaëlle annotée sur S03 : heures = fin − début − 0,5 h de pause au-delà
de 6 h) ; les mois suivants viennent du setup du backtest, c'est-à-dire des
heures sup que le cabinet a réellement payées. C'est volontaire : on juge le
moteur sur les entrées de Quadra, pas sur notre lecture des feuilles. Ce que les
feuilles disent est une question de saisie, traitée à part (Bugny, 95 h relevées
sur janvier-mars pour 46,5 payées, question Q6 à Gaëlle).

Deux copies en double sont écartées avant de commencer, faute de quoi le moteur
les additionne — voir `_nettoyer_les_doublons_du_cabinet`.

Références : `data/colorplast/bulletins/2026-MM/` et `data/colorplast/dsn/`.
Détail des écarts dans `docs/colorplast-{janvier,fevrier}-2026-ligne-a-ligne.md`.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply] [--jusqu-a N]
"""

from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)
from scripts.backtest.colorplast_feuilles_janvier import poser_les_feuilles  # noqa: E402
from scripts.backtest.colorplast_setup import _clear_actual, apply_month  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR = 2026
#: Toutes les fiches que le rejeu touche sur l'année. Chaque mois n'en joue
#: qu'une partie — Demory est embauché le 23/03 — et c'est le tableau de
#: références du mois qui dit lesquelles.
SALARIES = ("BUGNY", "COTTE", "DEMORY", "ESPINOSA", "GAUTHERON", "GIRERD")
SMIC_HORAIRE = 12.02  # 12,31 à partir de juin

#: Tolérances par défaut : le centime, sauf le SMIC (au demi-centime) et les
#: lignes où le cabinet est connu pour ne pas être cohérent avec lui-même.
TOLERANCES = {
    "brut": 0.05, "net": 0.05, "pas": 0.05, "net_social": 0.05, "net_hs_exo": 0.05,
    "heures": 0.05, "pss": 0.05, "smic": 0.005, "autres": 0.05,
    "deduction": 0.005, "reduction": 0.05,
}

#: Chiffres relevés sur les bulletins Quadra, mois par mois.
#: `net` = (net à payer avant impôt, impôt à la source).
#: `heures` = (cumul heures, cumul h. sup) de l'encadré, cumulés depuis janvier.
REFERENCES: dict[int, dict] = {
    1: {
        "fenetre": ("2025-12-22", "2026-01-25"),
        # Janvier porte l'incohérence connue du cabinet sur les heures d'une
        # absence : trois valeurs différentes pour Cotte (16,97 imprimé / 16,99
        # pour la déduction / 17,11 pour l'allègement). D'où les tolérances
        # élargies sur les seules lignes concernées — question Q3 à Gaëlle.
        "tolerances": {"net": 0.15, "net_social": 0.15, "net_hs_exo": 1.0,
                       "deduction": 0.15, "reduction": 5.0},
        "brut": {"BUGNY": 3023.40, "COTTE": 2351.89, "ESPINOSA": 3046.68,
                 "GAUTHERON": 2252.28, "GIRERD": 3799.06},
        # Gros acomptes en janvier : le net à payer est ce qui reste après.
        "net": {"BUGNY": (139.02, 63.44), "COTTE": (65.97, 35.52), "ESPINOSA": (74.06, 0.0),
                "GAUTHERON": (54.69, 25.42), "GIRERD": (159.74, 111.81)},
        "net_social": {"BUGNY": 2508.65, "COTTE": 1880.84, "ESPINOSA": 2538.18,
                       "GAUTHERON": 1769.08, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 645.56, "COTTE": 256.64, "ESPINOSA": 611.08,
                       "GAUTHERON": 245.46, "GIRERD": 413.31},
        "heures": {"BUGNY": (189.50, 37.83), "COTTE": (165.50, 16.97), "ESPINOSA": (185.00, 33.33),
                   "GAUTHERON": (158.00, 16.20), "GIRERD": (169.00, 17.33)},
        # Proratisé en jours calendaires d'absence non rémunérée : Cotte 30/31,
        # Gautheron 29/31.
        "pss": {"BUGNY": 4005.00, "COTTE": 3875.81, "ESPINOSA": 4005.00,
                "GAUTHERON": 3746.61, "GIRERD": 4005.00},
        "autres": {"BUGNY": 53.22, "COTTE": 39.61, "ESPINOSA": 53.63,
                   "GAUTHERON": 40.26, "GIRERD": 89.41},
        "deduction": {"BUGNY": -56.75, "COTTE": -25.49, "ESPINOSA": -50.00,
                      "GAUTHERON": -24.38, "GIRERD": -26.00},
        "reduction": {"BUGNY": -569.91, "COTTE": -609.61, "ESPINOSA": -524.94,
                      "GAUTHERON": -582.21, "GIRERD": -252.64},
    },
    2: {
        "fenetre": ("2026-01-26", "2026-02-22"),
        # Février ne porte aucune absence non rémunérée : tout est au centime,
        # sauf la traîne de janvier sur l'allègement de Gautheron (−0,26).
        "tolerances": {"reduction": 0.30},
        "brut": {"BUGNY": 2634.90, "COTTE": 2398.38, "ESPINOSA": 3104.24,
                 "GAUTHERON": 2455.03, "GIRERD": 3799.06},
        "net": {"BUGNY": (2741.73, 63.51), "COTTE": (1918.04, 36.22), "ESPINOSA": (2491.84, 0.0),
                "GAUTHERON": (1838.78, 27.09), "GIRERD": (3051.51, 111.81)},
        # Le net social exclut le complément de mutuelle famille (98,13 chez
        # Espinosa, Gautheron et Girerd), retenu après lui, mais inclut le
        # transport et le remboursement de notes de frais.
        "net_social": {"BUGNY": 2741.73, "COTTE": 1918.04, "ESPINOSA": 2589.97,
                       "GAUTHERON": 1936.91, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 283.02, "COTTE": 261.77, "ESPINOSA": 664.80,
                       "GAUTHERON": 314.63, "GIRERD": 413.31},
        "heures": {"BUGNY": (358.50, 55.16), "COTTE": (334.50, 34.30), "ESPINOSA": (373.00, 69.66),
                   "GAUTHERON": (330.50, 37.03), "GIRERD": (338.00, 34.66)},
        "pss": {nom: 4005.00 for nom in ("BUGNY", "COTTE", "ESPINOSA", "GAUTHERON", "GIRERD")},
        "autres": {"BUGNY": 46.68, "COTTE": 40.37, "ESPINOSA": 54.58,
                   "GAUTHERON": 43.66, "GIRERD": 89.41},
        "deduction": {"BUGNY": -26.00, "COTTE": -26.00, "ESPINOSA": -54.50,
                      "GAUTHERON": -31.25, "GIRERD": -26.00},
        "reduction": {"BUGNY": -529.50, "COTTE": -622.61, "ESPINOSA": -531.17,
                      "GAUTHERON": -632.28, "GIRERD": -252.63},
    },
    3: {
        "fenetre": ("2026-02-23", "2026-03-22"),
        # Mars apporte trois mécanismes nouveaux d'un coup : l'arrêt maladie de
        # Gautheron (16→28/03, dont 3 jours de maintien de salaire, et des
        # heures sup dont une part perd l'exonération), le congé pour événement
        # familial de Cotte (25→27/02, payé mais qui sort les heures du compteur
        # et proratise le plafond) et l'embauche de Demory le 23/03.
        "brut": {"BUGNY": 3124.90, "COTTE": 2398.38, "DEMORY": 625.25,
                 "ESPINOSA": 3139.74, "GAUTHERON": 1609.96, "GIRERD": 3799.06},
        "net": {"BUGNY": (2751.38, 63.42), "COTTE": (1918.04, 36.22), "DEMORY": (496.93, 0.0),
                "ESPINOSA": (2523.79, 0.0), "GAUTHERON": (1157.34, 18.02), "GIRERD": (3051.51, 111.81)},
        "net_social": {"BUGNY": 2751.38, "COTTE": 1918.04, "DEMORY": 496.93,
                       "ESPINOSA": 2621.92, "GAUTHERON": 1255.47, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 740.28, "COTTE": 261.77, "DEMORY": 42.69,
                       "ESPINOSA": 697.92, "GAUTHERON": 175.97, "GIRERD": 413.31},
        "heures": {"BUGNY": (553.50, 98.49), "COTTE": (480.10, 49.23), "DEMORY": (50.50, 3.00),
                   "ESPINOSA": (562.50, 107.49), "GAUTHERON": (420.50, 46.26), "GIRERD": (507.00, 51.99)},
        # Proratisé chez les trois salariés dont le mois n'est pas entier : Cotte
        # ses 3 jours d'événement familial, Gautheron son arrêt, Demory son
        # embauche le 23.
        "pss": {"BUGNY": 4005.00, "COTTE": 3575.89, "DEMORY": 1162.74,
                "ESPINOSA": 4005.00, "GAUTHERON": 2957.61, "GIRERD": 4005.00},
        # Demory est en CDD : 2,646 % au lieu de 1,646 %, le point d'écart étant
        # la contribution au financement du CPF des titulaires de CDD.
        "autres": {"BUGNY": 54.93, "COTTE": 40.37, "DEMORY": 16.78,
                   "ESPINOSA": 55.19, "GAUTHERON": 29.44, "GIRERD": 89.41},
        # Chez Gautheron la base n'est pas son compteur d'heures sup (9,23) mais
        # 11,65 h : le bulletin porte la mention « 11,65 H.sup exo / 5,68 H
        # n.exo » — seules les heures sup rattachées à la part non maintenue de
        # l'arrêt perdent l'exonération. Chez Cotte c'est l'inverse : 17,33 h de
        # base alors que son compteur n'affiche que 14,93, parce que son absence
        # est payée.
        "deduction": {"BUGNY": -65.00, "COTTE": -26.00, "DEMORY": -4.50,
                      "ESPINOSA": -56.75, "GAUTHERON": -17.48, "GIRERD": -26.00},
        "reduction": {"BUGNY": -581.69, "COTTE": -617.14, "DEMORY": -201.39,
                      "ESPINOSA": -531.66, "GAUTHERON": -419.16, "GIRERD": -252.64},
    },
}


def _salaries_du_mois(mois: int) -> tuple[str, ...]:
    """Les salariés que le cabinet a payés ce mois-là."""
    return tuple(sorted(REFERENCES[mois]["brut"]))


def _tolerance(mois: int, cle: str) -> float:
    return REFERENCES[mois].get("tolerances", {}).get(cle, TOLERANCES[cle])


def _generer(employee_id: str, mois: int):
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id, year=YEAR, month=mois,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_rejeu_test",
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


def _snapshot(ids: list[str]) -> tuple[dict, list]:
    emps = supabase.table("employees").select("*").in_("id", ids).execute().data or []
    hist = supabase.table("salary_history").select("*").in_("employee_id", ids).execute().data or []
    return {e["id"]: e for e in emps}, hist


def _restaurer(emp_avant: dict, hist_avant: list) -> None:
    ids = list(emp_avant)
    apres = {e["id"]: e for e in (supabase.table("employees").select("*").in_("id", ids).execute().data or [])}
    for emp_id, avant in emp_avant.items():
        diff = {k: v for k, v in avant.items() if k != "updated_at" and apres.get(emp_id, {}).get(k) != v}
        if diff:
            supabase.table("employees").update(diff).eq("id", emp_id).execute()
            print(f"  fiche {avant.get('last_name')} : {sorted(diff)} remis")
    ids_avant = {h["id"] for h in hist_avant}
    hist_apres = supabase.table("salary_history").select("id").in_("employee_id", ids).execute().data or []
    retirees = [h for h in hist_apres if h["id"] not in ids_avant]
    for h in retirees:
        supabase.table("salary_history").delete().eq("id", h["id"]).execute()
    for h in hist_avant:
        supabase.table("salary_history").upsert(h).execute()
    print(f"  historique de salaire : {len(hist_avant)} ligne(s) remise(s), {len(retirees)} retirée(s)")


def _nettoyer_les_doublons_du_cabinet(emps: dict, mois_joues: list[int]) -> None:
    """Retire les copies que la base de test porte en double du cabinet.

    Deux chargements coexistent — le setup du backtest et un import DSN — et là
    où ils se recouvrent le moteur additionne au lieu de choisir.

    1. Les heures sup d'un mois existent deux fois (février : Espinosa 15 et 4
       de chaque côté, Gautheron 3,5), donc payées en double. Elles sont
       effacées ici, le setup repose ensuite les siennes.
    2. Les absences importées de la DSN sont datées **en fin de mois** au lieu
       de leur vraie date : Cotte le 30/01 quand son bulletin Quadra dit le 21,
       Gautheron les 29 et 30/01 quand il dit les 13 et 14. Comme la fenêtre
       d'un mois s'arrête avant la fin du mois civil, ces copies mal datées ne
       pèsent pas sur leur propre mois — elles tombent dans la fenêtre du mois
       suivant et y créent des absences qui n'ont jamais eu lieu. Les vraies
       dates sont posées par le setup ; les jours concernés sont remis à
       l'horaire normal de leur jour de semaine.

    Le chargeur date en revanche correctement les arrêts maladie, qui portent
    leurs dates dans la DSN : ils ne sont pas touchés.
    """
    admin = get_supabase_admin_client()
    for mois in mois_joues:
        fin_fenetre = date.fromisoformat(REFERENCES[mois]["fenetre"][1])
        for nom in _salaries_du_mois(mois):
            emp_id = emps[nom]["id"]
            admin.table("monthly_inputs").delete().match(
                {"employee_id": emp_id, "year": YEAR, "month": mois}
            ).ilike("name", "%suppl%").execute()

            sched = (
                admin.table("employee_schedules").select("id, planned_calendar")
                .match({"employee_id": emp_id, "year": YEAR, "month": mois})
                .maybe_single().execute()
            )
            if not sched or not sched.data:
                continue
            planned = copy.deepcopy(sched.data.get("planned_calendar") or {})
            jours = planned.get("calendrier_prevu") or []
            heures_du_jour_de_semaine: dict[int, float] = {}
            for j in jours:
                if j.get("type") == "travail" and j.get("heures_prevues"):
                    heures_du_jour_de_semaine.setdefault(
                        date(YEAR, mois, int(j["jour"])).weekday(), j["heures_prevues"]
                    )
            remis = []
            for j in jours:
                jour = date(YEAR, mois, int(j["jour"]))
                if not j.get("dsn_loader") or jour <= fin_fenetre or j.get("type") == "travail":
                    continue
                if j.get("type", "").startswith("arret"):
                    continue
                heures = heures_du_jour_de_semaine.get(jour.weekday())
                if heures is None:
                    continue
                j.update({"type": "travail", "heures_prevues": heures, "manuel": False})
                j.pop("dsn_loader", None)
                remis.append(f"{jour:%d/%m}={heures}")
            if remis:
                admin.table("employee_schedules").update(
                    {"planned_calendar": planned}
                ).eq("id", sched.data["id"]).execute()
                print(f"  {nom:10s} : absences DSN mal datées remises au travail ({', '.join(remis)})")


def _controler(nom: str, mois: int, data: dict, res) -> int:
    ref = REFERENCES[mois]
    rc = 0

    def verifier(cle: str, valeur: float, attendu: float, libelle: str, indent: str = "      ") -> None:
        nonlocal rc
        ecart = valeur - attendu
        print(f"{indent}{libelle} {valeur:.2f} (Quadra {attendu:.2f}, écart {ecart:+.2f})")
        if abs(ecart) > _tolerance(mois, cle):
            print(f"::error::{nom} {mois:02d}/{YEAR} : {libelle} hors tolérance ({ecart:+.2f})")
            rc = 1

    brut = float(data.get("salaire_brut") or 0)
    en_tete = data.get("en_tete") or {}
    ecart = brut - ref["brut"][nom]
    etat = "OK" if abs(ecart) <= _tolerance(mois, "brut") else "ECART"
    print(f"\n{etat:5s} {nom:10s} brut {brut:.2f} — Quadra {ref['brut'][nom]:.2f} — écart {ecart:+.2f} ; "
          f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; {res.status}")
    if etat != "OK":
        rc = 1
    fenetre_attendue = ref["fenetre"]
    if (en_tete.get("date_debut_variables"), en_tete.get("date_fin_variables")) != fenetre_attendue:
        print(f"::error::{nom} {mois:02d}/{YEAR} : fenêtre des variables inattendue "
              f"(attendu {fenetre_attendue[0]} → {fenetre_attendue[1]})")
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
    net = float(synthese.get("net_social_avant_impot") or 0)
    pas = float((synthese.get("impot_prelevement_a_la_source") or {}).get("montant") or 0)
    q_net, q_pas = ref["net"][nom]
    verifier("net", net, q_net, "net à payer avant impôt")
    verifier("pas", pas, q_pas, "impôt à la source")
    print(f"      net après impôt {net - pas:.2f} (Quadra {q_net - q_pas:.2f})")
    verifier("net_social", float(synthese.get("montant_net_social") or 0),
             ref["net_social"][nom], "montant net social")
    verifier("net_hs_exo", float(synthese.get("montant_net_hs_exonerees") or 0),
             ref["net_hs_exo"][nom], "net des heures sup exonérées")

    parametres = data.get("parametres") or {}
    verifier("smic", float(parametres.get("smic_horaire") or 0), SMIC_HORAIRE, "SMIC horaire")
    verifier("pss", float(parametres.get("pss_mensuel") or 0), ref["pss"][nom], "plafond Sécu")

    cumuls = (data.get("cumuls") or {}).get("cumuls") or {}
    q_h, q_hs = ref["heures"][nom]
    verifier("heures", float(cumuls.get("heures_remunerees") or 0), q_h, "cumul heures")
    verifier("heures", float(cumuls.get("heures_supplementaires_remunerees") or 0), q_hs, "cumul h. sup")

    structure = data.get("structure_cotisations") or {}
    verifier("autres", float((structure.get("bloc_autres_contributions") or {}).get("total") or 0),
             ref["autres"][nom], "autres contributions employeur")
    for c in (structure.get("bloc_autres_contributions") or {}).get("lignes") or []:
        print(f"        {str(c.get('libelle'))[:46]:46s} {c.get('montant_patronal')}")

    allegements = structure.get("bloc_allegements") or []

    def montant(coti_id: str) -> float:
        return next((float(c.get("montant_patronal") or 0.0)
                     for c in allegements if c.get("coti_id") == coti_id), 0.0)

    verifier("deduction", montant("deduction_hs_patronale"), ref["deduction"][nom],
             "déduction forfaitaire HS")
    verifier("reduction", montant("reduction_generale"), ref["reduction"][nom],
             "réduction générale")

    for w in res.warnings or []:
        print(f"      avertissement : {w}")
    return rc


def _jouer_le_mois(emps: dict, mois: int) -> int:
    print(f"\n{'=' * 62}\n=== {mois:02d}/{YEAR} : état posé puis bulletins générés\n{'=' * 62}")
    apply_month("Colorplast", YEAR, mois)
    if mois == 1:
        poser_les_feuilles(emps)
    rc = 0
    for nom in _salaries_du_mois(mois):
        try:
            res = _generer(emps[nom]["id"], mois)
        except PayslipBadRequestError as exc:
            print(f"::error::{nom} {mois:02d}/{YEAR} : {exc}")
            rc = 1
            continue
        rc |= _controler(nom, mois, _bulletin(emps[nom]["id"], mois), res)
    if mois == 1:
        # La fenêtre de février démarre le 26 janvier : elle relit la dernière
        # semaine de janvier, où les feuilles viennent d'être posées. Ce
        # pointage n'est pas celui que le cabinet a retenu pour février (Bugny
        # y fait 45,5 h, Gautheron n'a pas de feuille du tout). Une fois le
        # bulletin de janvier écrit, on l'efface : la fenêtre de février repart
        # du planning contractuel, c'est-à-dire de la saisie du cabinet.
        admin = get_supabase_admin_client()
        for nom in _salaries_du_mois(1):
            _clear_actual(admin, emps[nom]["id"], YEAR, 1)
        print("\n  pointages de janvier effacés : la fenêtre de février repart du planning")
    return rc


def main() -> int:
    apply = "--apply" in sys.argv
    dernier_mois = max(REFERENCES)
    if "--jusqu-a" in sys.argv:
        dernier_mois = int(sys.argv[sys.argv.index("--jusqu-a") + 1])
    mois_joues = [m for m in sorted(REFERENCES) if m <= dernier_mois]
    if not mois_joues:
        print(f"::error::Aucun mois de référence jusqu'à {dernier_mois}.")
        return 1

    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name")
                  .eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    if not apply:
        print(f"SIMULATION : rien n'est écrit. Mois à rejouer : {mois_joues}")
        for mois in mois_joues:
            ref = REFERENCES[mois]
            print(f"  {mois:02d}/{YEAR} — fenêtre {ref['fenetre'][0]} → {ref['fenetre'][1]}")
            for nom in _salaries_du_mois(mois):
                net, pas = ref["net"][nom]
                print(f"    {nom:10s} brut {ref['brut'][nom]:8.2f} ; "
                      f"net avant impôt {net:8.2f} ; impôt {pas:6.2f}")
        return 0

    manquants = sorted({nom for mois in mois_joues for nom in _salaries_du_mois(mois)} - set(emps))
    if manquants:
        print(f"::error::Salariés introuvables : {manquants}")
        return 1

    emp_avant, hist_avant = _snapshot([e["id"] for e in emps.values()])
    print("=== Fiches relevées avant ===")
    for e in emp_avant.values():
        print(f"  {e['last_name']:10s} salaire_de_base={e.get('salaire_de_base')}")
    rc = 0
    try:
        print("\n=== Doublons de la base de test retirés ===")
        _nettoyer_les_doublons_du_cabinet(emps, mois_joues)
        for mois in mois_joues:
            rc |= _jouer_le_mois(emps, mois)
    finally:
        print("\n=== Fiches remises comme avant ===")
        _restaurer(emp_avant, hist_avant)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
