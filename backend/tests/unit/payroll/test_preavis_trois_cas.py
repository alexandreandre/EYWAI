"""[H1] Préavis : trois cas, et l'écran, le calcul et les documents disent la même chose.

L'écran proposait « Payée (préavis effectué) » par défaut, et le moteur lisait
cette valeur comme une dispense : un préavis travaillé ajoutait un mois
d'indemnité au salaire du mois (bac à sable du 11/10/2026, +2 374,55 € de brut).
L'inverse (« Dispensée … payé ») ne versait rien.

Sources ouvertes le 11/10/2026 :
- Code du travail, art. L1234-5 (Légifrance, version en vigueur depuis le
  01/05/2008) : « Lorsque le salarié n'exécute pas le préavis, il a droit, sauf
  s'il a commis une faute grave, à une indemnité compensatrice. L'inexécution du
  préavis, notamment en cas de dispense par l'employeur, n'entraîne aucune
  diminution des salaires et avantages que le salarié aurait perçus s'il avait
  accompli son travail jusqu'à l'expiration du préavis, indemnité de congés
  payés comprise. »
- service-public.gouv.fr F2883, « Démission d'un salarié » (vérifié le
  08/07/2026) : dispense « À sa demande et après acceptation de l'employeur
  […] Dans ce cas, l'indemnité compensatrice de préavis n'est pas due. Ou à la
  seule initiative de l'employeur. Celui-ci doit néanmoins verser l'indemnité
  compensatrice de préavis. »

Trois cas : préavis exécuté (payé avec le salaire, aucune indemnité), dispense à
l'initiative de l'employeur (indemnité égale à la rémunération qu'aurait perçue
le salarié, pour le temps de préavis restant), dispense à la demande du salarié
acceptée (rien).
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PyPDF2 import PdfReader

from app.modules.employee_exits.schemas.requests import EmployeeExitCreate
from app.modules.payroll.documents.attestation_employeur_generator import _preavis_lines
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.solde_de_tout_compte.cases import demission
from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}


def _salarie(**extra) -> dict:
    return {
        "id": "emp-1",
        "first_name": "Jean",
        "last_name": "Test",
        "hire_date": "2021-08-23",
        "contract_type": "CDI",
        "duree_hebdomadaire": 39,
        "salaire_de_base": {"valeur": 2374.55},
        **extra,
    }


def _depart(type_preavis: str, **extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "demission",
        "exit_request_date": "2026-09-01",
        "last_working_day": "2026-09-30",
        "notice_period_days": 60,
        "notice_start_date": "2026-09-01",
        "notice_end_date": "2026-10-31",
        "notice_indemnity_type": type_preavis,
        **extra,
    }


def _bulletin(mois: int, brut: float) -> dict:
    return {
        "employee_id": "emp-1",
        "year": 2026,
        "month": mois,
        "payslip_data": {
            "salaire_brut": brut,
            "calcul_du_brut": [{"libelle": "Salaire de base", "gain": brut}],
        },
    }


def _base_avec_bulletins() -> BaseEnMemoire:
    # Juin, juillet, août : les trois mois avant celui du dernier jour travaillé.
    return BaseEnMemoire(
        {"payslips": [_bulletin(6, 3100.00), _bulletin(7, 3168.27), _bulletin(8, 3050.00)]}
    )


@patch(_ICCP, return_value=_SANS_ICCP)
def test_un_preavis_execute_est_paye_avec_le_salaire_sans_indemnite(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart("executed"), _base_avec_bulletins())

    assert dossier["indemnite_preavis"]["montant"] == 0.0
    assert dossier["total_gross_indemnities"] == 0.0


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_dispense_a_la_demande_du_salarie_ne_verse_rien(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart("waived"), _base_avec_bulletins())

    assert dossier["indemnite_preavis"]["montant"] == 0.0


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_dispense_par_l_employeur_verse_la_remuneration_du_temps_restant(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart("paid"), _base_avec_bulletins())

    preavis = dossier["indemnite_preavis"]
    # Rémunération qu'il aurait perçue : la moyenne des bruts des trois derniers
    # mois (heures structurelles et primes comprises), pas le salaire de base.
    remuneration = round((3100.00 + 3168.27 + 3050.00) / 3, 2)
    assert preavis["salaire_reference"] == remuneration
    # Préavis du 01/09 au 31/10, dernier jour travaillé le 30/09 : 31 jours restent.
    assert preavis["jours_restants"] == 31
    assert preavis["montant"] == round(remuneration / 30 * 31, 2)
    assert dossier["total_gross_indemnities"] == preavis["montant"]


@patch(_ICCP, return_value=_SANS_ICCP)
def test_sans_bulletin_la_remuneration_est_le_salaire_habituel_et_non_le_salaire_de_base(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart("paid"), BaseEnMemoire({}))

    preavis = dossier["indemnite_preavis"]
    # 39 h : 151,67 h de base et 17,33 h structurelles majorées de 25 %.
    assert preavis["salaire_reference"] > 2374.55
    assert "contrat" in preavis["calcul"]


def test_l_ecran_et_l_api_proposent_par_defaut_un_preavis_execute():
    depart = EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="demission",
        exit_request_date="2026-09-01",
        last_working_day="2026-10-31",
        notice_period_days=60,
    )
    assert depart.notice_indemnity_type == "executed"


_PHRASES = {
    "executed": "Préavis exécuté, payé avec le salaire.",
    "paid": (
        "Préavis non exécuté, dispense à l'initiative de l'employeur : "
        "indemnité compensatrice de préavis versée."
    ),
    "waived": (
        "Préavis non exécuté à la demande du salarié, dispense acceptée : "
        "pas d'indemnité compensatrice."
    ),
}


@pytest.mark.parametrize("type_preavis", sorted(_PHRASES))
def test_l_attestation_france_travail_dit_le_cas_choisi(type_preavis):
    lignes = _preavis_lines(_depart(type_preavis))
    assert _PHRASES[type_preavis] in lignes


@pytest.mark.parametrize("type_preavis", sorted(_PHRASES))
def test_le_certificat_de_travail_dit_le_cas_choisi(type_preavis):
    pdf = EmployeeExitDocumentGenerator().generate_certificat_travail(
        _salarie(job_title="Régleur"),
        {"company_name": "Société Test", "adresse_ville": "Lyon"},
        _depart(type_preavis),
    )
    texte = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert " ".join(_PHRASES[type_preavis].split()) in " ".join(texte.split())


@pytest.mark.parametrize("type_preavis", sorted(_PHRASES))
def test_le_recu_pour_solde_de_tout_compte_dit_le_cas_choisi(type_preavis, monkeypatch):
    sections = {}

    def _capturer(*_a, **k):
        sections["toutes"] = k["sections"]
        return b""

    monkeypatch.setattr(demission, "render_solde_tout_compte_html", _capturer)
    monkeypatch.setattr(
        demission.socle_commun,
        "compute_remunerations_section",
        lambda *a, **k: ({"title": "R", "rows": []}, 0.0, 0.0, 0.0),
    )
    montant = 3200.0 if type_preavis == "paid" else 0.0
    demission.generate_demission_solde(
        {}, _salarie(), {}, _depart(type_preavis), {"indemnite_preavis": {"montant": montant}}
    )
    textes = [
        str(valeur)
        for section in sections["toutes"]
        for ligne in (section.get("rows") or [])
        for valeur in (ligne.values() if isinstance(ligne, dict) else [ligne])
    ]
    assert any(_PHRASES[type_preavis] in t for t in textes), textes
