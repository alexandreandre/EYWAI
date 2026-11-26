"""Congé parental d'éducation : saisie par période, sans migration (retour d'Elsa du 26/11).

Il s'enregistre comme un congé sans solde (`type = sans_solde`) de sous-type
`conge_parental_education` (`event_subtype`, texte libre) : ni nouvelle valeur
d'enum, ni nouvelle valeur de la contrainte `absence_requests_arret_type_check`.
Il dure des mois : il se saisit du … au … (C. trav. L1225-50 : le salarié
informe l'employeur « du point de départ et de la durée »), jamais en
demi-journées. Sa validation pose au planning le motif et les bornes, que le
calendrier affiche, que le moteur relaie jusqu'à la ligne du bulletin et que la
DSN déclare en 632. Il n'ouvre aucun congé payé (L3141-5 ne l'assimile pas).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.modules.absences.application import commands
from app.modules.absences.domain.cp_absences_non_assimilees import (
    jours_non_assimiles_des_demandes,
    mois_perdus_par_absences,
)
from app.modules.absences.schemas.requests import AbsenceRequestCreate
from app.modules.maintenance_settings.schemas.responses import MaintenanceSettings
from app.shared.domain.conge_parental import (
    SOUS_TYPE_CONGE_PARENTAL,
    est_conge_parental,
    periode_de_la_demande,
)

pytestmark = pytest.mark.unit


def _creation(**k):
    return AbsenceRequestCreate(
        employee_id="emp-1",
        type="sans_solde",
        event_subtype=SOUS_TYPE_CONGE_PARENTAL,
        **k,
    )


class TestSaisie:
    def test_se_saisit_par_periode_jours_calendaires_compris(self):
        demande = _creation(date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 31))

        assert demande.est_conge_parental()
        assert len(demande.selected_days) == 31
        assert demande.selected_days[0] == date(2026, 7, 1)
        assert demande.selected_days[-1] == date(2026, 7, 31)

    def test_un_an_de_conge_passe(self):
        """L1225-48 : durée initiale d'un an au plus."""
        demande = _creation(date_debut=date(2026, 7, 1), date_fin=date(2027, 6, 30))
        assert len(demande.selected_days) == 365

    def test_la_fin_prevue_est_obligatoire(self):
        with pytest.raises(ValidationError, match="premier jour ET sa fin prévue"):
            _creation(date_debut=date(2026, 7, 1))

    def test_un_sans_solde_ordinaire_ne_se_saisit_pas_par_periode(self):
        with pytest.raises(ValidationError, match="congé parental"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="sans_solde",
                date_debut=date(2026, 7, 1),
                date_fin=date(2026, 7, 31),
            )

    def test_pas_de_demi_journee(self):
        with pytest.raises(ValidationError, match="journées entières"):
            _creation(
                selected_days=[date(2026, 7, 1)],
                demi_journees={date(2026, 7, 1): "matin"},
            )

    def test_le_sous_type_ne_vaut_que_pour_le_sans_solde(self):
        with pytest.raises(ValidationError, match="ne s'applique qu'à un"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="rtt",
                selected_days=[date(2026, 7, 1)],
                event_subtype=SOUS_TYPE_CONGE_PARENTAL,
            )

    def test_l_evenement_familial_garde_ses_sous_types(self):
        demande = AbsenceRequestCreate(
            employee_id="emp-1",
            type="evenement_familial",
            selected_days=[date(2026, 7, 1)],
            event_subtype="mariage_salarie",
        )
        assert not demande.est_conge_parental()


class TestCreationEtValidation:
    def test_la_creation_enregistre_le_sous_type(self):
        demande = _creation(date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 5))
        with (
            patch.object(commands, "get_employee_company_id", return_value="comp-1"),
            patch.object(commands, "absence_repository") as repo,
        ):
            repo.create.side_effect = lambda d: d
            cree = commands.create_absence_request(demande)

        assert cree["type"] == "sans_solde"
        assert cree["event_subtype"] == SOUS_TYPE_CONGE_PARENTAL
        assert "arret_type" not in cree
        assert cree["selected_days"][0] == "2026-07-01"
        assert cree["selected_days"][-1] == "2026-07-05"

    def test_un_sans_solde_ordinaire_n_a_pas_de_sous_type(self):
        demande = AbsenceRequestCreate(
            employee_id="emp-1", type="sans_solde", selected_days=[date(2026, 7, 1)]
        )
        with (
            patch.object(commands, "get_employee_company_id", return_value="comp-1"),
            patch.object(commands, "absence_repository") as repo,
        ):
            repo.create.side_effect = lambda d: d
            cree = commands.create_absence_request(demande)

        assert "event_subtype" not in cree

    def _valider(self, demande: dict):
        with patch.object(commands, "absence_repository") as repo:
            repo.get_by_id.return_value = demande
            repo.update.return_value = {**demande, "status": "validated"}
            with (
                patch.object(commands, "calendar_update_provider") as cal,
                patch.object(
                    commands,
                    "get_maintenance_settings",
                    return_value=MaintenanceSettings(company_id="comp-1"),
                ),
                patch.object(commands, "resolve_nombre_enfants_employee", return_value=0),
                patch.object(commands, "attendre_calendriers_libres"),
                patch.object(commands, "supabase") as base,
            ):
                commands.update_absence_request_status(
                    demande["id"], "validated", current_user_id="rh-1"
                )
        return cal.update_calendar_from_days.call_args, base

    def test_la_validation_pose_le_motif_et_les_bornes_au_planning(self):
        args, base = self._valider(
            {
                "id": "req-cpe",
                "employee_id": "emp-1",
                "company_id": "comp-1",
                "type": "sans_solde",
                "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
                "status": "pending",
                "selected_days": ["2026-07-01", "2026-07-02", "2027-06-30"],
            }
        )

        assert args.args[2] == "sans_solde"
        assert args.kwargs["motif_absence"] == SOUS_TYPE_CONGE_PARENTAL
        assert args.kwargs["periode_absence"] == {"debut": "2026-07-01", "fin": "2027-06-30"}
        assert args.kwargs["arret_type"] is None
        # Ni subrogation ni lecture de fiche : ce n'est pas un arrêt.
        base.table.assert_not_called()

    def test_un_sans_solde_ordinaire_ne_pose_pas_de_motif(self):
        args, _ = self._valider(
            {
                "id": "req-ss",
                "employee_id": "emp-1",
                "company_id": "comp-1",
                "type": "sans_solde",
                "status": "pending",
                "selected_days": ["2026-07-01"],
            }
        )

        assert "motif_absence" not in args.kwargs


def _provider(monkeypatch, existant):
    from tests.unit.schedules.test_planned_calendar_preservation import (
        _provider_avec_calendrier,
    )

    return _provider_avec_calendrier(monkeypatch, existant)


class TestProjection:
    PERIODE = {"debut": "2026-07-01", "fin": "2027-06-30"}

    def test_les_jours_travailles_deviennent_absence_non_remuneree_avec_motif(self, monkeypatch):
        existant = [
            {"jour": 3, "type": "travail", "heures_prevues": 7.0},
            {"jour": 4, "type": "weekend", "heures_prevues": 0},
        ]
        provider, capture = _provider(monkeypatch, existant)

        provider.update_calendar_from_days(
            "emp-1",
            [date(2026, 7, 3), date(2026, 7, 4)],
            "sans_solde",
            motif_absence=SOUS_TYPE_CONGE_PARENTAL,
            periode_absence=self.PERIODE,
        )

        jour3 = next(e for e in capture["ecrit"] if e["jour"] == 3)
        assert jour3["type"] == "absence_non_remuneree"
        assert jour3["origine"] == "absence"
        assert jour3["motif_absence"] == SOUS_TYPE_CONGE_PARENTAL
        assert jour3["periode_absence"] == self.PERIODE
        assert "arret_type" not in jour3
        jour4 = next(e for e in capture["ecrit"] if e["jour"] == 4)
        assert jour4 == {"jour": 4, "type": "weekend", "heures_prevues": 0}

    def test_mois_non_planifie(self, monkeypatch):
        provider, capture = _provider(monkeypatch, None)

        provider.update_calendar_from_days(
            "emp-1",
            [date(2026, 7, d) for d in range(1, 32)],
            "sans_solde",
            motif_absence=SOUS_TYPE_CONGE_PARENTAL,
            periode_absence=self.PERIODE,
        )

        ouvres = [e for e in capture["ecrit"] if date(2026, 7, e["jour"]).weekday() < 5]
        assert ouvres and all(e["motif_absence"] == SOUS_TYPE_CONGE_PARENTAL for e in ouvres)
        assert all(e["type"] == "absence_non_remuneree" for e in ouvres)

    def test_l_annulation_purge_le_motif(self, monkeypatch):
        existant = [
            {
                "jour": 3,
                "type": "absence_non_remuneree",
                "heures_prevues": 0,
                "origine": "absence",
                "motif_absence": SOUS_TYPE_CONGE_PARENTAL,
                "periode_absence": self.PERIODE,
                "entree_avant_absence": {"type": "travail", "heures_prevues": 7.0},
            }
        ]
        provider, capture = _provider(monkeypatch, existant)

        provider.restore_calendar_from_days("emp-1", [date(2026, 7, 3)], "sans_solde")

        jour3 = capture["ecrit"][0]
        assert jour3["type"] == "travail"
        assert "motif_absence" not in jour3 and "periode_absence" not in jour3

    def test_une_ecriture_de_planning_ne_peut_pas_fabriquer_un_conge_parental(self):
        from app.modules.schedules.domain.rules import merge_planned_entries

        stocke = [{"jour": 3, "type": "travail", "heures_prevues": 7.0}]
        entrant = [
            {
                "jour": 3,
                "type": "absence_non_remuneree",
                "heures_prevues": 0,
                "motif_absence": SOUS_TYPE_CONGE_PARENTAL,
            }
        ]
        fusion = merge_planned_entries(stocke, entrant)
        assert "motif_absence" not in fusion[0]


class TestCongesPayes:
    def test_aucun_conge_paye_acquis_pendant_le_conge(self):
        """L3141-5 n'assimile pas le congé parental : un mois entier de congé
        parental fait perdre un mois d'acquisition, comme un sans solde."""
        demande = {
            "type": "sans_solde",
            "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
            "status": "validated",
            "selected_days": [date(2026, 11, d).isoformat() for d in range(1, 31)],
        }
        jours = jours_non_assimiles_des_demandes([demande])

        assert date(2026, 11, 2) in jours
        perte = mois_perdus_par_absences(
            jours, debut=date(2026, 6, 1), fin=date(2026, 11, 30)
        )
        assert perte == pytest.approx(1.0)


def test_reconnaissance_et_bornes():
    assert est_conge_parental({"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL})
    assert not est_conge_parental({"type": "sans_solde"})
    assert not est_conge_parental({"type": "rtt", "event_subtype": SOUS_TYPE_CONGE_PARENTAL})
    assert periode_de_la_demande(["2026-07-03", "2026-07-01"]) == {
        "debut": "2026-07-01",
        "fin": "2026-07-03",
    }
    assert periode_de_la_demande([]) is None


def test_le_compteur_sans_solde_n_inclut_pas_le_conge_parental():
    from app.modules.absences.application import queries
    from app.modules.absences.domain.rules import count_absence_days_taken

    demandes = [
        {"type": "sans_solde", "selected_days": ["2026-07-01"]},
        {
            "type": "sans_solde",
            "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
            "selected_days": ["2026-07-02", "2026-07-03"],
        },
    ]
    filtrees = [r for r in demandes if not queries.est_conge_parental(r)]
    assert count_absence_days_taken(filtrees, "sans_solde", date(2026, 12, 31)) == 1


class TestChevauchement:
    def _creer(self, demande, existantes):
        with (
            patch.object(commands, "get_employee_company_id", return_value="comp-1"),
            patch.object(commands, "absence_repository") as repo,
        ):
            repo.list_by_employee_id.return_value = existantes
            repo.create.side_effect = lambda d: d
            return commands.create_absence_request(demande)

    def test_un_conge_parental_ne_recouvre_pas_un_sans_solde(self):
        existante = {"type": "sans_solde", "status": "validated", "selected_days": ["2026-07-03"]}
        with pytest.raises(ValueError, match="recouvrent un congé sans solde"):
            self._creer(_creation(date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 31)), [existante])

    def test_un_sans_solde_ne_recouvre_pas_un_conge_parental(self):
        existante = {
            "type": "sans_solde",
            "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
            "status": "validated",
            "selected_days": ["2026-07-01", "2026-07-02"],
        }
        demande = AbsenceRequestCreate(
            employee_id="emp-1", type="sans_solde", selected_days=[date(2026, 7, 2)]
        )
        with pytest.raises(ValueError, match="congé parental d'éducation déjà posé"):
            self._creer(demande, [existante])

    def test_annule_ou_hors_dates_ne_gene_pas(self):
        existantes = [
            {"type": "sans_solde", "status": "cancelled", "selected_days": ["2026-07-03"]},
            {"type": "sans_solde", "status": "validated", "selected_days": ["2026-08-03"]},
        ]
        cree = self._creer(_creation(date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 31)), existantes)
        assert cree["event_subtype"] == SOUS_TYPE_CONGE_PARENTAL

    def test_deux_sans_solde_ordinaires_restent_permis(self):
        existante = {"type": "sans_solde", "status": "validated", "selected_days": ["2026-07-03"]}
        demande = AbsenceRequestCreate(
            employee_id="emp-1", type="sans_solde", selected_days=[date(2026, 7, 3)]
        )
        assert self._creer(demande, [existante])["type"] == "sans_solde"


def test_changer_la_fin_prevue_ne_met_pas_les_mois_payes_a_recalculer():
    from app.modules.payroll.application.empreinte_entrees_service import _avec_source_absence

    jour = {
        "jour": 3,
        "type": "absence_non_remuneree",
        "heures_prevues": 0,
        "motif_absence": SOUS_TYPE_CONGE_PARENTAL,
        "periode_absence": {"debut": "2026-07-01", "fin": "2027-06-30"},
    }
    prolonge = {**jour, "periode_absence": {"debut": "2026-07-01", "fin": "2027-12-31"}}
    assert _avec_source_absence([jour], [], 2026, 7) == _avec_source_absence([prolonge], [], 2026, 7)
