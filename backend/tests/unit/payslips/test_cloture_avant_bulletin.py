"""Clôturer un départ avant le bulletin de sortie ne bloque plus rien [D3].

Relevé du 12/10/2026 (vidéo H) : un départ clôturé avant la génération du
bulletin de son dernier mois rendait ce bulletin impossible (« Ce collaborateur
n'est pas actif (statut : parti). ») et, par ricochet, le « Nouveau contrat »
(« Générez d'abord le bulletin de 10/2026 »). La clôture efface
`current_exit_id` : la date de sortie ne se lisait plus que sur la fin de
contrat de la fiche, absente d'un CDI ou d'un apprentissage.

Un salarié parti garde ses bulletins jusqu'à sa date de sortie : elle se lit sur
le départ de son contrat en cours, archivé ou non.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.payslips.application import commands
from app.modules.payslips.application.dto import PayslipBadRequestError
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_LECTEUR = "app.modules.employees.application.contrat_du_mois.lecteur_contrats"

_PARTI = {
    "id": "emp-1",
    "company_id": "co-1",
    "employment_status": "parti",
    "current_exit_id": None,
    "hire_date": "2025-03-03",
    "contract_type": "CDI",
    "contract_end_date": None,
    "nir": "1850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Paris"},
    "coordonnees_bancaires": {"iban": "FR7630001007941234567890185"},
    "salaire_de_base": {"montant": 2100},
    "statut": "Non-Cadre",
}


@pytest.fixture
def fiche():
    with patch.object(commands._employee_repository, "get_by_id_only", return_value=dict(_PARTI)), patch.object(
        commands, "raison_de_blocage_avant_bascule", return_value=None
    ):
        yield


def test_un_parti_cloture_avant_son_bulletin_le_recoit(fiche):
    with patch(f"{_LECTEUR}.sortie_du_contrat", return_value="2026-10-15") as lire:
        employe = commands.salarie_generable("emp-1", 2026, 10)
    assert employe["exit_last_working_day"] == "2026-10-15"
    lire.assert_called_once_with("emp-1", date(2025, 3, 3))


def test_le_mois_d_apres_la_sortie_reste_refuse(fiche):
    with patch(f"{_LECTEUR}.sortie_du_contrat", return_value="2026-10-15"):
        with pytest.raises(PayslipBadRequestError, match="pas actif"):
            commands.salarie_generable("emp-1", 2026, 11)


def test_sans_depart_date_le_refus_de_statut_reste(fiche):
    with patch(f"{_LECTEUR}.sortie_du_contrat", return_value=None):
        with pytest.raises(PayslipBadRequestError, match="pas actif"):
            commands.salarie_generable("emp-1", 2026, 10)


def test_le_generateur_date_la_sortie_par_le_depart_archive():
    """Sans elle, le bulletin du dernier mois d'un CDI clôturé se calculait sur
    le mois entier : aucune sortie connue."""
    from app.modules.payroll.documents.payslip_generator import resolve_date_sortie

    with patch(f"{_LECTEUR}.sortie_du_contrat", return_value="2026-10-15"):
        assert str(resolve_date_sortie(dict(_PARTI)))[:10] == "2026-10-15"


def test_un_salarie_actif_ne_lit_aucun_depart():
    from app.modules.payroll.documents.payslip_generator import resolve_date_sortie

    with patch(f"{_LECTEUR}.sortie_du_contrat") as lire:
        assert resolve_date_sortie({**_PARTI, "employment_status": "actif"}) is None
    lire.assert_not_called()


def test_le_depart_lu_est_celui_du_contrat_en_cours(monkeypatch):
    """Le premier départ daté depuis le début du contrat en cours : ni celui d'un
    contrat d'avant, ni un départ annulé, ni un transfert."""
    from app.modules.employees.application.contrat_du_mois import LecteurContrats

    BaseEnMemoire(
        {
            "employee_exits": [
                {"employee_id": "emp-1", "last_working_day": "2024-06-30", "status": "archivee", "exit_type": "fin_cdd"},
                {"employee_id": "emp-1", "last_working_day": "2026-10-15", "status": "archivee", "exit_type": "demission"},
                {"employee_id": "emp-1", "last_working_day": "2026-09-30", "status": "annulee", "exit_type": "demission"},
                {"employee_id": "emp-1", "last_working_day": "2026-08-31", "status": "archivee", "exit_type": "transfert"},
                {"employee_id": "emp-2", "last_working_day": "2026-05-31", "status": "archivee", "exit_type": "demission"},
            ]
        }
    ).brancher(monkeypatch)
    assert LecteurContrats().sortie_du_contrat("emp-1", date(2025, 3, 3)) == "2026-10-15"
    assert LecteurContrats().sortie_du_contrat("emp-1", date(2026, 11, 1)) is None
