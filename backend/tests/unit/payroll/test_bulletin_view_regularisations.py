"""Le PDF dit chaque régularisation saisie à la main."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents import bulletin_view
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def test_le_pdf_porte_une_note_par_regularisation():
    ligne = RegularisationCotisation(
        coti_id="mutuelle",
        libelle="Mutuelle",
        motif="Tarif 2026",
        montant_patronal=8.3,
        saisie_id="s1",
    ).ligne_de_cotisation()
    bulletin = {"cotisations_officielles": [{"code": "sante", "libelle": "Santé", "lignes": [ligne]}]}
    lignes = bulletin_view.construire_lignes(bulletin)
    notes = [l["libelle"] for l in lignes if l["type"] == "note"]
    assert "Régularisation saisie à la main — Mutuelle : Tarif 2026" in notes
