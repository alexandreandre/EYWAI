"""Un remboursement de prêt retenu en partie le dit sur le bulletin. [rejeu G.3]

Relevé (rejeu du 11/10/2026) : prêt de 2 400 € sur 12 mois à 1 %, mensualité
201,08 € (échéance n° 1 : 199,08 € de capital, 2,00 € d'intérêts). Le bulletin
d'octobre (net à payer avant le prêt 1 619,54 €) ne retenait que 163,58 €
(161,95 € de capital, 1,63 € d'intérêts), sans un mot : `alertes_baremes` vide,
le volet du prêt disait seulement « Partielle ».

Règle (D7, 31/10/2026) : un prêt signé à part du contrat de travail, pour une
durée fixée, n'est pas une avance (Cass. soc., 15 janvier 2014, n° 12-19.739) :
il se retient dans la limite de la quotité saisissable du mois, moins ce que les
saisies sur salaire en ont pris, et du net encore disponible ; capital et
intérêts tiennent ensemble sous ce plafond, les intérêts au prorata du capital
retenu. Le reliquat reste dû sur l'échéance, reprise seule au bulletin suivant.
Jusqu'au 31/10, le plafond était le dixième du salaire exigible (L3251-3) :
l'échéance du rejeu G.3 était retenue en partie (163,58 €) ; la quotité
(274,63 €) la laisse passer en entier.

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


def test_rejeu_g3_l_echeance_passe_en_entier_sous_la_quotite():
    # Quotité de 1 619,54 € au barème 2026 : 274,63 €, au-dessus des 201,08 € dus.
    bulletin, _ = _enrichir({"net_a_payer": 1619.54, "salaire_brut": 2105.04}, [_pret()])

    prets = bulletin["remboursements_prets"]
    assert prets["total_capital"] == pytest.approx(199.08)
    assert prets["total_interets"] == pytest.approx(2.00)
    assert bulletin["net_a_payer"] == pytest.approx(1418.46)
    assert _alertes(bulletin) == []


def test_ce_que_la_saisie_laisse_de_la_quotite_limite_le_pret_interets_compris():
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 1369.54,
            "retenues_saisies": {"total_preleve": 250.0, "personnes_a_charge": 0},
        },
        [_pret()],
    )
    prets = bulletin["remboursements_prets"]
    assert prets["total_capital"] == pytest.approx(24.38)
    assert prets["total_interets"] == pytest.approx(0.24)
    (alerte,) = _alertes(bulletin)
    assert alerte["message"] == (
        "Prêt employeur : 24,62 € retenus sur 201,08 € prévus pour l'échéance n° 1. "
        "La retenue, intérêts compris, est limitée à la quotité saisissable du mois "
        "(274,63 €, barème 2026, article L3252-2 du Code du travail), dont il restait "
        "24,63 € après les saisies sur salaire : 24,38 € de capital, plus 0,24 € "
        "d'intérêts au prorata. Le reliquat de 176,46 € reste dû sur l'échéance n° 1 : "
        "il sera retenu seul sur le bulletin suivant, et les échéances suivantes "
        "glissent d'un mois."
    )


def test_les_personnes_a_charge_de_la_saisie_baissent_la_quotite_du_pret():
    # Deux personnes à charge : 201,31 € au lieu de 274,63 € sur 1 619,54 €.
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 1619.54,
            "retenues_saisies": {"total_preleve": 0.0, "personnes_a_charge": 2},
        },
        [_pret(capital=250.0, interets=0.0, taux=0.0352)],
    )
    assert bulletin["remboursements_prets"]["total_capital"] == pytest.approx(201.31)


def test_le_bulletin_de_sortie_ne_compte_pas_l_indemnite_de_licenciement():
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 4619.54,
            "bulletin_de_sortie": True,
            "indemnites_sortie": {"total_exonerees": 3000.0},
        },
        [_pret(capital=400.0, interets=0.0, taux=0.0352)],
    )
    assert bulletin["remboursements_prets"]["total_capital"] == pytest.approx(274.63)
    assert bulletin["net_a_payer"] == pytest.approx(4344.91)


def test_sans_bareme_rien_n_est_retenu_et_le_bulletin_le_dit(_bareme_de_la_quotite):
    _bareme_de_la_quotite.return_value = None
    bulletin, _ = _enrichir({"net_a_payer": 1619.54}, [_pret()])
    assert bulletin["remboursements_prets"]["total_rembourse"] == 0.0
    (alerte,) = _alertes(bulletin)
    assert alerte["message"] == (
        "Prêt employeur : 0,00 € retenus sur 201,08 € prévus pour l'échéance n° 1. "
        "Le barème de la quotité saisissable n'est pas chargé : rien n'est retenu. "
        "Contactez le support. Le reliquat de 201,08 € reste dû sur l'échéance n° 1 : "
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
    # Base de 1 050 € (une avance de 1 000 € déjà retenue) : la quotité
    # (118,59 €) dépasse le net encore disponible (50 €).
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


def test_un_second_pret_sans_reste_de_quotite_le_dit_aussi():
    # Quotité de 2 000 € au barème 2026 : 471,73 €, prise par le premier prêt.
    bulletin, _ = _enrichir(
        {"net_a_payer": 2000.0},
        [
            _pret(loan_id="loan-1", capital=500.0, interets=0.0, taux=0.0352),
            _pret(loan_id="loan-2", numero=3, capital=100.0, interets=0.0, taux=0.0352),
        ],
    )
    assert bulletin["remboursements_prets"]["total_rembourse"] == pytest.approx(471.73)
    messages = [a["message"] for a in _alertes(bulletin)]
    assert messages == [
        "Prêt employeur : 471,73 € retenus sur 500,00 € prévus pour l'échéance n° 1. "
        "La retenue, intérêts compris, est limitée à la quotité saisissable du mois "
        "(471,73 €, barème 2026, article L3252-2 du Code du travail) : 471,73 € de "
        "capital. Le reliquat de 28,27 € reste dû sur l'échéance n° 1 : il sera retenu "
        "seul sur le bulletin suivant, et les échéances suivantes glissent d'un mois.",
        "Prêt employeur : 0,00 € retenus sur 100,00 € prévus pour l'échéance n° 3. "
        "La quotité saisissable du mois, 471,73 €, limite de la retenue (article L3252-2 "
        "du Code du travail), est déjà prise par un autre prêt. Le reliquat de 100,00 € "
        "reste dû sur l'échéance n° 3 : il sera retenu seul sur le bulletin suivant, et "
        "les échéances suivantes glissent d'un mois.",
    ]


def test_une_saisie_qui_prend_toute_la_quotite_ne_laisse_rien_au_pret():
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 1344.91,
            "retenues_saisies": {"total_preleve": 274.63, "personnes_a_charge": 0},
        },
        [_pret()],
    )
    assert bulletin["remboursements_prets"]["total_rembourse"] == 0.0
    (alerte,) = _alertes(bulletin)
    assert "est déjà prise par les saisies sur salaire." in alerte["message"]


def test_les_saisies_en_variables_prennent_aussi_sur_la_quotite():
    bulletin, _ = _enrichir(
        {
            "net_a_payer": 1619.54,
            "retenues_saisies": {"total_preleve": 0.0, "total_en_variables": 274.63},
        },
        [_pret()],
    )
    assert bulletin["remboursements_prets"]["total_rembourse"] == 0.0
