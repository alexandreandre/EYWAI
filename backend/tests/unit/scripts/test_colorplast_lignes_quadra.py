"""Motif de repérage du matricule dans un bulletin Quadra (pdftotext -layout)."""
import pytest

from scripts.backtest.colorplast_lignes_quadra import MATRICULE

pytestmark = pytest.mark.unit


def test_le_matricule_garde_son_suffixe_numerique():
    """Vu sur les bulletins réels : des matricules suffixés d'un chiffre (contrats
    successifs, homonymes) étaient tronqués à leur partie alphabétique par l'ancien
    motif (`[A-Z]+` seul), fusionnant parfois plusieurs salariés sous une seule clé
    (Mont-Blanc) ou mal étiquetant un contrat (Comitech, un contrat d'apprentissage
    portait le matricule tronqué d'un autre). Vérifié en lecture seule, bulletin par
    bulletin, que le contenu ne change jamais avec le suffixe restauré (voir le
    rapport de tâche)."""
    assert MATRICULE.search("   Matricule : ESSAI2                NoSécu.: 123456789012345").group(1) == "ESSAI2"
    assert MATRICULE.search("   Matricule : DUPONT                NoSécu.: 123456789012345").group(1) == "DUPONT"
