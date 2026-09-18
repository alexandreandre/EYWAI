"""Compteurs de congés d'un bulletin repris de Quadra : copiés du PDF, jamais recalculés.

Les soldes imprimés au bulletin sont posés à la génération
(`pied_de_page.solde_conges`) et un mois importé ne se régénère plus. Pour qu'un
bulletin repris porte les compteurs que Gaëlle a imprimés — et non une case vide,
ni un recalcul depuis nos absences —, l'import littéral copie le bloc
« CP N-1 / CP N » du PDF, dans la forme que le rendu du bulletin sait lire.
"""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin
from scripts.reprise_colorplast_import_litteral import (
    _compteurs_affiches,
    _donnees_reprises,
)

pytestmark = pytest.mark.unit

BLOC_JUIN = {"Acquis": (40.0, 2.08), "Total pris": (0.0, 0.0), "Solde": (40.0, 2.08)}


def _bulletin(cp: dict) -> Bulletin:
    return Bulletin(matricule="BUGNY", cp=cp, pages=[1, 2])


def test_les_deux_colonnes_du_pdf_deviennent_les_deux_periodes_du_bulletin():
    compteurs = _compteurs_affiches(_bulletin(BLOC_JUIN), 2026, 6)

    assert compteurs["date_reference"] == "30/06/2026"
    assert compteurs["conges_payes_periode_precedente"] == {
        "acquis": 40.0, "pris": 0.0, "solde": 40.0,
        "periode": "01/06/2025 – 31/05/2026",
    }
    assert compteurs["conges_payes"] == {
        "acquis": 2.08, "pris": 0.0, "solde": 2.08,
        "periode": "01/06/2026 – 31/05/2027",
    }


def test_avant_le_1er_juin_les_periodes_sont_celles_de_l_exercice_precedent():
    bloc_mai = {"Acquis": (28.0, 24.96), "Total pris": (13.0, 0.0), "Solde": (15.0, 24.96)}

    compteurs = _compteurs_affiches(_bulletin(bloc_mai), 2026, 5)

    assert compteurs["date_reference"] == "31/05/2026"
    assert compteurs["conges_payes_periode_precedente"]["periode"] == "01/06/2024 – 31/05/2025"
    assert compteurs["conges_payes"]["periode"] == "01/06/2025 – 31/05/2026"
    assert compteurs["conges_payes_periode_precedente"]["pris"] == 13.0


def test_rien_d_autre_que_ce_que_quadra_imprime():
    """« Solde rep.remp. » et « Solde rep.récup. » sont vides sur tous les
    bulletins : on ne fabrique pas un zéro à leur place, la question des
    compteurs de repos reste posée à Gaëlle."""
    compteurs = _compteurs_affiches(_bulletin(BLOC_JUIN), 2026, 6)

    assert set(compteurs) == {
        "date_reference", "conges_payes", "conges_payes_periode_precedente",
    }


def test_sans_bloc_conges_lu_aucun_compteur():
    assert _compteurs_affiches(_bulletin({}), 2026, 6) is None


def test_l_import_pose_les_compteurs_sans_effacer_le_reste_du_pied_de_page():
    existantes = {
        "salaire_brut": 1.0,
        "pied_de_page": {"mentions": ["conservée"], "solde_conges": {"vieux": True}},
    }

    donnees = _donnees_reprises(existantes, _bulletin(BLOC_JUIN), 2026, 6)

    assert donnees["pied_de_page"]["mentions"] == ["conservée"]
    assert donnees["pied_de_page"]["solde_conges"]["conges_payes"]["solde"] == 2.08
    assert "solde_conges" in donnees["reprise"]["sections_copiees_du_pdf"]
    assert existantes["pied_de_page"]["solde_conges"] == {"vieux": True}, (
        "les données lues en base ne doivent pas être modifiées en place"
    )


def test_le_rendu_du_bulletin_lit_les_compteurs_copies():
    """Contrat avec `bulletin_view.construire_compteurs` : deux colonnes, N-1 puis N."""
    from app.modules.payroll.documents.bulletin_view import construire_compteurs

    vue = construire_compteurs(
        {"pied_de_page": {"solde_conges": _compteurs_affiches(_bulletin(BLOC_JUIN), 2026, 6)}}
    )

    assert vue["date_reference"] == "30/06/2026"
    assert [(c["titre"], c["acquis"], c["pris"], c["solde"]) for c in vue["colonnes"]] == [
        ("CP N-1", 40.0, 0.0, 40.0),
        ("CP N", 2.08, 0.0, 2.08),
    ]
