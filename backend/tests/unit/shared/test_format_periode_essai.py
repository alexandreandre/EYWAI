"""Libellé de période d'essai dans les contrats générés."""

from app.shared.infrastructure.pdf.helpers import format_periode_essai

REPLI = (
    "Conformément aux dispositions légales et conventionnelles applicables "
    "à l'emploi concerné"
)


def test_depuis_la_table_avec_renouvellement():
    label = format_periode_essai(
        {
            "trial_period": {
                "duration_value": 2,
                "duration_unit": "mois",
                "renewal_allowed": True,
            }
        }
    )
    assert label.startswith("2 mois, renouvelable une fois")


def test_depuis_la_table_sans_renouvellement():
    label = format_periode_essai(
        {
            "trial_period": {
                "duration_value": 1,
                "duration_unit": "jours",
                "renewal_allowed": False,
            }
        }
    )
    assert label.startswith("1 jour,")
    assert "renouvelable" not in label


def test_accord_du_pluriel():
    label = format_periode_essai(
        {
            "trial_period": {
                "duration_value": 3,
                "duration_unit": "semaines",
                "renewal_allowed": False,
            }
        }
    )
    assert label.startswith("3 semaines,")


def test_valeur_explicite_prioritaire():
    label = format_periode_essai(
        {"periode_essai_duree": "2 mois renouvelables", "trial_period": {"duration_value": 4}}
    )
    assert label == "2 mois renouvelables"


def test_repli_quand_la_periode_n_existe_pas_encore():
    # La génération du contrat peut précéder la création de la période.
    assert format_periode_essai({}) == REPLI
    assert format_periode_essai({"trial_period": None}) == REPLI
