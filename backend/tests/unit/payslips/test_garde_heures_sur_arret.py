"""Garde de génération : des heures saisies un jour d'arrêt bloquent le bulletin.

Constat du 30/09/2026 : une salariée en arrêt tout septembre gardait des heures
pointées sur douze jours, que le moteur payait en heures sup (70,75 h à 50 %).
La génération refuse (422 `heures_sur_jour_d_arret`) tant qu'un jour de la
période est dans ce cas ; aucun forçage ne la passe, la seule sortie est une
correction. Le bac à sable, lui, calcule quand même : il ne passe pas par
cette garde, comme pour le calendrier incomplet.

Supabase est toujours moqué.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payslips.application.commands import generate_payslip
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipHeuresSurArretError,
)
from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

_SERVICE = "app.modules.schedules.application.periode_a_saisir_service"
_COMMANDS = "app.modules.payslips.application.commands"

_SALARIEE = {
    "id": "emp-1",
    "company_id": "co-1",
    "first_name": "Octavie",
    "employment_status": "actif",
    "hire_date": "2020-01-15",
    "nir": "2850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Paris"},
    "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
    "salaire_de_base": {"montant": 2500},
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
}


def _arret_de_septembre(heures_sur: dict[int, float]) -> dict:
    """Arrêt validé sur tous les jours ouvrés de septembre 2026 ; réel pointé à la main."""
    prevu, reel = [], []
    for jour in range(1, 31):
        if date(2026, 9, jour).weekday() >= 5:
            prevu.append({"jour": jour, "type": "weekend", "heures_prevues": 0.0})
            continue
        prevu.append(
            {
                "jour": jour,
                "type": "arret_maladie",
                "heures_prevues": 0.0,
                "origine": "absence",
                "arret_type": "maladie_simple",
            }
        )
        reel.append({"jour": jour, "type": "travail", "heures_faites": heures_sur.get(jour, 0.0)})
    return {
        "planned_calendar": {"calendrier_prevu": prevu},
        "actual_hours": {"calendrier_reel": reel},
    }


@contextmanager
def _generation(
    schedule_row: dict,
    *,
    statut: str = "Non-Cadre",
    employee: dict | None = None,
    arrets: list[dict] | None = None,
):
    """Tout ce que la génération lit, moqué ; rend la doublure du générateur."""
    with ExitStack() as pile:
        mock_repo = pile.enter_context(patch(f"{_COMMANDS}._employee_repository"))
        mock_repo.get_by_id_only.return_value = dict(employee or _SALARIEE)
        mock_reader = pile.enter_context(patch(f"{_COMMANDS}.employee_statut_reader"))
        mock_reader.get_employee_statut.return_value = statut
        mock_provider = pile.enter_context(patch(f"{_COMMANDS}.payslip_generator_provider"))
        mock_provider.generate_heures.return_value = {
            "status": "success",
            "message": "OK",
            "download_url": "u",
        }
        mock_provider.generate_forfait.return_value = mock_provider.generate_heures.return_value
        pile.enter_context(patch(f"{_COMMANDS}._fetch_existing_payslip", return_value=None))
        pile.enter_context(
            patch(
                f"{_SERVICE}.resoudre_fenetre_variables",
                return_value=FenetreVariables(
                    debut=date(2026, 9, 1), fin=date(2026, 9, 30), origine="regle"
                ),
            )
        )
        mock_sched = pile.enter_context(patch(f"{_SERVICE}.schedule_repository"))
        mock_sched.list_schedules_for_employees.side_effect = lambda ids, y, m: (
            {"emp-1": schedule_row} if (y, m) == (2026, 9) else {}
        )
        mock_arrets = pile.enter_context(patch(f"{_SERVICE}.arrets_valides_reader"))
        mock_arrets.par_salarie.return_value = {"emp-1": arrets or []}
        yield mock_provider


class TestGardeHeuresSurJourDArret:
    def test_des_heures_sur_des_jours_d_arret_refusent_la_generation(self):
        row = _arret_de_septembre({7: 9.0, 8: 8.0, 9: 7.75})
        with _generation(row) as generateur:
            with pytest.raises(PayslipHeuresSurArretError) as exc:
                generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

        generateur.generate_heures.assert_not_called()
        generateur.generate_forfait.assert_not_called()
        assert exc.value.code == "heures_sur_jour_d_arret"
        assert str(exc.value) == (
            "Octavie est en arrêt, mais des heures sont saisies les 7, 8 et 9 septembre."
        )
        assert exc.value.details == {
            "jours": [
                {"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0},
                {"annee": 2026, "mois": 9, "jour": 8, "heures": 8.0},
                {"annee": 2026, "mois": 9, "jour": 9, "heures": 7.75},
            ]
        }

    def test_aucun_forcage_ne_passe_la_garde(self):
        row = _arret_de_septembre({7: 9.0})
        cmd = GeneratePayslipInput(
            employee_id="emp-1",
            year=2026,
            month=9,
            force_calendrier_incomplet=True,
            regenerer_bulletin_valide=True,
        )
        with _generation(row) as generateur:
            with pytest.raises(PayslipHeuresSurArretError):
                generate_payslip(cmd)

        generateur.generate_heures.assert_not_called()

    def test_le_forfait_jour_est_garde_aussi(self):
        """Un jour d'arrêt marqué travaillé efface l'arrêt du bulletin forfait de la même façon."""
        row = _arret_de_septembre({7: 1.0})
        salariee = {**_SALARIEE, "statut": "Cadre forfait jour", "is_forfait_jour": True}
        with _generation(row, statut="Cadre forfait jour", employee=salariee) as generateur:
            with pytest.raises(PayslipHeuresSurArretError):
                generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

        generateur.generate_forfait.assert_not_called()

    def test_une_absence_qui_n_est_pas_un_arret_est_nommee(self):
        row = _arret_de_septembre({})
        prevu = row["planned_calendar"]["calendrier_prevu"]
        prevu[20] = {"jour": 21, "type": "conges_payes", "heures_prevues": 0.0}
        for entree in row["actual_hours"]["calendrier_reel"]:
            if entree["jour"] == 21:
                entree["heures_faites"] = 8.0
        with _generation(row):
            with pytest.raises(PayslipHeuresSurArretError) as exc:
                generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

        assert str(exc.value) == (
            "Octavie a une absence (congés payés), mais des heures sont saisies "
            "le 21 septembre."
        )

    def test_des_heures_un_samedi_d_arret_valide_refusent_aussi(self):
        """La validation d'un arrêt ne retype pas ses week-ends : l'arrêt validé
        dit que le samedi 12 est couvert."""
        row = _arret_de_septembre({})
        row["actual_hours"]["calendrier_reel"].append(
            {"jour": 12, "type": "travail", "heures_faites": 5.0}
        )
        arret = {
            "type": "arret_maladie",
            "status": "validated",
            "selected_days": [f"2026-09-{j:02d}" for j in range(1, 31)],
        }
        with _generation(row, arrets=[arret]) as generateur:
            with pytest.raises(PayslipHeuresSurArretError) as exc:
                generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

        generateur.generate_heures.assert_not_called()
        assert str(exc.value) == (
            "Octavie est en arrêt, mais des heures sont saisies le 12 septembre."
        )
        assert exc.value.details["jours"] == [
            {"annee": 2026, "mois": 9, "jour": 12, "heures": 5.0}
        ]

    def test_un_samedi_travaille_hors_arret_se_genere(self):
        row = _arret_de_septembre({})
        row["actual_hours"]["calendrier_reel"].append(
            {"jour": 12, "type": "travail", "heures_faites": 5.0}
        )
        arret = {"type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-11"]}
        with _generation(row, arrets=[arret]) as generateur:
            generate_payslip(GeneratePayslipInput(employee_id="emp-1", year=2026, month=9))

        generateur.generate_heures.assert_called_once()

    def test_un_arret_sans_heures_se_genere(self):
        with _generation(_arret_de_septembre({})) as generateur:
            result = generate_payslip(
                GeneratePayslipInput(employee_id="emp-1", year=2026, month=9)
            )

        generateur.generate_heures.assert_called_once()
        assert result.status == "success"


class TestLeBacASableCalculeQuandMeme:
    def test_le_calcul_a_blanc_ne_passe_pas_par_la_garde(self):
        """L'étape suivante vérifie à blanc que le moteur écarte ces heures :
        le bac à sable ne doit pas être bloqué par la garde de génération."""
        from app.modules.payslips.infrastructure.providers import (
            payslip_generator_provider,
        )

        with (
            patch(
                "app.modules.payslips.infrastructure.providers.employee_statut_reader"
            ) as reader,
            patch(
                "app.modules.payslips.infrastructure.providers.process_payslip_generation",
                return_value={"status": "success", "payslip_data": {}},
            ) as calcul,
            patch(f"{_SERVICE}.charger_periodes_a_saisir") as garde,
        ):
            reader.get_employee_statut.return_value = "Non-Cadre"
            payslip_generator_provider.generate_en_bac_a_sable("emp-1", 2026, 9)

        calcul.assert_called_once()
        garde.assert_not_called()


class TestRoute422HeuresSurJourDArret:
    def _rh_user(self):
        from app.modules.users.schemas.responses import CompanyAccess, User

        return User(
            id="user-rh-1",
            email="rh@test.co",
            first_name="R",
            last_name="H",
            is_platform_admin=False,
            is_group_admin=False,
            accessible_companies=[
                CompanyAccess(company_id="co-1", company_name="Co", role="rh", is_primary=True)
            ],
            active_company_id="co-1",
        )

    def test_la_route_rend_422_avec_code_message_et_jours(self, client: TestClient):
        from app.core.security import get_current_user

        jours = [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]
        erreur = PayslipHeuresSurArretError(
            "Octavie est en arrêt, mais des heures sont saisies le 7 septembre.",
            {"jours": jours},
        )
        with (
            patch("app.modules.payslips.api.router.generate_payslip", side_effect=erreur),
            patch(
                "app.modules.payslips.api.router.access_control_service.require_employee_access"
            ),
        ):
            app.dependency_overrides[get_current_user] = self._rh_user
            try:
                response = client.post(
                    "/api/actions/generate-payslip",
                    json={
                        "employee_id": "emp-1",
                        "year": 2026,
                        "month": 9,
                        "force_calendrier_incomplet": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422
        assert response.json()["detail"] == {
            "code": "heures_sur_jour_d_arret",
            "message": "Octavie est en arrêt, mais des heures sont saisies le 7 septembre.",
            "jours": jours,
        }
