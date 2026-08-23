"""
Périmètre société neutralisé pour ces tests d'intégration.

Depuis la fermeture de l'IDOR inter-sociétés (23/08/2026),
require_employee_access résout en base la société RÉELLE du salarié visé et
refuse (404) si elle diffère de celle de l'appelant. Ces tests simulent la
base : le salarié y appartient par construction à la société de l'appelant.

Le cas HORS périmètre — le cœur de la faille — est couvert avec la VRAIE
logique dans tests/unit/security/test_perimetre_societe_employe.py.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def perimetre_societe_neutralise():
    with patch(
        "app.modules.access_control.application.service.AccessControlService."
        "assert_employee_in_company",
        return_value=None,
    ):
        yield
