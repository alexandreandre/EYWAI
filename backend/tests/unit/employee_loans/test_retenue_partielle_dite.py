"""Un remboursement de prêt retenu en partie le dit sur le bulletin. [rejeu G.3]

Relevé (rejeu du 11/10/2026) : prêt de 2 400 € sur 12 mois à 1 %, mensualité
201,08 € (échéance n° 1 : 199,08 € de capital, 2,00 € d'intérêts). Le bulletin
d'octobre (net à payer avant le prêt 1 619,54 €) ne retenait que 163,58 €
(161,95 € de capital, 1,63 € d'intérêts), sans un mot : `alertes_baremes` vide,
le volet du prêt disait seulement « Partielle ».

Règle appliquée par le code (inchangée, « dixième et étalement des avances »
attend une décision) : le capital retenu est limité au dixième du salaire
exigible (article L3251-3 du Code du travail : retenues successives ne
dépassant pas le dixième du montant des salaires exigibles), et au net encore
disponible ; les intérêts suivent au prorata du capital retenu, en plus. Le
reliquat reste dû sur l'échéance, reprise seule au bulletin suivant.

Le champ `avantage_nature_interets` valait 4,10 (5,04 au prorata du capital
retenu) quand la ligne imprimée « Avantages en nature » valait 5,04 : l'avantage
d'un prêt est l'intérêt épargné sur le capital dû pendant le mois ; il ne
dépend pas de ce que le bulletin a pu retenir. La ligne est juste, le champ
s'aligne.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.modules.employee_loans.application import enrichment

pytestmark = pytest.mark.unit

CODE = "pret_employeur_retenue_partielle"


def _pret(
    *,
    loan_id="loan-1",
    numero=1,
    capital=199.08,
    interets=2.00,
    restant=2400.0,
    taux=0.01,
    motif=None,
):
    return {
        "id": loan_id,
        "remaining_capital": restant,
        "principal_amount": 2400.0,
        "annual_interest_rate": taux,
        "start_date": "2026-10-01",
        "duration_months": 12,
        "status": "active",
        "reason": motif,
        "installment": {
            "id": f"inst-{loan_id}-{numero}",
            "installment_number": numero,
            "year": 2026,
            "month": 10,
            "capital_part": capital,
            "interest_part": interets,
            "capital_paid": 0,
            "interest_paid": 0,
            "status": "pending",
        },
    }


def _enrichir(bulletin: dict, prets: list):
    with (
        patch.object(enrichment, "get_suspended_loans_with_pending_installment", return_value=[]),
        patch.object(enrichment, "get_unsettled_installments_for_payroll", return_value=prets),
        patch.object(enrichment, "get_legal_interest_rate", return_value=Decimal("0.0352")),
        patch.object(enrichment, "get_capital_repayments", return_value=[], create=True),
        patch.object(enrichment, "employee_loan_repayments_repository") as remboursements,
        patch.object(enrichment, "employee_loan_installments_repository"),
        patch.object(enrichment, "employee_loans_repository"),
    ):
        remboursements.get_existing.return_value = None
        resultat = enrichment.enrich_payslip_loans(
            dict(bulletin), "emp-1", 2026, 10, payslip_id="bulletin-1"
        )
    return resultat, remboursements


def _alertes(bulletin: dict) -> list[dict]:
    return [a for a in bulletin.get("alertes_baremes") or [] if a.get("code") == CODE]


def test_rejeu_g3_le_montant_ne_change_pas_et_le_bulletin_le_dit():
    bulletin, _ = _enrichir({"net_a_payer": 1619.54, "salaire_brut": 2105.04}, [_pret()])

    prets = bulletin["remboursements_prets"]
    assert prets["total_capital"] == pytest.approx(161.95)
    assert prets["total_interets"] == pytest.approx(1.63)
    assert prets["total_rembourse"] == pytest.approx(163.58)
    assert bulletin["net_a_payer"] == pytest.approx(1455.96)
    (alerte,) = _alertes(bulletin)
    assert alerte["severity"] == "warning"
    assert alerte["message"] == (
        "Prêt employeur : 163,58 € retenus sur 201,08 € prévus pour l'échéance n° 1. "
        "La retenue est limitée au dixième du salaire exigible (article L3251-3 du Code "
        "du travail) : 161,95 € de capital (le dixième de 1 619,54 €), plus 1,63 € "
        "d'intérêts au prorata. Le reliquat de 37,50 € reste dû sur l'échéance n° 1 : "
        "il sera retenu seul sur le bulletin suivant, et les échéances suivantes "
        "glissent d'un mois."
    )


def test_l_avantage_en_nature_du_pret_est_celui_de_la_ligne_imprimee():
    bulletin, remboursements = _enrichir(
        {"net_a_payer": 1619.54, "salaire_brut": 2105.04}, [_pret()]
    )
    # 2 400 € × (3,52 % − 1 %) / 12 = 5,04 €, comme la ligne « Avantages en nature ».
    assert bulletin["remboursements_prets"]["avantage_nature_interets"] == pytest.approx(5.04)
    payload = remboursements.create.call_args.args[0]
    assert payload["avantage_nature_amount"] == pytest.approx(5.04)


def test_echeance_retenue_en_entier_ne_dit_rien():
    bulletin, _ = _enrichir({"net_a_payer": 4000.0, "salaire_brut": 5000.0}, [_pret()])
    assert bulletin["remboursements_prets"]["total_rembourse"] == pytest.approx(201.08)
    assert _alertes(bulletin) == []


def test_le_net_limite_la_retenue_et_le_bulletin_le_dit():
    # Salaire exigible 1 050 € (une avance de 1 000 € déjà retenue) : le dixième
    # (105 €) dépasse le net encore disponible (50 €).
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 50.0,
            "remboursements_avances": {"total_rembourse": 1000.0},
        },
        [_pret(capital=400.0, interets=0.0, taux=0.0352, motif="Achat d'un véhicule")],
    )
    (alerte,) = _alertes(bulletin)
    assert alerte["message"] == (
        "Prêt employeur (Achat d'un véhicule) : 50,00 € retenus sur 400,00 € prévus "
        "pour l'échéance n° 1. Le net à payer du mois ne permet pas plus. Le reliquat "
        "de 350,00 € reste dû sur l'échéance n° 1 : il sera retenu seul sur le bulletin "
        "suivant, et les échéances suivantes glissent d'un mois."
    )


def test_un_second_pret_sans_reste_de_dixieme_le_dit_aussi():
    bulletin, _ = _enrichir(
        {"net_a_payer": 2000.0},
        [
            _pret(loan_id="loan-1", capital=300.0, interets=0.0, taux=0.0352),
            _pret(loan_id="loan-2", numero=3, capital=100.0, interets=0.0, taux=0.0352),
        ],
    )
    assert bulletin["remboursements_prets"]["total_rembourse"] == pytest.approx(200.0)
    messages = [a["message"] for a in _alertes(bulletin)]
    assert messages[1] == (
        "Prêt employeur : 0,00 € retenus sur 100,00 € prévus pour l'échéance n° 3. "
        "Le dixième du salaire exigible (article L3251-3 du Code du travail), 200,00 €, "
        "est déjà retenu pour un autre prêt. Le reliquat de 100,00 € reste dû sur "
        "l'échéance n° 3 : il sera retenu seul sur le bulletin suivant, et les échéances "
        "suivantes glissent d'un mois."
    )
