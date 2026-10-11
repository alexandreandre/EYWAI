"""Nature de l'arrêt et type d'arrêt : une combinaison incohérente est refusée.

Le maintien de salaire suit le type d'arrêt (`arret_type`), la DSN et
l'attestation de salaire suivent la nature (`type` de la demande). Un
« Arrêt maladie » typé « Accident du travail » était enregistré : maintien
d'accident du travail (sans carence), motif DSN de maladie, attestation en
salaires rétablis. La saisie est refusée, avec une phrase qui dit quoi choisir.
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.absences.application import commands
from app.modules.absences.domain.nature_arret import (
    incoherence_nature_type_d_arret,
)
from app.modules.absences.schemas.requests import AbsenceRequestCreate

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "nature, type_arret",
    [
        ("arret_maladie", "maladie_simple"),
        ("arret_maladie", "ald"),
        ("arret_maladie", "mi_temps_therapeutique"),
        ("arret_maladie", "arret_exceptionnel"),
        ("arret_at", "accident_travail"),
        ("arret_at", "accident_trajet"),
        ("arret_at", "rechute_at"),
        ("arret_maladie_pro", "maladie_professionnelle"),
        ("arret_maladie_pro", "rechute_at"),
        # Pas encore de type d'arrêt propre à la parentalité (défaut F12, en
        # attente de décision) : le seul choix possible à l'écran reste permis.
        ("arret_maternite", "maladie_simple"),
        ("arret_paternite", "maladie_simple"),
    ],
)
def test_combinaisons_coherentes_acceptees(nature, type_arret):
    assert incoherence_nature_type_d_arret(nature, type_arret) is None


@pytest.mark.parametrize(
    "nature, type_arret",
    [
        ("arret_maladie", "accident_travail"),
        ("arret_maladie", "maladie_professionnelle"),
        ("arret_maladie", "accident_trajet"),
        ("arret_maladie", "rechute_at"),
        ("arret_at", "maladie_simple"),
        ("arret_at", "maladie_professionnelle"),
        ("arret_at", "mi_temps_therapeutique"),
        ("arret_maladie_pro", "accident_travail"),
        ("arret_maladie_pro", "maladie_simple"),
        ("arret_maternite", "accident_travail"),
        ("arret_paternite", "maladie_professionnelle"),
    ],
)
def test_combinaisons_incoherentes_refusees(nature, type_arret):
    assert incoherence_nature_type_d_arret(nature, type_arret)


def test_la_phrase_dit_quoi_choisir():
    message = incoherence_nature_type_d_arret("arret_maladie", "accident_travail")
    assert message == (
        "Le type d'arrêt « Accident du travail » ne correspond pas à la nature "
        "« Arrêt maladie ». Pour cette nature, choisissez « Maladie simple », "
        "« ALD », « Mi-temps thérapeutique » ou « Arrêt exceptionnel » ; "
        "ou gardez « Accident du travail » et choisissez la nature "
        "« Accident du travail »."
    )


def test_hors_arret_ou_sans_type_rien_a_controler():
    assert incoherence_nature_type_d_arret("conge_paye", None) is None
    assert incoherence_nature_type_d_arret("arret_maladie", None) is None


def _demande(nature: str, type_arret: str) -> AbsenceRequestCreate:
    return AbsenceRequestCreate(
        employee_id="emp-1",
        type=nature,
        arret_type=type_arret,
        date_debut=date(2026, 10, 12),
        date_fin=date(2026, 10, 16),
    )


def test_enregistrement_refuse_une_combinaison_incoherente():
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ), patch("app.modules.absences.application.commands.absence_repository") as repo:
        with pytest.raises(ValueError) as refus:
            commands.create_absence_request(_demande("arret_maladie", "accident_travail"))
    assert "choisissez la nature « Accident du travail »" in str(refus.value)
    repo.create.assert_not_called()


def test_enregistrement_accepte_un_accident_de_trajet_en_accident_du_travail():
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ), patch("app.modules.absences.application.commands.absence_repository") as repo:
        repo.create.return_value = {"id": "req-1"}
        commands.create_absence_request(_demande("arret_at", "accident_trajet"))
    assert repo.create.call_args[0][0]["arret_type"] == "accident_trajet"
