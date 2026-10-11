"""Une saisie sur salaire retenue en partie le dit sur le bulletin. [D8]

Relevé à l'écran (vidéo G, 11/10/2026) : une saisie à montant fixe de 900 € sur
un net de 1 383,52 € n'a retenu que 230,26 € (« Retenues sur salaire −230.26 »),
sans aucune alerte : la saisie restait « Active » à 900 €, et rien ne disait
pourquoi la retenue était moindre. La limite est la quotité saisissable du mois
(Code du travail L3252-2 ; barème de l'année, R3252-2) ; le reste n'est pas
retenu ce mois-ci.

Une alerte au bulletin dit le montant retenu, le montant demandé et pourquoi.
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


def _saisie(montant: float, mode: str = "fixe") -> dict:
    return {
        "id": "saisie-1",
        "type": "saisie_arret",
        "calculation_mode": mode,
        "amount": montant,
        "priority": 4,
        "creditor_name": "Créancier fictif SARL",
    }


def _enrichir(net: float, saisies: list, avances: list | None = None) -> dict:
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=list(saisies)),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=BAREME, create=True),
        patch.object(service, "get_advances_to_repay", return_value=list(avances or [])),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_advance_repayment", ecritures.remboursement),
        patch.object(service, "insert_seizure_deduction", ecritures.saisie),
        patch.object(service, "advance_repository", ecritures.depot),
    ):
        return service.enrich_payslip(
            {"net_a_payer": net, "salaire_brut": 1700.0}, "e1", 2026, 10, payslip_id=None
        )


def _quotite(net: str) -> Decimal:
    bareme, _ = rules.resoudre_bareme_quotite(BAREME, 2026, 10)
    return rules.calculate_seizable_amount(Decimal(net), 0, bareme)


def _euros(montant: Decimal) -> str:
    entier, decimales = f"{montant:.2f}".split(".")
    return f"{int(entier):,}".replace(",", " ") + f",{decimales} €"


def _alertes(bulletin: dict) -> list[dict]:
    return [a for a in bulletin.get("alertes_baremes") or [] if a.get("code") == CODE]


def test_saisie_fixe_plafonnee_a_la_quotite_le_dit():
    bulletin = _enrichir(1383.52, [_saisie(900.0)])
    quotite = _quotite("1383.52")

    assert bulletin["retenues_saisies"]["total_preleve"] == pytest.approx(float(quotite))
    (alerte,) = _alertes(bulletin)
    assert alerte["severity"] == "warning"
    assert alerte["message"] == (
        f"Saisie sur salaire (Créancier fictif SARL) : {_euros(quotite)} retenus sur "
        f"900,00 € demandés. La quotité saisissable du mois est de {_euros(quotite)} "
        f"(barème 2026, sur un net de 1 383,52 €) : le reste n'est pas retenu ce mois-ci."
    )


def test_saisie_retenue_en_entier_ne_dit_rien():
    bulletin = _enrichir(1383.52, [_saisie(46.49)])

    assert bulletin["retenues_saisies"]["total_preleve"] == pytest.approx(46.49)
    assert _alertes(bulletin) == []


def test_bareme_legal_sans_montant_ne_dit_rien():
    # Rien n'est « demandé » : la saisie prend la quotité, c'est sa règle.
    bulletin = _enrichir(1383.52, [_saisie(None, mode="barème_legal")])

    assert _alertes(bulletin) == []


def test_net_negatif_rien_retenu_et_le_bulletin_le_dit():
    bulletin = _enrichir(-50.0, [_saisie(100.0)])

    assert bulletin["retenues_saisies"]["total_preleve"] == pytest.approx(0.0)
    (alerte,) = _alertes(bulletin)
    assert alerte["message"] == (
        "Saisie sur salaire (Créancier fictif SARL) : 0,00 € retenus sur 100,00 € demandés. "
        "Le net à payer du mois ne permet pas de retenue : le reste n'est pas retenu ce mois-ci."
    )
