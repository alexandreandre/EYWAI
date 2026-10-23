"""Une déduction d'IJSS sans subrogation se lit au bulletin, à l'écran et au PDF."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents import bulletin_view
from app.modules.payroll.domain.explications_lignes import poser_explications

pytestmark = pytest.mark.unit

LIGNE = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None,
         "gain": 295.82, "perte": None, "is_maintien_employeur": True}

DEDUIT = {"maintien_cible": 665.68, "maintien_verse": 295.82,
          "ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}


def _bulletin(maintien, ligne=None):
    return {
        "en_tete": {"annee": 2025, "mois": 6},
        "calcul_du_brut": [dict(ligne or LIGNE)],
        "bloc_maintien": {"maintien": maintien},
    }


def test_l_explication_dit_le_garanti_moins_les_ijss():
    b = poser_explications(_bulletin(DEDUIT))
    assert b["calcul_du_brut"][0]["explication"] == (
        "Complément employeur : salaire garanti 665,68 € moins 369,86 € d'IJSS "
        "versées par la CPAM au salarié (estimées par Martine)"
    )


def test_montant_valide_l_explication_le_dit():
    b = poser_explications(_bulletin({**DEDUIT, "ijss_deduites_source": "validees"}))
    assert b["calcul_du_brut"][0]["explication"].endswith("(montant validé dans le suivi IJSS)")


def test_sans_deduction_aucune_cle_nouvelle():
    b = poser_explications(_bulletin({"maintien_cible": 665.68, "maintien_verse": 665.68}))
    assert "explication" not in b["calcul_du_brut"][0]
    lignes = bulletin_view.construire_lignes(_bulletin({"maintien_verse": 665.68}))
    assert [ligne for ligne in lignes if ligne["type"] == "note"] == []


def test_le_pdf_porte_la_mention_sous_la_ligne_de_maintien():
    lignes = bulletin_view.construire_lignes(_bulletin(DEDUIT))
    i = next(i for i, ligne in enumerate(lignes) if ligne["libelle"] == "Maintien de salaire employeur")
    assert lignes[i + 1] == bulletin_view._ligne("note", "dont IJSS déduites : 369,86 € (estimées)")


def test_le_pdf_d_une_ligne_corrigee_a_la_main_ne_porte_pas_la_mention():
    corrigee = {**LIGNE, "correction": {"motif": "Relevé CPAM", "valeur_calculee": 295.82}}
    lignes = bulletin_view.construire_lignes(_bulletin(DEDUIT, corrigee))
    assert not any(str(ligne["libelle"]).startswith("dont IJSS") for ligne in lignes)
