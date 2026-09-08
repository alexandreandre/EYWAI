"""Saisie RH directe au calendrier → demande d'absence VALIDÉE auto-créée.

« Une saisie RH enregistre un fait » : les jours CP/RTT posés au planning
deviennent des demandes validées (une par jour), avec les gardes qui
empêchent le double décompte (demande existante — récup modulation comprise —,
jours antérieurs à la reprise bulletin) et l'annulation au retypage.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.absences.application import commands

pytestmark = pytest.mark.unit


def _mock_supabase_validated(rows):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=rows
    )
    return sb


@pytest.fixture()
def harnais(monkeypatch):
    """Monte les doublures communes et capture créations / projections."""
    etat = {
        "crees": [],
        "projections": [],
        "annulees": [],
        "cutoff": None,
        "solde": 25.0,
        "valides": [],
    }

    monkeypatch.setattr(
        commands, "supabase", _mock_supabase_validated(etat["valides"])
    )
    monkeypatch.setattr(
        "app.modules.absences.infrastructure.planning_cp_repository."
        "get_cp_opening_reference_dates",
        lambda ids: {ids[0]: etat["cutoff"]} if etat["cutoff"] else {},
    )
    monkeypatch.setattr(
        commands, "get_cp_solde_restant", lambda _eid: etat["solde"]
    )

    def fake_create(db_data):
        etat["crees"].append(db_data)
        return {**db_data, "id": f"req-{len(etat['crees'])}"}

    monkeypatch.setattr(commands.absence_repository, "create", fake_create)

    def fake_update_calendar(employee_id, days, absence_type, **kw):
        etat["projections"].append(
            {"days": days, "type": absence_type, **kw}
        )

    monkeypatch.setattr(
        commands.calendar_update_provider,
        "update_calendar_from_days",
        fake_update_calendar,
    )
    monkeypatch.setattr(
        commands,
        "update_absence_request_status",
        lambda rid, status, **kw: etat["annulees"].append((rid, status)),
    )
    return etat


class TestCreateAbsencesFromPlanning:
    def test_cree_une_demande_validee_par_jour(self, harnais):
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14, 15], "rtt": [21]},
            photos_avant={"2026-09-14": {"type": "travail", "heures_prevues": 7.0}},
        )

        assert len(harnais["crees"]) == 3
        cp = [c for c in harnais["crees"] if c["type"] == "conge_paye"]
        rtt = [c for c in harnais["crees"] if c["type"] == "rtt"]
        assert [c["selected_days"] for c in cp] == [["2026-09-14"], ["2026-09-15"]]
        assert rtt[0]["selected_days"] == ["2026-09-21"]
        for c in harnais["crees"]:
            assert c["status"] == "validated"
            assert c["workflow_step"] == "approved_rh"
            assert c["comment"].startswith(commands.PLANNING_SOURCE_COMMENT)
        assert all(c["jours_payes"] == 1.0 for c in cp)
        # Projection en mode adoption : le jour est déjà typé par la RH.
        assert all(p["adopter_jours_deja_types"] for p in harnais["projections"])
        codes = [w["code"] for w in warnings]
        assert codes.count("demande_creee_depuis_planning") == 3

    def test_noop_si_demande_validee_couvre_deja_le_jour(self, harnais):
        # Une récup modulation projette AUSSI conges_payes : créer un CP
        # par-dessus double-débiterait (modulation + solde CP).
        harnais["valides"].append(
            {
                "id": "r-1",
                "type": "recuperation_modulation",
                "selected_days": ["2026-09-14"],
            }
        )
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14]},
        )
        assert harnais["crees"] == []
        assert warnings == []

    def test_cp_avant_la_reprise_bulletin_est_laisse_au_calendrier(self, harnais):
        from datetime import date

        # Jour ≤ cutoff : déjà dans le solde d'ouverture repris du bulletin —
        # le matérialiser en demande le compterait deux fois.
        harnais["cutoff"] = date(2026, 8, 31)
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=8,
            jours_par_type={"conges_payes": [17], "rtt": [18]},
        )
        assert [c["type"] for c in harnais["crees"]] == ["rtt"]
        assert [w["code"] for w in warnings if w["code"] == "cp_avant_reprise"] == [
            "cp_avant_reprise"
        ]

    def test_le_pseudo_jour_passe_est_reintegre_au_solde(self, harnais):
        """Le solde affiché décompte DÉJÀ un jour PASSÉ tout juste posé au
        planning (pseudo-CP) : la dernière journée d'un solde juste doit être
        payée 1, pas 0. Solde affiché 0,6 = solde réel 1,6 avant la saisie."""
        from datetime import date

        harnais["solde"] = 0.6
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14]},
            aujourd_hui=date(2026, 9, 20),
        )
        assert harnais["crees"][0]["jours_payes"] == 1.0
        assert not any(w["code"] == "cp_au_dela_du_solde" for w in warnings)

    def test_cp_futur_nest_pas_reintegre(self, harnais):
        """Un jour FUTUR n'est jamais compté comme pris par le solde affiché
        (count_absence_days_taken s'arrête à aujourd'hui) : pas de
        réintégration, sinon un CP posé pour demain à solde nul serait payé
        plein."""
        from datetime import date

        harnais["solde"] = 0.0
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14]},
            aujourd_hui=date(2026, 9, 1),
        )
        assert harnais["crees"][0]["jours_payes"] == 0.0
        assert any(w["code"] == "cp_au_dela_du_solde" for w in warnings)

    def test_solde_insuffisant_clampe_jours_payes_et_previent(self, harnais):
        from datetime import date

        # Jour passé — solde affiché −0,4 après saisie = 0,6 réel : 0,5 payé.
        harnais["solde"] = -0.4
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14]},
            aujourd_hui=date(2026, 9, 20),
        )
        assert harnais["crees"][0]["jours_payes"] == 0.5
        assert any(w["code"] == "cp_au_dela_du_solde" for w in warnings)

    def test_rafale_epuise_le_solde_jour_apres_jour(self, harnais):
        """Deux jours passés posés d'un coup : le solde se décrémente
        localement, chaque journée est payée sur ce qui reste (0,5 puis 0)."""
        from datetime import date

        harnais["solde"] = -1.2  # réel avant saisie : 0,8 pour 2 jours
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14, 15]},
            aujourd_hui=date(2026, 9, 20),
        )
        payes = [c["jours_payes"] for c in harnais["crees"]]
        assert payes == [0.5, 0.0]
        assert (
            sum(1 for w in warnings if w["code"] == "cp_au_dela_du_solde") == 2
        )

    def test_jour_couvert_par_une_demande_dun_autre_type_est_refuse(self, harnais):
        """Un arrêt validé couvre le jour : matérialiser un CP par-dessus
        créerait une double trace (arrêt actif + CP débité) — refus explicite."""
        harnais["valides"].append(
            {
                "id": "r-arret",
                "type": "arret_maladie",
                "selected_days": ["2026-09-14"],
            }
        )
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"conges_payes": [14]},
        )
        assert harnais["crees"] == []
        assert [w["code"] for w in warnings] == ["jour_couvert_par_autre_demande"]

    def test_type_calendrier_inconnu_ignore(self, harnais):
        warnings = commands.create_absences_from_planning(
            "emp-1",
            "comp-1",
            year=2026,
            month=9,
            jours_par_type={"arret_maladie": [3], "absence_non_remuneree": [4]},
        )
        assert harnais["crees"] == []
        assert warnings == []


class TestCancelPlanningAbsences:
    def _requalif(self, jour, type_avant="conges_payes"):
        return {
            "jour": jour,
            "code": "absence_validee_requalifiee",
            "type_avant": type_avant,
            "type_apres": "travail",
        }

    def test_annule_la_demande_planning_dun_jour(self, harnais):
        harnais["valides"].append(
            {
                "id": "r-9",
                "type": "conge_paye",
                "selected_days": ["2026-09-14"],
                "comment": f"{commands.PLANNING_SOURCE_COMMENT} (14/09/2026)",
            }
        )
        warnings = commands.cancel_planning_absences_for_requalified_days(
            "emp-1", year=2026, month=9, requalifications=[self._requalif(14)]
        )
        assert harnais["annulees"] == [("r-9", "cancelled")]
        assert warnings[0]["code"] == "demande_planning_annulee"

    def test_ne_touche_ni_multijour_ni_sans_marqueur(self, harnais):
        harnais["valides"].extend(
            [
                {
                    "id": "r-multi",
                    "type": "conge_paye",
                    "selected_days": ["2026-09-14", "2026-09-15"],
                    "comment": f"{commands.PLANNING_SOURCE_COMMENT} (x)",
                },
                {
                    "id": "r-salarie",
                    "type": "conge_paye",
                    "selected_days": ["2026-09-16"],
                    "comment": "Demande salariée",
                },
            ]
        )
        warnings = commands.cancel_planning_absences_for_requalified_days(
            "emp-1",
            year=2026,
            month=9,
            requalifications=[self._requalif(14), self._requalif(16)],
        )
        assert harnais["annulees"] == []
        assert warnings == []

    def test_ignore_les_types_hors_perimetre(self, harnais):
        warnings = commands.cancel_planning_absences_for_requalified_days(
            "emp-1",
            year=2026,
            month=9,
            requalifications=[self._requalif(3, type_avant="arret_maladie")],
        )
        assert harnais["annulees"] == []
        assert warnings == []
