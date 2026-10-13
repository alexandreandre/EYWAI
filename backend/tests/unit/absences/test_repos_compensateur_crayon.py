"""Repos compensateur : un crayon avec motif pour corriger le compteur.

Comme pour les RTT et les JTC (décision du 12/10/2026) : la gestionnaire saisit
le solde voulu, en heures ; l'outil enregistre l'écart comme un crédit « manual »
du mois, que le bulletin lit avec les autres crédits, et garde le motif. Cas
réel : remettre le compteur à zéro chez Colorplast.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.application import leave_settings_commands as cmd
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment
from app.modules.absences.schemas.leave_settings import EmployeeLeaveSoldeUpdate

pytestmark = pytest.mark.unit


@pytest.fixture()
def harnais(monkeypatch):
    etat = {"solde": 35.0, "deja": 0.0, "credits": [], "ajustements": [], "upsert_ok": True}
    monkeypatch.setattr(cmd, "_ensure_employee_in_company", lambda *a, **k: None)
    monkeypatch.setattr(cmd, "_solde_repos_affiche", lambda _eid: etat["solde"])
    monkeypatch.setattr(cmd, "_correction_repos_du_mois", lambda _eid, _a, _m: etat["deja"])
    monkeypatch.setattr(cmd, "_heures_par_jour_de_repos", lambda _eid: 7.0)

    def _upsert(credit):
        etat["credits"].append(credit)
        return etat["upsert_ok"]

    monkeypatch.setattr(cmd, "upsert_credit", _upsert)
    monkeypatch.setattr(
        cmd, "get_employee_adjustment", lambda _eid, _a: EmployeeLeaveAdjustment(note=None)
    )

    def _upsert_ajustement(company_id, employee_id, year, payload):
        etat["ajustements"].append(payload)
        return {"note": payload.get("note")}

    monkeypatch.setattr(cmd, "upsert_employee_adjustment", _upsert_ajustement)
    return etat


def test_le_schema_accepte_le_repos_compensateur_en_heures():
    corps = EmployeeLeaveSoldeUpdate(compteur="repos_compensateur", solde_cible=0, note="Remise à zéro")
    assert corps.compteur == "repos_compensateur"


def test_remettre_a_zero_ecrit_l_ecart_en_credit_du_mois(harnais):
    annee = date.today().year
    cmd.apply_leave_solde_manual(
        "co-1", "emp-1", annee, compteur="repos_compensateur", solde_cible=0.0, note="Remise à zéro demandée"
    )
    (credit,) = harnais["credits"]
    assert credit.source == "manual"
    assert credit.year == annee and credit.month == date.today().month
    assert credit.heures == -35.0
    assert credit.jours == -5.0
    (ajustement,) = harnais["ajustements"]
    assert "repos compensateur → 0 h" in ajustement["note"]
    assert "Remise à zéro demandée" in ajustement["note"]


def test_une_seconde_correction_du_mois_remplace_la_premiere(harnais):
    # Le solde affiché (10 h) compte déjà une correction de −25 h ce mois-ci.
    harnais["solde"], harnais["deja"] = 10.0, -25.0
    cmd.apply_leave_solde_manual(
        "co-1", "emp-1", date.today().year, compteur="repos_compensateur", solde_cible=4.0
    )
    assert harnais["credits"][0].heures == -31.0


def test_le_motif_est_garde_meme_sans_note(harnais):
    cmd.apply_leave_solde_manual(
        "co-1", "emp-1", date.today().year, compteur="repos_compensateur", solde_cible=0.0
    )
    assert "repos compensateur → 0 h" in harnais["ajustements"][0]["note"]


def test_un_echec_d_ecriture_est_dit(harnais):
    harnais["upsert_ok"] = False
    with pytest.raises(ValueError, match="repos compensateur"):
        cmd.apply_leave_solde_manual(
            "co-1", "emp-1", date.today().year, compteur="repos_compensateur", solde_cible=0.0
        )
    assert harnais["ajustements"] == []
