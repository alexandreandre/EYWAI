from copy import deepcopy
from datetime import date

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    document_to_engine_rules,
)
from app.modules.collective_agreements.rules.seeds.plasturgie_0292 import (
    PLASTURGIE_0292_SEED,
)
from app.modules.collective_agreements.domain.classification import (
    normalize_classification_for_payroll,
)
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def test_plasturgie_uses_numeric_dsn_level_as_coefficient():
    classification = {
        "idcc": "0292",
        "coefficient": 730,
        "niveau_dsn": "700",
    }

    assert normalize_classification_for_payroll(classification)["coefficient"] == 700


def test_other_idcc_keeps_existing_coefficient():
    classification = {
        "idcc": "3248",
        "coefficient": 710,
        "niveau_dsn": "7",
    }

    assert normalize_classification_for_payroll(classification)["coefficient"] == 710


def test_plasturgie_under_first_seniority_tier_has_no_classification_warning():
    baremes = deepcopy(baremes_snapshot())
    doc = CCRulesDocument(
        idcc="0292",
        prime_anciennete=PLASTURGIE_0292_SEED.prime,
    )
    baremes.setdefault("conventions_collectives", {})["idcc_0292"] = (
        document_to_engine_rules(doc)
    )
    contexte = ChargerContexte(
        {
            "date_entree": "2024-04-25",
            "statut": "Non-cadre",
            "duree_hebdomadaire": 37.5,
            "salaire_base": 1868.57,
            "convention_collective": {"idcc": "0292", "libelle": "Plasturgie"},
            "classification_conventionnelle": {"coefficient": 700},
        },
        {"parametres_paie": {"effectif": 50}},
        baremes,
    )

    ligne = calculer_ligne_prime_anciennete(
        contexte,
        calendrier_saisie=[],
        date_debut_periode=date(2026, 1, 1),
        date_fin_periode=date(2026, 1, 31),
    )

    assert ligne is None
    assert not any(
        alerte.get("code") == "prime_anciennete_classification_manquante"
        for alerte in contexte.alertes_baremes
    )
