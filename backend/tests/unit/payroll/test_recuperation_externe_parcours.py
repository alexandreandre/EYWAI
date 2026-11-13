"""Recette isolée : sauvegarde du calendrier, réouverture, analyse et bulletin.

Les lectures/écritures de planning sont en mémoire, les barèmes sont figés.
Le moteur réel calcule brut, cotisations, net et cumuls sans persister.
"""

import json
from copy import deepcopy
from datetime import date
from io import BytesIO
from unittest.mock import Mock

import pytest
from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfReader
from weasyprint import HTML

from app.core.paths import payroll_engine_root
from app.modules.modulation.application import payroll_hook as compte_heures
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin
from app.modules.schedules.application import commands
from app.modules.schedules.application.persist_timesheet import _merge_days
from app.modules.schedules.domain.ecart_rules import is_day_ready_for_payroll
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee
from app.modules.schedules.schemas.requests import (
    ActualHoursRequest,
    PlannedCalendarRequest,
)
from tests.unit.payroll.test_annee_des_baremes import _baremes, _dossier_calculable

pytestmark = pytest.mark.unit

ANNEE, MOIS = 2026, 11


def _mois(*, motif="travail", repos_integral=False):
    prevu, reel = [], []
    for j in range(1, 31):
        ouvre = date(ANNEE, MOIS, j).weekday() < 5
        type_jour = "travail" if ouvre else "weekend"
        if ouvre and (j == 6 or repos_integral):
            type_jour = "repos" if repos_integral else motif
        heures_prevues = 0 if type_jour in ("repos", "weekend") else 7
        heures_faites = 7 if ouvre else 0
        if ouvre and 9 <= j <= 13 and not repos_integral:
            heures_faites = 9  # 45 h : 8 à 25 %, 2 à 50 % avant déclaration.
        if type_jour == "repos" or (j == 6 and motif == "absence_non_remuneree"):
            heures_faites = 0
        prevu.append({"jour": j, "type": type_jour, "heures_prevues": heures_prevues})
        reel.append({"jour": j, "type": type_jour, "heures_faites": heures_faites})
    return prevu, reel


def _enregistrer(monkeypatch, prevu, reel):
    """Les deux commandes réelles ne peuvent écrire que dans ce dictionnaire."""
    stocke = {"planned_calendar": {"calendrier_prevu": _mois()[0]}}
    monkeypatch.setattr(commands, "get_employee_company_and_statut", lambda _id: ("soc-test", "Non-Cadre"))
    monkeypatch.setattr(commands.queries, "get_planned_calendar", lambda *_a: deepcopy(stocke["planned_calendar"]))
    monkeypatch.setattr(commands.schedule_repository, "get_planned_calendar", lambda *_a: deepcopy(stocke["planned_calendar"]))

    def sauvegarder(*_a, **colonnes):
        stocke.update(deepcopy(colonnes))

    monkeypatch.setattr(commands.schedule_repository, "upsert_schedule", sauvegarder)
    resultat = commands.update_planned_calendar("emp-test", PlannedCalendarRequest(
        year=ANNEE, month=MOIS, calendrier_prevu=prevu,
    ))
    assert resultat["warnings"] == []  # Ni création ni annulation de demande CP/RTT.
    commands.update_actual_hours("emp-test", ActualHoursRequest(
        year=ANNEE, month=MOIS, calendrier_reel=reel,
    ))
    return stocke["planned_calendar"]["calendrier_prevu"], stocke["actual_hours"]["calendrier_reel"]


def _calculer(tmp_path, prevu, reel, declaration=None, *, primes=(), forfait=False, evenements=None):
    dossier = _dossier_calculable(tmp_path, forfait=forfait)
    if evenements is None:
        evenements = analyser_horaires_du_mois(
            [{**j, "annee": ANNEE, "mois": MOIS} for j in prevu],
            [{**j, "annee": ANNEE, "mois": MOIS} for j in reel],
            35, ANNEE, MOIS, "Salarié synthétique",
        )
    saisies = {"primes": list(primes)}
    if declaration is not None:
        saisies.update({
            "heures_sup_declarees_au_bulletin": True,
            "heures_supplementaires_conjoncturelles": declaration[0],
            "heures_supplementaires_conjoncturelles_50": declaration[1],
        })
    fichiers = {
        "saisies/11.json": saisies,
        "calendriers/11.json": {"calendrier_prevu": prevu},
        "horaires/11.json": {"calendrier_reel": reel},
        "evenements_paie/11.json": {"calendrier_analyse": evenements},
    }
    for chemin, contenu in fichiers.items():
        cible = dossier / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(json.dumps(contenu), encoding="utf-8")
    calculer = (
        payslip_run_forfait.run_payslip_generation_forfait if forfait
        else payslip_run_heures.run_payslip_generation_heures
    )
    return calculer(
        dossier, ANNEE, MOIS, payroll_engine_root(),
        baremes_override=_baremes(), persister=False,
    )


def _hs(bulletin):
    return [l for l in bulletin["calcul_du_brut"] if str(l.get("libelle", "")).startswith("Heures suppl.")]


@pytest.mark.parametrize("declaration", [(0, 0), (3, 0), (3, 2)])
def test_repos_enregistre_et_hs_definitives_au_bulletin(monkeypatch, tmp_path, declaration):
    prevu, reel = _enregistrer(monkeypatch, *_mois(motif="repos"))
    assert prevu[5] == {"jour": 6, "type": "repos", "heures_prevues": 0.0}
    assert reel[5]["heures_faites"] == 0
    assert is_day_ready_for_payroll(prevu[5], reel[5])
    bulletin = _calculer(tmp_path, prevu, reel, declaration)
    assert bulletin["heures_sup_declarees"] == {"hs25": declaration[0], "hs50": declaration[1], "planning": 10.0}
    for taux, quantite in zip((25, 50), declaration):
        assert sum(l["quantite"] for l in _hs(bulletin) if f"à {taux}%" in l["libelle"]) == quantite
    assert not any(l.get("perte") for l in bulletin["calcul_du_brut"])
    assert not bulletin["details_absences"]
    assert not bulletin["details_conges"]
    assert bulletin["salaire_brut"] >= 2500
    assert bulletin["net_a_payer"] > 0
    assert bulletin["cumuls"]["cumuls"]["brut_total"] == bulletin["salaire_brut"]
    assert bulletin["cumuls"]["cumuls"]["heures_supplementaires_remunerees"] == sum(declaration)
    # Recalcul identique, sans consommation ou mouvement lié au repos externe.
    assert _calculer(tmp_path / "recalcul", prevu, reel, declaration) == bulletin
    assert not bulletin.get("modulation_account")


def test_une_absence_sans_solde_reste_retenue_apres_sauvegarde(monkeypatch, tmp_path):
    prevu, reel = _enregistrer(monkeypatch, *_mois(motif="absence_non_remuneree"))
    bulletin = _calculer(tmp_path, prevu, reel, (0, 0))
    assert bulletin["salaire_brut"] < 2500
    assert bulletin["details_absences"]


def test_un_mois_entier_en_repos_ne_devient_pas_une_absence_integrale(monkeypatch, tmp_path):
    prevu, reel = _enregistrer(monkeypatch, *_mois(repos_integral=True))
    bulletin = _calculer(tmp_path, prevu, reel, (0, 0))
    assert bulletin["salaire_brut"] == 2500
    assert not any(l.get("perte") for l in bulletin["calcul_du_brut"])


def test_un_pointage_positif_sur_repos_est_conserve(monkeypatch):
    prevu, reel = _mois(motif="repos")
    reel[5]["heures_faites"] = 2
    prevu, reel = _enregistrer(monkeypatch, prevu, reel)
    assert reel[5]["heures_faites"] == 2


def test_un_zero_importe_attend_son_motif_avant_de_devenir_un_repos(monkeypatch, tmp_path):
    prevu, reel = _mois()
    jours = PersistTimesheetEmployee.model_validate({
        "employee_id": "emp-test",
        "days": [{"jour": 6, "type": "travail", "heures": 0, "nature": "reel"}],
    }).days
    reel = _merge_days(reel, jours, "reel")
    assert reel[5]["heures_faites"] == 0
    assert prevu[5]["type"] == "travail"
    assert not is_day_ready_for_payroll(prevu[5], reel[5])
    # Décision RH explicite, après vérification du suivi externe.
    prevu[5].update(type="repos", heures_prevues=0)
    prevu, reel = _enregistrer(monkeypatch, prevu, reel)
    bulletin = _calculer(tmp_path, prevu, reel, (0, 0))
    assert is_day_ready_for_payroll(prevu[5], reel[5])
    assert bulletin["salaire_brut"] == 2500
    assert not bulletin["details_absences"]


@pytest.mark.parametrize(
    ("compteur_ouvert", "politique", "decision", "declaration"),
    [
        (False, "account_all", None, (3, 0)),
        (True, "pay_all", None, (3, 0)),
        (True, "account_all", {"hours_to_account": 0, "status": "validated"}, (3, 0)),
        (True, "account_all", None, (0, 0)),
    ],
    ids=["compteur-ferme", "tout-payer", "payer-ce-mois", "zero-declare"],
)
def test_le_routage_compatible_avec_le_suivi_externe_ne_recredite_pas_le_repos(
    monkeypatch, tmp_path, compteur_ouvert, politique, decision, declaration,
):
    """Routage réel, puis moteur : pas de nouveau mouvement dans ces configurations.

    Le solde historique du compte n'est ni supprimé ni dupliqué. La décision
    du mois est distincte du réglage de la société ; aucune donnée réelle lue.
    """
    mouvements = [{
        "movement_type": "opening_balance", "hours": 20, "status": "validated",
        "year": 2026, "month": 10, "source": "manual_rh",
    }]
    avant = deepcopy(mouvements)
    monkeypatch.setattr(compte_heures.repo, "get_modulation_settings", lambda _id: ModulationSettings(
        hour_account_enabled=compteur_ouvert, hs_routing_policy=politique,
    ))
    monkeypatch.setattr(compte_heures.repo, "list_movements_for_employee", lambda _id: mouvements)
    monkeypatch.setattr(compte_heures, "_decision_du_mois", lambda *_a: decision)
    insertion = Mock(side_effect=AssertionError("aucun crédit attendu"))
    monkeypatch.setattr(compte_heures.repo, "insert_movement", insertion)
    monkeypatch.setattr(compte_heures, "sync_account_balance_cache", Mock())
    monkeypatch.setattr(compte_heures, "sync_employee_modulation_counter", Mock())
    prevu, reel = _mois(motif="repos")
    evenements = analyser_horaires_du_mois(
        [{**j, "annee": ANNEE, "mois": MOIS} for j in prevu],
        [{**j, "annee": ANNEE, "mois": MOIS} for j in reel],
        35, ANNEE, MOIS, "Salarié synthétique",
    )
    calendrier = [{**e, "date_complete": date(ANNEE, MOIS, e["jour"]).isoformat()} for e in evenements]
    calendrier, ids, resultat = compte_heures.apply_modulation_hour_account_to_calendar(
        "soc-test", "emp-test", ANNEE, MOIS, calendrier,
        bornes_variables=(date(ANNEE, MOIS, 1), date(ANNEE, MOIS, 30)),
        heures_declarees=declaration,
    )
    assert ids == []
    assert resultat.hs_credited == resultat.repos_credite == 0
    insertion.assert_not_called()
    assert mouvements == avant
    bulletin = _calculer(
        tmp_path, prevu, reel,
        resultat.declaration_restante if resultat.declaration_restante is not None else declaration,
        evenements=calendrier,
    )
    assert sum(l["quantite"] for l in _hs(bulletin)) == sum(declaration)
    assert not bulletin["details_absences"]


@pytest.mark.parametrize("forfait", [False, True], ids=["heures", "forfait"])
def test_la_periode_du_maintien_est_imprimee_une_fois_sur_le_pdf(tmp_path, forfait):
    prevu, reel = _mois(motif="repos")
    if forfait:
        prevu = [{**j, "heures_prevues": int(j["type"] == "travail")} for j in prevu]
        reel = [{**j, "heures_faites": int(j["type"] == "travail")} for j in reel]
    libelle = "Rappel de maintien de salaire du 01/10/2026 au 05/10/2026"
    bulletin = _calculer(tmp_path, prevu, reel, forfait=forfait, primes=[{
        "prime_id": "rappel_maintien_salaire", "libelle": libelle,
        "montant": 100, "soumise_a_cotisations": True, "soumise_a_impot": True,
    }])
    ligne = next(l for l in bulletin["calcul_du_brut"] if l.get("libelle") == libelle)
    assert ligne["gain"] == 100
    assert bulletin["en_tete"]["mois"] == MOIS
    templates = payroll_engine_root() / "templates"
    html = Environment(loader=FileSystemLoader(str(templates))).get_template("template_bulletin.html").render(
        vue=construire_vue_bulletin(bulletin),
    )
    pdf = HTML(string=html).write_pdf()
    (tmp_path / f"bulletin-{'forfait' if forfait else 'heures'}.pdf").write_bytes(pdf)
    texte = " ".join(" ".join(page.extract_text().split()) for page in PdfReader(BytesIO(pdf)).pages)
    assert texte.count(libelle) == 1
