"""« Modèle standard » : la nouvelle sentinelle ET l'ancienne sont acceptées."""
from __future__ import annotations

import pytest

from app.modules.documents.application.commands import _validate_template_choice


@pytest.mark.parametrize("sentinelle", [None, "", "__martine__", "__eywai__"])
def test_le_modele_standard_n_a_pas_de_modele_personnalise(sentinelle):
    assert _validate_template_choice("c1", "contrat", sentinelle) is None
