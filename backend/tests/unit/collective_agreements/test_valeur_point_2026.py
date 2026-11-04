"""Valeur du point de la prime d'ancienneté de la métallurgie en 2026, par territoire.

CCN de la métallurgie (IDCC 3248), art. 142 : la valeur du point est fixée par
accord territorial. Audit du 03/11/2026 (lot B, verdict 3) :
- Deux-Sèvres : accord du 31/10/2025, « la valeur de point pour le calcul de la
  prime d'ancienneté est fixée à 5,80 € », « applicable à compter du 1er janvier
  2026 » ; étendu par arrêté du 3 mars 2026 (JORF du 6 mars 2026), qui « prend
  effet à compter de la date de publication » ;
- Seine-et-Marne : avenant du 23/01/2026, point porté à 5,29 € au 1er janvier
  2026 ; étendu par arrêté du 4 mai 2026 (JORF du 8 mai 2026).
Martine applique la loi : le point de l'accord vaut pour tous les employeurs à
la publication de l'extension (avant, seulement pour les adhérents de la
chambre patronale, ce que la fiche ne dit pas). L'ancien logiciel restait aux
points de 2025 (5,70 et 5,24).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.collective_agreements.rules.prime_calcul import resolve_prime_anciennete_config
from app.modules.collective_agreements.rules.resolver import resolve_valeur_point
from app.modules.collective_agreements.rules.schema import CCRulesDocument, document_to_engine_rules
from app.modules.collective_agreements.rules.seeds import apply_seed_to_document, get_seed
from app.modules.payroll.engine.baremes_loader import _enrich_cc_rules_with_seed

pytestmark = pytest.mark.unit


def _prime_du_seed():
    doc = apply_seed_to_document(CCRulesDocument(idcc="3248"), get_seed("3248"))
    return document_to_engine_rules(doc)["prime_anciennete"]


@pytest.mark.parametrize(
    "code_postal, jour, attendu",
    [
        ("79140", date(2026, 2, 28), 5.70),
        ("79140", date(2026, 3, 6), 5.80),
        ("79140", date(2026, 10, 31), 5.80),
        ("77140", date(2026, 4, 30), 5.24),
        ("77140", date(2026, 5, 8), 5.29),
        ("77140", date(2026, 11, 30), 5.29),
    ],
)
def test_le_point_de_l_accord_territorial_a_la_date_du_bulletin(code_postal, jour, attendu):
    assert resolve_valeur_point(_prime_du_seed(), code_postal=code_postal, a_la_date=jour) == attendu


def test_la_regle_en_base_au_point_de_2025_cede_au_point_date_du_seed():
    """La base porte une zone des Deux-Sèvres sans date, à 5,70 € : le point daté
    de 2026 la remplace dès sa date d'effet."""
    en_base = {
        "prime_anciennete": {
            "base_de_calcul": {"valeur": 5.57, "methode": "valeur_du_point"},
            "valeurs_point": [
                {"valeur": 5.83, "zone_type": "national", "departements": [], "zone_libelle": "National"},
                {"valeur": 5.7, "zone_type": "departemental", "departements": ["79"], "zone_libelle": "Deux-Sèvres"},
            ],
        }
    }
    prime = _enrich_cc_rules_with_seed(en_base, "3248")["prime_anciennete"]
    assert resolve_valeur_point(prime, code_postal="79140", a_la_date=date(2026, 10, 31)) == 5.80
    assert resolve_valeur_point(prime, code_postal="79140", a_la_date=date(2026, 1, 31)) == 5.70
    assert resolve_valeur_point(prime, code_postal="77140", a_la_date=date(2026, 10, 31)) == 5.29


def test_sans_date_la_lecture_d_avant():
    assert resolve_valeur_point(_prime_du_seed(), code_postal="79140") == 5.70


def test_la_configuration_du_mois_porte_le_point_du_mois():
    entreprise = {"adresse": {"code_postal": "79140"}}
    config = resolve_prime_anciennete_config(_prime_du_seed(), entreprise, a_la_date=date(2026, 10, 31))
    assert config["valeur_point"] == 5.80


def test_la_surcharge_de_la_societe_reste_prioritaire():
    entreprise = {"adresse": {"code_postal": "79140"}, "parametres_paie": {"prime_anciennete": {"valeur_point_override": 6.0}}}
    config = resolve_prime_anciennete_config(_prime_du_seed(), entreprise, a_la_date=date(2026, 10, 31))
    assert config["valeur_point"] == 6.0
