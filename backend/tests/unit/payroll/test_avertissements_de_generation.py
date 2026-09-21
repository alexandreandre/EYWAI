"""Les avertissements renvoyés à la génération distinguent l'alerte du point à arbitrer.

Un point d'information (plafond transport…) ne doit plus sortir en orange
« généré avec alerte » : il part avec sa sévérité pour que le front le montre
discrètement. Les vraies alertes restent des chaînes, comme avant.
"""

from app.modules.payroll.engine.controles_convention import (
    avertissements_de_generation,
    controle_plafond_transport,
)

FRAIS_PRO = {
    "FRAIS_PRO": [
        {"sections": {"mobilite_durable": {"employeurs_prives": {"limite_base": 600.0}}}}
    ]
}


def test_une_alerte_reste_une_chaine():
    bulletin = {
        "alertes_baremes": [
            {"code": "x", "critique": True, "severity": "warning", "message": "Vraie alerte."}
        ]
    }
    assert avertissements_de_generation(bulletin) == ["Vraie alerte."]


def test_un_point_a_arbitrer_part_avec_sa_severite():
    bulletin = {
        "alertes_baremes": [
            {"code": "transport_plafond_annuel_depasse", "critique": False, "severity": "info",
             "a_arbitrer": True, "message": "Transport : 700,00 € versés."}
        ]
    }
    assert avertissements_de_generation(bulletin) == [
        {"code": "transport_plafond_annuel_depasse", "severity": "info",
         "message": "Transport : 700,00 € versés."}
    ]


def test_une_alerte_non_critique_sans_le_drapeau_reste_une_alerte():
    """Classification manquante, grille vide… : non critiques mais à corriger, donc en orange."""
    bulletin = {
        "alertes_baremes": [
            {"code": "cc_classification_manquante", "critique": False, "severity": "info",
             "message": "Classification manquante."}
        ]
    }
    assert avertissements_de_generation(bulletin) == ["Classification manquante."]


def test_les_doublons_et_les_codes_non_actionnables_sont_ecartes():
    bulletin = {
        "alertes_baremes": [
            {"code": "a", "critique": True, "message": "Même alerte."},
            {"code": "a", "critique": True, "message": "Même alerte."},
        ]
    }
    assert avertissements_de_generation(bulletin) == ["Même alerte."]


def test_le_message_transport_tient_en_une_phrase_courte():
    (alerte,) = controle_plafond_transport(700.0, FRAIS_PRO, annee=2026, cumul_mois_precedents=600.0)
    message = alerte["message"].replace(" ", " ").replace("\xa0", " ")
    assert message == (
        "Indemnité de transport : 700,00 € versés en 2026 pour 600,00 € exonérables, "
        "excédent 100,00 € à arbitrer (bulletin inchangé)."
    )
    assert alerte["severity"] == "info"
