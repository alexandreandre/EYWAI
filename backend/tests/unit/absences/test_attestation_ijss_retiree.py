"""L'attestation de salaire maison pour la CPAM n'existe plus (Elsa, 05/11).

Le signalement d'arrêt en DSN la remplace (cahier technique 2026.1, § 2.5). Le
document inventait le salaire de la fiche pour les mois sans bulletin.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from app.modules.absences.api.router import router

pytestmark = pytest.mark.unit


def test_plus_aucune_route_d_attestation_sur_un_arret():
    chemins = [getattr(route, "path", "") for route in router.routes]
    assert [c for c in chemins if "certificate" in c] == []


def test_le_generateur_a_disparu():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.payroll.documents.salary_certificate_generator")


def test_valider_un_arret_ne_genere_plus_rien():
    source = Path("app/modules/absences/application/commands.py").read_text(encoding="utf-8")
    assert not re.search(r"salary_certificate|attestation_salaire_ijss", source)
