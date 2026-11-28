"""L23 (28/11) : les jours travaillés sans heure d'arrivée dits une fois par
salarié, avec les règles concernées.

Avec trois règles « par jour travaillé » qui lisent l'heure d'arrivée (panier
de jour, panier de nuit, prime de nuit), les mêmes jours étaient signalés trois
fois sur le bulletin et dans « Primes du mois ». Une phrase par groupe de jours
identiques, qui nomme les règles ; rien d'autre ne change.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.payroll_variables.application import alertes_paniers as ap
from app.modules.payroll_variables.application import generate_monthly as gm

pytestmark = pytest.mark.unit

PLAGES = {"plages_debut": [{"de": "03:30", "a": "04:30"}]}
SIX = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26"]


def _ligne(eid, regle, dates, aucun_badge=False):
    return {"employee_id": eid, "first_name": "A", "last_name": "B", "rule_label": regle,
            "dates": list(dates), "aucun_badge": aucun_badge}


def _brancher(monkeypatch, lignes):
    repo = MagicMock()
    repo.list_rules.return_value = [
        {"enabled": True, "code": c, "label": l, "rule_type": "per_worked_day", "amount": 7.6, "conditions": PLAGES}
        for c, l in (("pj", "Panier"), ("pn", "Panier de nuit"), ("nuit", "Prime de nuit"))
    ]
    monkeypatch.setattr(gm, "repo", repo)
    monkeypatch.setattr(ap, "jours_sans_heure_d_arrivee", lambda cid, a, m, eid=None: lignes)


class TestRegroupement:
    def test_trois_regles_memes_jours_une_seule_ligne(self):
        lignes = [_ligne("e1", r, SIX) for r in ("Panier", "Panier de nuit", "Prime de nuit")]
        assert ap.regrouper_jours_sans_heure_d_arrivee(lignes) == [
            {"employee_id": "e1", "first_name": "A", "last_name": "B",
             "rule_label": "Panier, Panier de nuit, Prime de nuit",
             "rule_labels": ["Panier", "Panier de nuit", "Prime de nuit"],
             "dates": SIX, "aucun_badge": False}
        ]

    def test_des_jours_differents_gardent_leur_groupe(self):
        lignes = [
            _ligne("e1", "Panier", SIX),
            _ligne("e1", "Panier de nuit", SIX[:2]),
            _ligne("e1", "Prime de nuit", SIX),
            _ligne("e2", "Panier", SIX[:1]),
        ]
        groupes = ap.regrouper_jours_sans_heure_d_arrivee(lignes)
        assert [(g["employee_id"], g["rule_labels"], g["dates"]) for g in groupes] == [
            ("e1", ["Panier", "Prime de nuit"], SIX),
            ("e1", ["Panier de nuit"], SIX[:2]),
            ("e2", ["Panier"], SIX[:1]),
        ]

    def test_aucun_badge_regroupe_de_meme(self):
        lignes = [_ligne("e1", r, SIX, aucun_badge=True) for r in ("Panier", "Prime de nuit")]
        [groupe] = ap.regrouper_jours_sans_heure_d_arrivee(lignes)
        assert groupe["rule_labels"] == ["Panier", "Prime de nuit"] and groupe["aucun_badge"] is True


class TestAlerteDuBulletin:
    def test_une_seule_alerte_qui_nomme_les_regles(self, monkeypatch):
        _brancher(monkeypatch, [_ligne("e1", r, SIX) for r in ("Panier", "Panier de nuit", "Prime de nuit")])
        alertes = ap.alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert [a["message"] for a in alertes] == [
            "Panier, Panier de nuit, Prime de nuit : 6 jours travaillés sans heure d'arrivée "
            "(19/10, 20/10, 21/10, 22/10, 23/10, 26/10) : aucun compté ces jours-là. "
            "Importez les pointages ou saisissez l'heure d'arrivée au calendrier."
        ]
        assert alertes[0]["code"] == "jours_sans_heure_d_arrivee" and alertes[0]["critique"] is False

    def test_une_phrase_par_groupe_de_jours_identiques(self, monkeypatch):
        _brancher(monkeypatch, [
            _ligne("e1", "Panier", SIX[:2]),
            _ligne("e1", "Panier de nuit", SIX[:1]),
            _ligne("e1", "Prime de nuit", SIX[:2]),
        ])
        alertes = ap.alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert [a["message"] for a in alertes] == [
            "Panier, Prime de nuit : 2 jours travaillés sans heure d'arrivée (19/10, 20/10) : "
            "aucun compté ces jours-là. Importez les pointages ou saisissez l'heure d'arrivée au calendrier.",
            "Panier de nuit : 1 jour travaillé sans heure d'arrivée (19/10) : "
            "aucun compté ce jour-là. Importez les pointages ou saisissez l'heure d'arrivée au calendrier.",
        ]

    def test_aucune_heure_sur_la_periode_une_seule_phrase(self, monkeypatch):
        _brancher(monkeypatch, [_ligne("e1", r, SIX, True) for r in ("Panier", "Panier de nuit", "Prime de nuit")])
        alertes = ap.alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert [a["message"] for a in alertes] == [
            "Panier, Panier de nuit, Prime de nuit : aucune heure d'arrivée sur la période "
            "(6 jours travaillés), aucun jour compté : importez les pointages ou saisissez "
            "les heures d'arrivée au calendrier."
        ]

    def test_que_des_paniers_le_dit(self, monkeypatch):
        _brancher(monkeypatch, [_ligne("e1", r, SIX, True) for r in ("Panier", "Panier de nuit")])
        [alerte] = ap.alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert "(6 jours travaillés), aucun panier compté :" in alerte["message"]

    def test_l_alerte_de_montant_reste_a_part(self, monkeypatch):
        _brancher(monkeypatch, [_ligne("e1", r, SIX[:1]) for r in ("Panier", "Prime de nuit")])
        saisie = {"name": "Panier", "description": "Auto: pj", "amount": 121.6, "payroll_quantity": 15}
        alertes = ap.alertes_des_paniers_du_mois("c", "e1", 2026, 10, [saisie])
        assert [a["code"] for a in alertes] == ["jours_sans_heure_d_arrivee", "panier_montant_sans_nombre"]


def test_la_route_rend_une_ligne_par_groupe(monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user
    from app.modules.payroll_variables.api import router as module_router

    app = FastAPI()
    app.include_router(module_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        is_platform_admin=True, active_company_id="c1"
    )
    monkeypatch.setattr(
        module_router,
        "jours_sans_heure_d_arrivee",
        lambda cid, a, m, eid=None: [_ligne("e1", r, SIX[:1]) for r in ("Panier", "Prime de nuit")],
    )
    r = TestClient(app).get("/api/payroll-variables/jours-sans-heure-d-arrivee", params={"year": 2026, "month": 10})
    assert r.status_code == 200
    assert r.json() == [
        {"employee_id": "e1", "first_name": "A", "last_name": "B", "rule_label": "Panier, Prime de nuit",
         "rule_labels": ["Panier", "Prime de nuit"], "dates": SIX[:1], "aucun_badge": False}
    ]
