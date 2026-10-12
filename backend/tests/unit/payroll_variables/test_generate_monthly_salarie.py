"""[J8] L'option « variables avant le bulletin » ne touche que le salarié du bulletin.

Avant : chaque génération d'un bulletin réécrivait les variables automatiques de
tous les salariés actifs de la société (deux primes de 60 € chez Comitech). Le
recalcul d'un seul salarié changeait les variables du mois de tous les autres.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.payroll_variables.application.generate_monthly import (
    generate_monthly_variables,
)

pytestmark = pytest.mark.unit

GM = "app.modules.payroll_variables.application.generate_monthly"

SALARIES = [
    {"id": "emp-1", "first_name": "Alice", "last_name": "Essai", "statut": "Non-Cadre",
     "company_id": "comp-1", "employment_status": "actif"},
    {"id": "emp-2", "first_name": "Bruno", "last_name": "Essai", "statut": "Non-Cadre",
     "company_id": "comp-1", "employment_status": "actif"},
    {"id": "emp-3", "first_name": "Chloé", "last_name": "Essai", "statut": "Cadre",
     "company_id": "comp-1", "employment_status": "actif"},
]

REGLE_60 = {
    "enabled": True,
    "rule_type": "fixed_monthly",
    "code": "prime_poste_difficile",
    "label": "Prime poste difficile",
    "amount": 60.0,
    "generation_mode": "auto",
    "conditions": {},
}


class _Requete:
    """Requête qui filtre vraiment les lignes : `.eq` et `.in_` comptent."""

    def __init__(self, lignes: list[dict[str, Any]]) -> None:
        self.lignes = lignes

    def select(self, *_a, **_k) -> "_Requete":
        return self

    def eq(self, cle: str, valeur: Any) -> "_Requete":
        return _Requete([l for l in self.lignes if l.get(cle) == valeur])

    def in_(self, cle: str, valeurs: list[Any]) -> "_Requete":
        return _Requete([l for l in self.lignes if l.get(cle) in valeurs])

    def execute(self) -> MagicMock:
        return MagicMock(data=list(self.lignes))


class _Base:
    def table(self, nom: str) -> _Requete:
        assert nom == "employees", nom
        return _Requete(SALARIES)


@pytest.fixture
def ecritures():
    ecrites: list[dict[str, Any]] = []
    with (
        patch(f"{GM}.supabase", _Base()),
        patch(f"{GM}.repo") as repo,
        patch(f"{GM}.list_validated_absences_for_employees_in_range", return_value=[]),
        patch(f"{GM}._bornes_variables", side_effect=lambda *_: _bornes()),
        patch(f"{GM}._resolve_quantity", return_value=1.0),
    ):
        repo.list_rules.return_value = [REGLE_60]
        repo.list_special_days.return_value = []
        repo.upsert_monthly_input.side_effect = ecrites.append
        yield ecrites


def _bornes():
    from datetime import date

    return date(2026, 10, 1), date(2026, 10, 31)


def test_sans_salarie_toute_la_societe_comme_avant(ecritures):
    generate_monthly_variables("comp-1", 2026, 10, dry_run=False)
    assert sorted(e["employee_id"] for e in ecritures) == ["emp-1", "emp-2", "emp-3"]


def test_pour_un_salarie_seules_ses_variables_sont_ecrites(ecritures):
    resultat = generate_monthly_variables("comp-1", 2026, 10, dry_run=False, employee_id="emp-2")

    assert [e["employee_id"] for e in ecritures] == ["emp-2"]
    assert ecritures[0]["amount"] == 60.0
    assert resultat["written_count"] == 1
    assert [p["employee_id"] for p in resultat["preview"]] == ["emp-2"]


def test_la_generation_d_un_bulletin_ne_genere_que_les_variables_de_son_salarie():
    """Le générateur passe l'identifiant du salarié : les autres ne sont pas touchés."""
    from app.modules.payroll.documents import payslip_generator as gen

    salarie = {
        "id": "emp-2",
        "company_id": "comp-1",
        "hire_date": "2020-01-01",
        "employee_folder_name": "dossier",
    }

    def table(nom: str):
        t = MagicMock()
        chaine = t.select.return_value.eq.return_value.single.return_value
        # La société introuvable arrête la génération juste après les variables.
        chaine.execute.return_value = MagicMock(data=salarie if nom == "employees" else None)
        return t

    base = MagicMock()
    base.table.side_effect = table
    reglages = MagicMock()
    reglages.get_company_planning_settings.return_value = {
        "auto_generate_payroll_variables_before_payslip": True
    }
    with (
        patch.object(gen, "supabase", base),
        patch(
            "app.modules.planning.infrastructure.repository.planning_repository", reglages
        ),
        patch(f"{GM}.generate_monthly_variables") as generer,
    ):
        with pytest.raises(HTTPException):
            gen.process_payslip_generation("emp-2", 2026, 10)

    generer.assert_called_once()
    assert generer.call_args.args[:3] == ("comp-1", 2026, 10)
    assert generer.call_args.kwargs.get("employee_id") == "emp-2"
    assert generer.call_args.kwargs.get("dry_run") is False
