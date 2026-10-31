"""La DSN d'un mois à deux contrats : un individu, deux contrats, deux versements
(D3.2, spécification 2026-10-31-dsn-deux-contrats-design.md).

Le CDD finit le 10/11, le nouveau contrat commence le 17/11.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.dsn_export.domain.deux_contrats import evenements_du_contrat, fusionner
from app.modules.dsn_export.domain.writer import write_individu
from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    BaseAssujettieBlock,
    ContratBlock,
    CotisationIndividuelleBlock,
    IndividuBlock,
    VersementBlock,
)


def _contrat(numero: str, debut: str, net: str, affiliation: str = "1") -> ContratBlock:
    versement = VersementBlock(
        rubriques={"S21.G00.50.001": "30112026", "S21.G00.50.002": net, "S21.G00.50.003": "01"},
        bases_assujetties=[
            BaseAssujettieBlock(
                code="03",
                rubriques={"S21.G00.78.001": "03", "S21.G00.78.004": net},
            ),
            BaseAssujettieBlock(
                code="31#0",
                rubriques={"S21.G00.78.001": "31", "S21.G00.78.005": affiliation},
            ),
        ],
        cotisations_individuelles=[
            CotisationIndividuelleBlock(
                code="059",
                identifiant_affiliation=affiliation,
                rubriques={"S21.G00.81.001": "059", "_base": "31#0"},
            )
        ],
    )
    return ContratBlock(
        numero_contrat=numero,
        date_debut=debut,
        rubriques={
            "S21.G00.40.001": debut,
            "S21.G00.40.009": numero,
            "_regime_retraite_complementaire": "RUAA",
            "_anciennete_entreprise": {"unite": "01", "valeur": "3", "contrat": numero},
        },
        affiliations=[
            AffiliationBlock(
                identifiant_affiliation=affiliation,
                rubriques={"S21.G00.70.012": affiliation, "S21.G00.70.013": "1"},
            )
        ],
        versements=[versement],
    )


def _individu(*contrats: ContratBlock) -> IndividuBlock:
    return IndividuBlock(
        nir="1850575123456", rubriques={"S21.G00.30.001": "1850575123456"}, contrats=list(contrats)
    )


def _blocs(lignes: list[str]) -> list[str]:
    """La suite des blocs écrits (un par première rubrique rencontrée)."""
    blocs: list[str] = []
    precedente = ""
    for ligne in lignes:
        rubrique = ligne.split(",")[0]
        bloc = rubrique[:10]
        if bloc != precedente[:10] or rubrique <= precedente:
            blocs.append(bloc)
        precedente = rubrique
    return blocs


def test_un_contrat_s_ecrit_comme_avant():
    lignes: list[str] = []
    write_individu(_individu(_contrat("00000", "01072026", "900.00")), lignes)
    assert _blocs(lignes) == [
        "S21.G00.30",
        "S21.G00.40",
        "S21.G00.70",
        "S21.G00.71",
        "S21.G00.50",
        "S21.G00.78",
        "S21.G00.78",
        "S21.G00.81",
        "S21.G00.86",
    ]


def test_deux_contrats_puis_deux_versements_puis_les_anciennetes():
    """Arborescence de la norme (CT 2026.1, § 8) : 40 et 50 sont tous deux
    enfants de l'individu ; un versement écrit sous chaque contrat ferait du
    second contrat un enfant du premier versement."""
    lignes: list[str] = []
    write_individu(
        _individu(_contrat("00000", "01072026", "700.00"), _contrat("00001", "17112026", "900.00")),
        lignes,
    )
    blocs = _blocs(lignes)
    assert [b for b in blocs if b in ("S21.G00.40", "S21.G00.50", "S21.G00.86")] == [
        "S21.G00.40",
        "S21.G00.40",
        "S21.G00.50",
        "S21.G00.50",
        "S21.G00.86",
        "S21.G00.86",
    ]
    # Les blocs 70 et 71 restent sous leur contrat.
    assert blocs.index("S21.G00.71") < blocs.index("S21.G00.40", 2)


# --------------------------------------------------------------------------
# Fusion des deux contrats sous un individu
# --------------------------------------------------------------------------

def _fusion() -> IndividuBlock:
    return fusionner(
        _individu(_contrat("00000", "01072026", "700.00", affiliation="1")),
        _individu(_contrat("00001", "17112026", "900.00", affiliation="1")),
    )


def test_l_individu_porte_l_ancien_contrat_puis_le_nouveau():
    individu = _fusion()
    assert [c.numero_contrat for c in individu.contrats] == ["00000", "00001"]


def test_chaque_versement_a_son_numero():
    """CT 50.003 CCH-11 et CCH-12 : deux versements, deux numéros."""
    individu = _fusion()
    numeros = [v.rubriques["S21.G00.50.003"] for c in individu.contrats for v in c.versements]
    assert numeros == ["01", "02"]


def test_chaque_base_cite_son_contrat():
    """CT 78.006 : plusieurs contrats, chaque base dit le sien."""
    individu = _fusion()
    for contrat in individu.contrats:
        for base in contrat.versements[0].bases_assujetties:
            assert base.rubriques["S21.G00.78.006"] == contrat.numero_contrat


def test_les_affiliations_de_l_ancien_contrat_sont_decalees():
    """CT 70.012 CCH-11 : un identifiant d'affiliation unique par salarié ; les
    bases 31 et les cotisations de l'ancien versement suivent (78.005 CCH-12)."""
    ancien, nouveau = _fusion().contrats
    assert nouveau.affiliations[0].rubriques["S21.G00.70.012"] == "1"
    assert ancien.affiliations[0].rubriques["S21.G00.70.012"] == "2"
    assert ancien.affiliations[0].identifiant_affiliation == "2"
    versement = ancien.versements[0]
    assert versement.bases_assujetties[1].rubriques["S21.G00.78.005"] == "2"
    assert versement.cotisations_individuelles[0].identifiant_affiliation == "2"
    # La base 03 ne cite aucune affiliation : rien n'y est ajouté.
    assert "S21.G00.78.005" not in versement.bases_assujetties[0].rubriques


def test_deux_contrats_sous_le_meme_numero_sont_refuses():
    """CT 40.009 CCH-12 : un numéro unique par individu dans la déclaration."""
    with pytest.raises(ValueError, match="00000"):
        fusionner(
            _individu(_contrat("00000", "01072026", "700.00")),
            _individu(_contrat("00000", "17112026", "900.00")),
        )


def test_les_cotisations_des_deux_bulletins_s_additionnent():
    ancien = _individu(_contrat("00000", "01072026", "700.00"))
    ancien.rubriques["_cot_sal"], ancien.rubriques["_cot_pat"] = "100.00", "200.00"
    nouveau = _individu(_contrat("00001", "17112026", "900.00"))
    nouveau.rubriques["_cot_sal"], nouveau.rubriques["_cot_pat"] = "50.50", "60.25"
    individu = fusionner(ancien, nouveau)
    assert individu.rubriques["_cot_sal"] == "150.50"
    assert individu.rubriques["_cot_pat"] == "260.25"


# --------------------------------------------------------------------------
# Événements de chaque contrat
# --------------------------------------------------------------------------

FIN_ANCIEN, DEBUT_NOUVEAU = date(2026, 11, 10), date(2026, 11, 17)


def _arret(*jours: str) -> dict:
    return {"type": "arret_maladie", "selected_days": list(jours)}


EVENEMENTS = {
    "absences_dsn": [_arret("2026-11-03", "2026-11-05"), _arret("2026-11-23", "2026-11-24")],
    "sorties_dsn": [{"last_working_day": "2026-11-10", "exit_type": "fin_cdd"}],
    "sortie_dsn": {"last_working_day": "2026-11-10", "exit_type": "fin_cdd"},
    "pas_type_taux": "01",
    "smic_horaire_reduction": 11.88,
    "heures_cumulees_avant": 1200.0,
}


def test_l_ancien_contrat_garde_sa_sortie_et_ses_arrets():
    ancien = evenements_du_contrat(EVENEMENTS, date(2026, 7, 1), FIN_ANCIEN)
    assert ancien["sortie_dsn"]["last_working_day"] == "2026-11-10"
    assert [a["selected_days"][0] for a in ancien["absences_dsn"]] == ["2026-11-03"]
    assert ancien["pas_type_taux"] == "01"


def test_l_ancien_contrat_n_a_pas_le_repli_du_smic_du_nouveau():
    """Le cumul d'heures du repli est celui du contrat de la fiche."""
    ancien = evenements_du_contrat(EVENEMENTS, date(2026, 7, 1), FIN_ANCIEN, contrat_de_la_fiche=False)
    assert "smic_horaire_reduction" not in ancien
    assert "heures_cumulees_avant" not in ancien


def test_le_nouveau_contrat_n_a_ni_la_sortie_ni_les_arrets_de_l_ancien():
    nouveau = evenements_du_contrat(EVENEMENTS, DEBUT_NOUVEAU, None)
    assert "sortie_dsn" not in nouveau
    assert [a["selected_days"][0] for a in nouveau["absences_dsn"]] == ["2026-11-23"]
    assert nouveau["smic_horaire_reduction"] == 11.88


def test_la_sortie_du_nouveau_contrat_dans_le_mois_lui_revient():
    evenements = {
        **EVENEMENTS,
        "sorties_dsn": EVENEMENTS["sorties_dsn"] + [{"last_working_day": "2026-11-28"}],
    }
    assert evenements_du_contrat(evenements, DEBUT_NOUVEAU, None)["sortie_dsn"] == {
        "last_working_day": "2026-11-28"
    }
    assert evenements_du_contrat(evenements, date(2026, 7, 1), FIN_ANCIEN)["sortie_dsn"][
        "last_working_day"
    ] == "2026-11-10"
