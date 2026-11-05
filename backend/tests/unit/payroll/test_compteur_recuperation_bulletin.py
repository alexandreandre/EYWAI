"""Le bulletin imprime le compteur de récupération, comme Quadra : heures
acquises, heures prises avec leur date, solde ; dès 7 h, la mention des deux
mois (C. trav. D3171-11). Spec 2026-11-05-heures-de-recuperation.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import construire_compteurs

pytestmark = pytest.mark.unit


def _bulletin(recup: dict | None) -> dict:
    solde = {
        "date_reference": "31/07/2026",
        "conges_payes": {"acquis": 2.08, "pris": 0.0, "solde": 2.08},
    }
    if recup is not None:
        solde["recuperation"] = recup
    return {"pied_de_page": {"solde_conges": solde}}


def test_sans_compteur_de_recuperation_rien_ne_change():
    compteurs = construire_compteurs(_bulletin(None))
    assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N"]
    assert compteurs["notes"] == []


def test_colonne_recuperation_et_heures_prises_avec_leur_date():
    compteurs = construire_compteurs(
        _bulletin(
            {
                "acquis": 9.0,
                "pris": 7.0,
                "paye": 0.0,
                "solde": 2.0,
                "acquis_annee": 12.5,
                "pris_annee": 7.0,
                "prises": [{"date": "2026-07-13", "heures": 7.0}],
            }
        )
    )
    # Le tableau se lit en cumul (comme les congés) ; le détail du mois en note.
    colonne = compteurs["colonnes"][-1]
    assert colonne == {"titre": "Récup. (h)", "acquis": 12.5, "pris": 7.0, "solde": 2.0}
    assert "Récupération ce mois-ci : 9 h acquises, 7 h prises le 13/07" in compteurs["notes"]
    assert not any("deux mois" in n for n in compteurs["notes"])


def test_un_solde_nul_sans_mouvement_s_imprime_quand_meme():
    # Le réglage est actif : un compteur à zéro se montre (jamais d'état muet).
    compteurs = construire_compteurs(
        _bulletin({"acquis": 0.0, "pris": 0.0, "paye": 0.0, "solde": 0.0, "prises": []})
    )
    assert compteurs["colonnes"][-1]["titre"] == "Récup. (h)"


def test_mention_des_deux_mois_des_sept_heures():
    compteurs = construire_compteurs(
        _bulletin(
            {
                "acquis": 8.75,
                "pris": 0.0,
                "paye": 0.0,
                "solde": 10.5,
                "prises": [],
            }
        )
    )
    assert (
        "Droit à repos ouvert : 10,5 h de récupération à prendre dans un délai "
        "maximum de deux mois (C. trav. D3171-11)."
    ) in compteurs["notes"]


def test_heures_payees_dites_en_note():
    compteurs = construire_compteurs(
        _bulletin({"acquis": 0.0, "pris": 0.0, "paye": 2.0, "solde": 0.0, "prises": []})
    )
    assert "Récupération ce mois-ci : 2 h payées" in compteurs["notes"]
