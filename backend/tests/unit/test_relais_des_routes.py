"""Les relais `router_support` acceptent les appels que leurs routes leur font.

Relevé le 01/11/2026 par un contrôle des signatures (mypy, erreurs d'appel) : depuis
la réorganisation de mai, trois relais ne prenaient plus les arguments de leur
route et l'auraient fait tomber en 500 au premier appel (validation d'une absence
par le manager, évaluation d'une formation, dépôt de son certificat). Chaque test
appelle le relais comme la route le fait, le dépôt remplacé au bout.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def test_le_manager_valide_une_absence():
    from app.modules.absences.application import router_support as relais

    with patch.object(relais, "absence_repository") as depot:
        relais.approve_absence_by_manager("abs-1", "soc-1", "user-1", False, "Trop tard")

    depot.approve_by_manager.assert_called_once_with("abs-1", "soc-1", "user-1", False, "Trop tard")


def test_le_salarie_evalue_sa_formation():
    from app.modules.training.application import router_support as relais

    with patch.object(relais, "training_repository") as depot:
        relais.submit_enrollment_evaluation("ins-1", "soc-1", "emp-1", 4, "Utile")

    depot.submit_evaluation.assert_called_once_with("ins-1", "soc-1", "emp-1", 4, "Utile")


def test_le_certificat_de_formation_se_depose():
    from app.modules.training.application import router_support as relais

    with patch.object(relais, "training_repository") as depot:
        relais.upload_enrollment_certificate("ins-1", "soc-1", b"%PDF", "certificat.pdf", "application/pdf")

    depot.upload_enrollment_certificate.assert_called_once_with(
        "ins-1", "soc-1", b"%PDF", "certificat.pdf", "application/pdf"
    )
