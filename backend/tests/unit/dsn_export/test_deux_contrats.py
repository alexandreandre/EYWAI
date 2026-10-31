"""La DSN d'un mois à deux contrats : un individu, deux contrats, deux versements
(D3.2, spécification 2026-10-31-dsn-deux-contrats-design.md).

Le CDD finit le 10/11, le nouveau contrat commence le 17/11.
"""

from __future__ import annotations

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
