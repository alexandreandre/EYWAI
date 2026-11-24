"""Bulletin d'un salarié qui suit sa propre règle d'heures sup (Cartol, 20/11/2026).

Routage réel par le compteur, puis moteur réel : un alternant « toujours payé »
dans une société qui met tout au compteur a le même bulletin qu'un salarié
d'une société qui paie ses heures sup ; « toujours au compteur » dans une
société qui paie : aucune heure sup sur le bulletin. Aucune donnée réelle lue.
"""

from datetime import date
from unittest.mock import Mock

import pytest

from app.modules.modulation.application import payroll_hook as compte_heures
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from tests.unit.payroll.test_recuperation_externe_parcours import (
    ANNEE,
    MOIS,
    _calculer,
    _hs,
    _mois,
)

pytestmark = pytest.mark.unit


def _bulletin(monkeypatch, tmp_path, politique, regle_du_salarie):
    monkeypatch.setattr(
        compte_heures.repo, "get_modulation_settings",
        lambda _id: ModulationSettings(hour_account_enabled=True, hs_routing_policy=politique),
    )
    monkeypatch.setattr(compte_heures.repo, "get_hs_routing_override", lambda _id: regle_du_salarie)
    monkeypatch.setattr(compte_heures.repo, "list_movements_for_employee", lambda _id: [])
    monkeypatch.setattr(compte_heures, "_decision_du_mois", lambda *_a: None)
    insertion = Mock(return_value={"id": "mov-1"})
    monkeypatch.setattr(compte_heures.repo, "insert_movement", insertion)
    monkeypatch.setattr(compte_heures, "sync_account_balance_cache", Mock())
    monkeypatch.setattr(compte_heures, "sync_employee_modulation_counter", Mock())
    prevu, reel = _mois(motif="repos")  # 10 h sup : 8 à 25 %, 2 à 50 %.
    evenements = analyser_horaires_du_mois(
        [{**j, "annee": ANNEE, "mois": MOIS} for j in prevu],
        [{**j, "annee": ANNEE, "mois": MOIS} for j in reel],
        35, ANNEE, MOIS, "Salarié synthétique",
    )
    calendrier = [{**e, "date_complete": date(ANNEE, MOIS, e["jour"]).isoformat()} for e in evenements]
    calendrier, _ids, resultat = compte_heures.apply_modulation_hour_account_to_calendar(
        "soc-test", "emp-test", ANNEE, MOIS, calendrier,
        bornes_variables=(date(ANNEE, MOIS, 1), date(ANNEE, MOIS, 30)),
        majorations={"travail_hs25": 0.25, "travail_hs50": 0.5},
    )
    bulletin = _calculer(tmp_path, prevu, reel, evenements=calendrier)
    return bulletin, resultat, insertion


def test_toujours_payees_meme_bulletin_que_dans_une_societe_qui_paie(monkeypatch, tmp_path):
    alternant, resultat, insertion = _bulletin(monkeypatch, tmp_path / "a", "account_all", "pay_all")
    reference, _r, _i = _bulletin(monkeypatch, tmp_path / "b", "pay_all", None)
    assert sum(l["quantite"] for l in _hs(alternant)) == 10
    assert resultat.hs_credited == resultat.repos_credite == 0
    insertion.assert_not_called()
    assert alternant["salaire_brut"] == reference["salaire_brut"]
    assert alternant["net_a_payer"] == reference["net_a_payer"]
    assert _hs(alternant) == _hs(reference)


def test_sans_reglage_le_bulletin_de_la_societe_au_compteur_ne_change_pas(monkeypatch, tmp_path):
    sans_reglage, resultat, insertion = _bulletin(monkeypatch, tmp_path, "account_all", None)
    assert _hs(sans_reglage) == []
    assert resultat.hs_credited == 10
    insertion.assert_called_once()


def test_toujours_au_compteur_dans_une_societe_qui_paie(monkeypatch, tmp_path):
    au_compteur, resultat, insertion = _bulletin(monkeypatch, tmp_path / "a", "pay_all", "account_all")
    societe_au_compteur, _r, _i = _bulletin(monkeypatch, tmp_path / "b", "account_all", None)
    assert _hs(au_compteur) == []
    # 8 h à 25 % et 2 h à 50 % : 13 h de repos.
    assert (resultat.hs_credited, resultat.repos_credite) == (10, 13)
    insertion.assert_called_once()
    assert au_compteur["net_a_payer"] == societe_au_compteur["net_a_payer"]
