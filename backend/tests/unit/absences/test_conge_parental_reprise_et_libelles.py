"""Congé parental d'éducation : reprise DSN (632), libellés de l'export et du
tableau de bord, régularisation antérieure (retours du coordinateur, 26/11)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.shared.domain.conge_parental import SOUS_TYPE_CONGE_PARENTAL

pytestmark = pytest.mark.unit


def _suspension(motif: str):
    return SimpleNamespace(motif=motif, date_debut="01092026", date_fin="30092026")


class TestRepriseDsn:
    def test_le_632_se_reprend_en_conge_parental(self):
        from app.modules.dsn_import.domain.dsn_absence_exit_mapping import (
            build_absence_payload_from_suspension,
        )

        payload = build_absence_payload_from_suspension(
            _suspension("632"), siret="1", nir="2", employee_label="salariée A"
        )
        assert payload["absence_type"] == "sans_solde"
        assert payload["event_subtype"] == SOUS_TYPE_CONGE_PARENTAL
        assert payload["date_debut"] == "2026-09-01" and payload["date_fin"] == "2026-09-30"

    def test_le_501_reste_un_sans_solde_ordinaire(self):
        from app.modules.dsn_import.domain.dsn_absence_exit_mapping import (
            build_absence_payload_from_suspension,
        )

        payload = build_absence_payload_from_suspension(
            _suspension("501"), siret="1", nir="2", employee_label="salariée A"
        )
        assert payload["absence_type"] == "sans_solde"
        assert "event_subtype" not in payload

    def test_la_reprise_enregistre_le_sous_type_et_pose_le_motif(self):
        from app.modules.absences.application import commands

        base = MagicMock()
        base.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "e-1", "company_id": "c-1", "employment_status": "actif"
        }
        base.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        with (
            patch.object(commands, "absence_repository") as repo,
            patch.object(commands, "calendar_update_provider") as cal,
        ):
            repo.create.side_effect = lambda d: {**d, "id": "nouvelle"}
            repo.list_by_employee_id.return_value = []
            cree = commands.create_reconciliation_absence(
                "e-1", "c-1", "u-1",
                absence_type="sans_solde",
                selected_days=["2026-09-01", "2026-09-02"],
                supabase_client=base,
                event_subtype=SOUS_TYPE_CONGE_PARENTAL,
            )
        assert cree["event_subtype"] == SOUS_TYPE_CONGE_PARENTAL
        kwargs = cal.update_calendar_from_days.call_args.kwargs
        assert kwargs["motif_absence"] == SOUS_TYPE_CONGE_PARENTAL
        assert kwargs["periode_absence"] == {"debut": "2026-09-01", "fin": "2026-09-02"}


def test_l_export_des_conges_nomme_le_conge_parental(monkeypatch):
    from app.modules.exports.infrastructure import export_conges_absences as mod

    lignes = [
        {"id": "1", "employee_id": "e", "type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
         "status": "validated", "selected_days": ["2026-11-02"], "employee": {}},
        {"id": "2", "employee_id": "e", "type": "sans_solde", "status": "validated",
         "selected_days": ["2026-11-03"], "employee": {}},
    ]
    requete = MagicMock()
    requete.select.return_value = requete
    requete.eq.return_value = requete
    requete.in_.return_value = requete
    requete.order.return_value.execute.return_value.data = lignes
    base = MagicMock()
    base.table.return_value = requete
    monkeypatch.setattr(mod, "supabase", base)
    sortie = mod.get_absences_for_export("c-1", "2026-11")
    assert [r["type_label"] for r in sortie] == ["Congé parental d'éducation", "Sans solde"]


def test_le_tableau_de_bord_nomme_le_conge_parental():
    from app.modules.dashboard.infrastructure.mappers import to_team_pulse_employees

    emp = {"id": "e", "first_name": "A", "last_name": "B"}
    sortie = to_team_pulse_employees([
        {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "employee": emp},
        {"type": "sans_solde", "employee": emp},
    ])
    assert [s.status for s in sortie] == ["Congé parental d'éducation", "Sans Solde"]


def test_une_regularisation_de_conge_parental_dit_son_nom_et_sort_en_632(monkeypatch):
    from app.modules.dsn_export.domain.evenements import suspensions_du_bulletin
    from app.modules.payroll.documents.payslip_generator import (
        marquer_les_regularisations_du_conge_parental,
    )
    from app.modules.payroll.engine import calcul_brut as cb
    from tests.unit.payroll.helpers import build_test_contexte

    demandes = [{"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "status": "validated",
                 "selected_days": ["2026-10-26", "2027-08-25"]}]
    regul = marquer_les_regularisations_du_conge_parental(
        [
            {"date_complete": "2026-10-29", "type": "absence_non_remuneree", "heures": 7.0,
             "is_regularisation_anterieure": True},
            {"date_complete": "2026-10-30", "type": "absence_non_remuneree", "heures": 7.0,
             "is_regularisation_anterieure": True},
            {"date_complete": "2026-09-10", "type": "absence_non_remuneree", "heures": 7.0,
             "is_regularisation_anterieure": True},
        ],
        demandes,
    )
    assert "motif_absence" not in regul[2]
    monkeypatch.setattr(cb, "coefficient_horaire_reel", lambda *_: 1.0)
    contexte = build_test_contexte(salaire_base=1870.83, duree_hebdo=35.0, date_entree="2020-01-06")
    resultat = cb.calculer_salaire_brut(contexte, regul, date(2026, 11, 1), date(2026, 11, 30), [])
    libelles = [l["libelle"] for l in resultat["lignes_composants_brut"] if l.get("perte")]
    assert "Absence congé parental du 29/10/26 au 31/10/26" in libelles
    assert "Absence non rémunérée du 10/09/26" in libelles
    motifs = {m for m, _, _ in suspensions_du_bulletin({"calcul_du_brut": resultat["lignes_composants_brut"]})}
    assert motifs == {"632", "501"}
