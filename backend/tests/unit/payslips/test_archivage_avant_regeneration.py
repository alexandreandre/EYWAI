"""
Régénérer un bulletin n'écrase jamais la version précédente sans la garder.

L'archivage existait, mais ne se déclenchait que pour un bulletin **validé**.
Or aucun des 1 308 bulletins de la plateforme ne l'est : en pratique il n'a
jamais joué. Le 26/08/2026, une régénération de routine sur Colorplast a
réécrit les bulletins de janvier à mai sans laisser de trace — mai est passé de
7 salariés convergents à 2, sans retour possible.

Tant que la paie est en transition, on ne verrouille pas la régénération : on
garde simplement la version d'avant. Le filet, pas la barrière.
"""

from __future__ import annotations

from unittest.mock import patch

from app.modules.payslips.application.commands import generate_payslip
from app.modules.payslips.application.dto import GeneratePayslipInput

#: Fiche complète : la génération refuse d'emblée une fiche paie incomplète,
#: et ce test porte sur l'archivage, pas sur cette garde-là.
EMPLOYEE = {
    "id": "emp-1",
    "company_id": "co-1",
    "employment_status": "actif",
    "hire_date": "2020-01-15",
    "nir": "1850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Paris"},
    "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
    "salaire_de_base": {"montant": 2500},
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
}


class TestArchivageAvantRegeneration:
    def _lancer(self, existant: dict | None):
        """Génère un bulletin en présence (ou non) d'un bulletin existant."""
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=5)
        with (
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as repo,
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ),
            patch(
                "app.modules.payslips.application.commands._calendar_row_status",
                return_value="saisi",
            ),
            patch(
                "app.modules.payslips.application.commands._fetch_existing_payslip",
                return_value=existant,
            ),
            patch(
                "app.modules.payslips.application.commands._archive_before_regeneration"
            ) as archive,
        ):
            repo.get_by_id_only.return_value = dict(EMPLOYEE)
            reader.get_employee_statut.return_value = "Non-Cadre"
            try:
                generate_payslip(cmd)
            except Exception:
                # Le générateur est une doublure : seul l'appel à l'archivage
                # nous intéresse, pas la suite de la chaîne.
                pass
            return archive

    def test_un_brouillon_existant_est_archive_avant_ecrasement(self):
        """Le cas qui a coûté mai : un brouillon écrasé sans copie."""
        brouillon = {
            "id": "bul-1",
            "status": "brouillon",
            "payslip_data": {"salaire_brut": 2500.0},
            "edit_history": [],
        }
        archive = self._lancer(brouillon)
        assert archive.called, (
            "Un bulletin existant doit être archivé avant d'être réécrit, "
            "quel que soit son statut. Sans cela, une régénération détruit "
            "définitivement l'état précédent."
        )

    def test_aucun_archivage_quand_il_n_y_a_rien_a_ecraser(self):
        archive = self._lancer(None)
        assert not archive.called
