"""Normalisation classification métallurgie (IDCC 3248, SMH national).

Le niveau DSN métallurgie (S21.G00.40.041) est de la forme "<classe> <groupe>"
(ex. "2 A", "11 F"). La grille SMH est indexée par la classe d'emploi (1-18),
donc la normalisation doit exposer `classe_emploi` pour que le contrôle du
minimum conventionnel puisse tourner.
"""

from copy import deepcopy
from datetime import date

from app.modules.collective_agreements.domain.classification import (
    normalize_classification_for_payroll,
)
from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    document_to_engine_rules,
)
from app.modules.collective_agreements.rules.seeds import get_seed
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.prime_anciennete import (
    calculer_ligne_prime_anciennete,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def _contexte_metallurgie(date_entree, *, classe=2, statut="Non-cadre"):
    baremes = deepcopy(baremes_snapshot())
    seed = get_seed("3248")
    doc = CCRulesDocument(idcc="3248", grilles_salaires=[seed.grille])  # type: ignore[list-item]
    doc.prime_anciennete = seed.prime
    baremes.setdefault("conventions_collectives", {})["idcc_3248"] = (
        document_to_engine_rules(doc)
    )
    return ChargerContexte(
        {
            "date_entree": date_entree,
            "statut": statut,
            "duree_hebdomadaire": 35.0,
            "salaire_base": 1850.0,
            "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
            "classification_conventionnelle": {"classe_emploi": classe},
        },
        {"parametres_paie": {"effectif": 50}, "adresse": {"code_postal": "79140"}},
        baremes,
    )


def test_embauche_recente_pas_alerte_non_eligible():
    """Ancienneté < seuil (cas normal d'un salarié récent) : pas d'alerte bruyante."""
    contexte = _contexte_metallurgie("2025-09-08")  # < 3 ans au 31/01/2026
    ligne = calculer_ligne_prime_anciennete(
        contexte,
        calendrier_saisie=[],
        date_debut_periode=date(2026, 1, 1),
        date_fin_periode=date(2026, 1, 31),
    )
    assert ligne is None
    assert not any(
        a.get("code") == "prime_anciennete_non_eligible"
        for a in contexte.alertes_baremes
    )


def test_metallurgie_parses_classe_and_groupe_from_niveau_dsn():
    result = normalize_classification_for_payroll(
        {"idcc": "3248", "niveau_dsn": "2 A"}
    )
    assert result["classe_emploi"] == 2
    assert result["classe"] == 2
    assert result["groupe"] == "A"


def test_metallurgie_parses_two_digit_classe():
    result = normalize_classification_for_payroll(
        {"idcc": "3248", "niveau_dsn": "11 F"}
    )
    assert result["classe_emploi"] == 11
    assert result["groupe"] == "F"


def test_metallurgie_niveau_sans_groupe():
    result = normalize_classification_for_payroll(
        {"idcc": "3248", "niveau_dsn": "7"}
    )
    assert result["classe_emploi"] == 7


def test_metallurgie_idcc_zero_pad_variant():
    result = normalize_classification_for_payroll(
        {"idcc": "03248", "niveau_dsn": "5 C"}
    )
    assert result["classe_emploi"] == 5


def test_metallurgie_niveau_invalide_laisse_inchange():
    for niveau in ("NC", "", None, "710"):
        result = normalize_classification_for_payroll(
            {"idcc": "3248", "niveau_dsn": niveau}
        )
        assert "classe_emploi" not in result


def test_metallurgie_ne_surcharge_pas_classe_existante():
    result = normalize_classification_for_payroll(
        {"idcc": "3248", "niveau_dsn": "2 A", "classe_emploi": 4}
    )
    assert result["classe_emploi"] == 4


def test_metallurgie_preserve_coefficient_existant():
    result = normalize_classification_for_payroll(
        {"idcc": "3248", "coefficient": 710, "niveau_dsn": "7 D"}
    )
    assert result["coefficient"] == 710
    assert result["classe_emploi"] == 7


def test_non_metallurgie_non_plasturgie_inchange():
    result = normalize_classification_for_payroll(
        {"idcc": "1486", "niveau_dsn": "3 B"}
    )
    assert "classe_emploi" not in result
