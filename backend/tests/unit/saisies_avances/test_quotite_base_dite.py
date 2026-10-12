"""La quotité saisissable dit sur quelle base elle est calculée. [rejeu G.4]

Relevé (rejeu du 11/10/2026) : une saisie de 900 € retenait 230,26 € « sur un
net de 1 383,52 € », puis 229,41 € quand le net passait à 1 483,89 €. La
quotité semblait baisser quand le net montait.

Ce n'était pas le calcul : le barème (R3252-2, version du 01/01/2026) est
progressif et la quotité ne baisse jamais quand la base monte. Le premier
bulletin portait aussi un prêt employeur (100 € retenus après la saisie) et
son avantage en nature (2,93 €) : la base saisissable était 1 483,52 € de net
à payer avant retenues + 2,93 € d'avantage en nature = 1 486,45 €, et
« 1 383,52 » était le net après le prêt. Le second n'avait plus le prêt : base
1 483,89 €. La base a baissé de 2,56 €, la quotité de 0,85 €.

L'alerte disait « sur un net de » : elle dit maintenant la base saisissable,
et de quoi elle est faite quand elle n'est pas le net à payer avant retenues.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service
from app.modules.saisies_avances.domain import rules

from .test_quotite_saisissable_legale import BAREME

pytestmark = pytest.mark.unit

CODE = "saisie_sur_salaire_plafonnee"


def _quotite(base: str) -> Decimal:
    bareme, _ = rules.resoudre_bareme_quotite(BAREME, 2026, 10)
    return rules.calculate_seizable_amount(Decimal(base), 0, bareme)


def _enrichir(bulletin: dict) -> dict:
    saisie = {
        "id": "saisie-1",
        "type": "saisie_arret",
        "calculation_mode": "fixe",
        "amount": 900.0,
        "priority": 4,
        "creditor_name": "Créancier fictif SARL",
    }
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[saisie]),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=BAREME, create=True),
        patch.object(service, "get_advances_to_repay", return_value=[]),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_advance_repayment", ecritures.remboursement),
        patch.object(service, "insert_seizure_deduction", ecritures.saisie),
        patch.object(service, "advance_repository", ecritures.depot),
    ):
        return service.enrich_payslip(dict(bulletin), "e1", 2026, 10, payslip_id=None)


def _message(bulletin: dict) -> str:
    (alerte,) = [a for a in bulletin.get("alertes_baremes") or [] if a.get("code") == CODE]
    return alerte["message"]


def test_la_quotite_ne_baisse_jamais_quand_la_base_monte():
    precedente = Decimal("0")
    base = Decimal("0")
    while base <= Decimal("3200"):
        quotite = _quotite(str(base))
        assert quotite >= precedente, f"{base} : {quotite} < {precedente}"
        precedente = quotite
        base += Decimal("0.37")


def test_les_deux_bulletins_du_rejeu():
    assert _quotite("1486.45") == Decimal("230.26")
    assert _quotite("1483.89") == Decimal("229.41")


def test_l_alerte_dit_la_base_et_ce_qui_s_ajoute_au_net():
    bulletin = _enrichir(
        {
            "net_a_payer": 1483.52,
            "salaire_brut": 1902.2,
            "synthese_net": {"avantages_en_nature": 2.93, "acompte_verse": 0.0},
        }
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == pytest.approx(230.26)
    assert _message(bulletin) == (
        "Saisie sur salaire (Créancier fictif SARL) : 230,26 € retenus sur 900,00 € "
        "demandés. La quotité saisissable du mois est de 230,26 € (barème 2026, sur une "
        "base saisissable de 1 486,45 € : net à payer avant retenues 1 483,52 € "
        "+ avantages en nature 2,93 €) : le reste n'est pas retenu ce mois-ci."
    )


def test_sans_ajout_ni_retrait_l_alerte_dit_le_net_avant_retenues():
    bulletin = _enrichir({"net_a_payer": 1483.89, "salaire_brut": 1898.98})
    assert _message(bulletin) == (
        "Saisie sur salaire (Créancier fictif SARL) : 229,41 € retenus sur 900,00 € "
        "demandés. La quotité saisissable du mois est de 229,41 € (barème 2026, sur le "
        "net à payer avant retenues de 1 483,89 €) : le reste n'est pas retenu ce mois-ci."
    )


def test_les_frais_et_l_acompte_sont_nommes():
    bulletin = _enrichir(
        {
            "net_a_payer": 1300.0,
            "salaire_brut": 2000.0,
            "synthese_net": {"acompte_verse": 300.0, "remboursement_transport": 40.0},
            "primes_non_soumises": [
                {"prime_id": "remb_frais_1", "libelle": "Note de frais", "montant": 42.0},
            ],
        }
    )
    assert "sur une base saisissable de 1 518,00 € : net à payer avant retenues " in _message(
        bulletin
    )
    assert _message(bulletin).endswith(
        "1 300,00 € + acomptes et retenues sur le net 300,00 € − frais de transport 40,00 € "
        "− remboursements de frais 42,00 €) : le reste n'est pas retenu ce mois-ci."
    )


def test_le_report_d_un_net_negatif_est_nomme_a_part():
    net, elements = rules.composition_base_saisissable(
        {
            "net_a_payer": 920.94,
            "synthese_net": {"acompte_verse": 801.25},
            "reports_nap_negatif": [{"nom": "Report NAP négatif 10/2026", "montant": 801.25}],
        }
    )
    assert net == Decimal("920.94")
    assert elements == [("report de net négatif retenu", Decimal("801.25"))]
