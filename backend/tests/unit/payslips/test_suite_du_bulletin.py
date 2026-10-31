"""Le recalcul suit la chaîne des cumuls : le mois suivant qui en part.

Une prime ajoutée en septembre après coup ne mettait que septembre « À
recalculer » ; octobre ne le devenait qu'une fois septembre recalculé, et
« Recalculer tout ce qui a changé » demandait un clic par mois (relevé J.1 du
12/10/2026). Après un recalcul dont les cumuls ont bougé, le serveur nomme le
mois suivant qui en part : un brouillon est recalculé dans le même geste, un
validé est signalé et laissé tel quel.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.payslips.application import suite_du_bulletin as suite
from app.modules.payslips.application.dto import GeneratePayslipInput


def _bulletin(status="brouillon", origine="calcule", brut=2450.0, net=1932.0):
    return {
        "year": 2026,
        "month": 10,
        "status": status,
        "origine": origine,
        "payslip_data": {
            "salaire_brut": brut,
            "net_a_payer": net,
            "calcul_du_brut": [
                {"libelle": "Heures suppl. majorées à 25%", "quantite": 17.33},
            ],
        },
    }


def _etat(cumuls_changes):
    return SimpleNamespace(cumuls_precedents_changes=cumuls_changes)


@pytest.fixture
def lectures(monkeypatch):
    vues: dict = {"bulletin": _bulletin(), "etat": _etat(True), "lus": []}

    def lire(employee_id, year, month):
        vues["lus"].append((employee_id, year, month))
        return vues["bulletin"]

    monkeypatch.setattr(suite, "_lire_bulletin_du_mois", lire)
    monkeypatch.setattr(suite, "_etat_du_mois", lambda e, y, m: vues["etat"])
    return vues


def test_un_brouillon_qui_part_des_cumuls_changes_est_a_recalculer(lectures):
    mois = suite.mois_suivant_a_recalculer("e1", 2026, 9)
    assert mois is not None
    assert (mois.year, mois.month, mois.valide) == (2026, 10, False)
    # Les montants d'avant : le message de fin compare avant → après.
    assert mois.montants == {"heures_sup": 17.33, "salaire_brut": 2450.0, "net_a_payer": 1932.0}
    assert lectures["lus"] == [("e1", 2026, 10)]


def test_decembre_mene_a_janvier_de_l_annee_suivante(lectures):
    suite.mois_suivant_a_recalculer("e1", 2026, 12)
    assert lectures["lus"] == [("e1", 2027, 1)]


def test_un_bulletin_valide_est_signale_pas_recalcule(lectures):
    lectures["bulletin"] = _bulletin(status="valide")
    mois = suite.mois_suivant_a_recalculer("e1", 2026, 9)
    assert mois is not None and mois.valide


@pytest.mark.parametrize(
    "bulletin, etat",
    [
        (None, _etat(True)),  # pas de bulletin le mois suivant
        (_bulletin(origine="importe"), _etat(True)),  # repris de l'ancien logiciel
        (_bulletin(), _etat(False)),  # cumuls inchangés (ou premier mois d'un contrat)
        (_bulletin(), _etat(None)),  # bulletin d'avant l'empreinte : on ne sait pas
        (_bulletin(), None),  # état illisible
    ],
)
def test_rien_a_suivre(lectures, bulletin, etat):
    lectures["bulletin"] = bulletin
    lectures["etat"] = etat
    assert suite.mois_suivant_a_recalculer("e1", 2026, 9) is None


def test_une_lecture_en_echec_ne_casse_pas_la_generation(monkeypatch):
    def en_panne(*a):
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(suite, "_lire_bulletin_du_mois", en_panne)
    assert suite.mois_suivant_a_recalculer("e1", 2026, 9) is None


def test_la_phrase_du_valide_nomme_le_mois_et_ne_ment_pas():
    phrase = suite.phrase_mois_suivant_valide(2026, 10)
    assert "10/2026" in phrase
    assert "validé" in phrase
    assert "pas été recalculé" in phrase


# --- La génération rend la suite ---------------------------------------------


def _generer(monkeypatch, *, statut="success", mois_suivant=None):
    from app.modules.payslips.application import commands

    monkeypatch.setattr(commands, "_periode_a_saisir", lambda *a: None)
    monkeypatch.setattr(commands, "_check_heures_sur_jour_d_arret", lambda *a: None)
    monkeypatch.setattr(commands, "_check_calendar_guard", lambda *a: None)
    monkeypatch.setattr(commands, "_check_validated_guard", lambda cmd: None)
    monkeypatch.setattr(commands, "_signaler_documents_de_sortie", lambda *a: None)
    monkeypatch.setattr(
        commands.employee_statut_reader, "get_employee_statut", lambda _id: "Non-Cadre"
    )
    appels = []

    def suivant(employee_id, year, month):
        appels.append((employee_id, year, month))
        return mois_suivant

    monkeypatch.setattr(commands, "mois_suivant_a_recalculer", suivant)
    with patch.object(commands, "payslip_generator_provider") as provider:
        provider.generate_heures.return_value = {
            "status": statut,
            "message": "ok",
            "download_url": "",
            "payslip_id": "p9",
        }
        resultat = commands._generer_sous_verrou(
            GeneratePayslipInput(employee_id="e1", year=2026, month=9), {"id": "e1"}
        )
    return resultat, appels


def test_la_generation_rend_le_brouillon_suivant_a_recalculer(monkeypatch):
    octobre = suite.MoisSuivant(2026, 10, False, {"heures_sup": 0.0, "salaire_brut": 2450.0, "net_a_payer": 1932.0})
    resultat, appels = _generer(monkeypatch, mois_suivant=octobre)
    assert appels == [("e1", 2026, 9)]
    assert resultat.mois_suivant_a_recalculer == {
        "year": 2026,
        "month": 10,
        "heures_sup": 0.0,
        "salaire_brut": 2450.0,
        "net_a_payer": 1932.0,
    }
    assert not resultat.warnings


def test_un_valide_suivant_est_signale_en_point_a_arbitrer(monkeypatch):
    octobre = suite.MoisSuivant(2026, 10, True, {})
    resultat, _ = _generer(monkeypatch, mois_suivant=octobre)
    assert resultat.mois_suivant_a_recalculer is None
    assert resultat.warnings == [
        {
            "code": "mois_suivant_valide",
            "severity": "info",
            "message": suite.phrase_mois_suivant_valide(2026, 10),
        }
    ]


def test_une_generation_en_echec_ne_cherche_pas_la_suite(monkeypatch):
    resultat, appels = _generer(monkeypatch, statut="error")
    assert appels == []
    assert resultat.mois_suivant_a_recalculer is None


def test_la_route_rend_la_suite(monkeypatch):
    from app.modules.payslips.api import router
    from app.modules.payslips.application.dto import GeneratePayslipResult

    rendu = GeneratePayslipResult(
        status="success",
        message="ok",
        download_url="",
        mois_suivant_a_recalculer={"year": 2026, "month": 10},
    )
    monkeypatch.setattr(router, "generate_payslip", lambda cmd: rendu)
    monkeypatch.setattr(router, "_require_rh_company_context", lambda user: "c1")
    monkeypatch.setattr(
        router.access_control_service, "require_employee_access", lambda *a, **k: None
    )
    utilisateur = SimpleNamespace(id="u1", first_name="A", last_name="B", is_platform_admin=False)
    reponse = router.generate_payslip_route(
        router.PayslipRequest(employee_id="e1", year=2026, month=9), utilisateur
    )
    assert reponse["mois_suivant_a_recalculer"] == {"year": 2026, "month": 10}
