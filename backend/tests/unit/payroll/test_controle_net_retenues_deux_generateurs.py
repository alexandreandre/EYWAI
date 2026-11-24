"""B06 sur le vrai chemin des deux générateurs : retenues et ajouts au net.

Le contrôle B06 relit le net à payer contre le net avant impôt moins l'impôt.
Saisies sur salaire, avances (et acomptes du module « Avances ») et prêts sont
retirés du net après le moteur, à l'enregistrement : avant la correction, une
saisie levait B06 et bloquait la validation sans acquittement.

Ici, chaque générateur (heures, forfait jours) calcule un bulletin au bac à
sable avec un acompte saisi sur le net et une note de frais (passés par le
moteur), puis la vraie retenue des saisies, avances et prêts lui est appliquée
sans rien écrire. Le contrôle doit voir les mêmes champs aux deux.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_loans.application import enrichment as prets
from app.modules.payslips.domain.anomalies_bulletin import (
    anomalies_critiques_actives,
    anomalies_du_bulletin,
)
from app.modules.saisies_avances.application import service as saisies
from tests.unit.payroll.profils_salaries import ANNEE, DEUX_GENERATEURS, MOIS, banc  # noqa: F401
from tests.unit.saisies_avances.test_quotite_saisissable_legale import BAREME

pytestmark = pytest.mark.unit

ACOMPTE = {
    "name": "Acompte",
    "amount": -200.0,
    "sur_le_net": True,
    "is_socially_taxed": False,
    "is_taxable": False,
}
NOTE_DE_FRAIS = {"type": "Repas", "amount": 45.5, "date": f"{ANNEE}-{MOIS:02d}-12", "status": "validated"}
SAISIE = {
    "id": "saisie-1",
    "type": "atd",
    "calculation_mode": "fixe",
    "amount": 150.0,
    "priority": 1,
    "creditor_name": "Trésor public",
}
AVANCE = {
    "id": "avance-1",
    "status": "paid",
    "advance_type": "acompte_salaire",
    "accounting_account": "4251",
    "approved_amount": 100.0,
    "remaining_amount": 100.0,
    "repayment_mode": "single",
    "repayment_months": 1,
    "requested_date": f"{ANNEE}-{MOIS:02d}-05",
}
PRET = {
    "id": "pret-1",
    "remaining_capital": 2000.0,
    "annual_interest_rate": 0,
    "reason": "Prêt",
    "installment": {
        "id": "echeance-1",
        "installment_number": 1,
        "year": ANNEE,
        "month": MOIS,
        "capital_part": 80.0,
        "interest_part": 0,
        "capital_paid": 0,
        "interest_paid": 0,
        "status": "pending",
    },
}


#: Un taux d'impôt non nul : le contrôle retire l'impôt avant les retenues.
IMPOT = {"specificites_paie": {"prelevement_a_la_source": {"taux": 4.5, "is_personnalise": True}}}


def _b06(donnees: dict) -> list:
    return [a for a in anomalies_du_bulletin(donnees) if a.rule_id == "B06"]


def _retenir_apres_le_moteur(donnees: dict, employee_id: str) -> dict:
    """Saisie, avance puis prêt, comme `enrich_payslip_after_upsert`, sans écrire
    (pas d'identifiant de bulletin : aucune écriture n'est tentée)."""
    with (
        patch.object(saisies, "get_seizures_for_period", return_value=[dict(SAISIE)]),
        patch.object(saisies, "get_bareme_quotite_saisissable", return_value=BAREME, create=True),
        patch.object(saisies, "get_retenues_sur_le_net_du_mois", return_value=[]),
        patch.object(saisies, "get_advances_to_repay", return_value=[dict(AVANCE)]),
        patch.object(saisies, "advance_repository", MagicMock()),
        patch.object(prets, "get_bareme_quotite_saisissable", return_value=BAREME, create=True),
        patch.object(prets, "get_suspended_loans_with_pending_installment", return_value=[]),
        patch.object(prets, "get_unsettled_installments_for_payroll", return_value=[dict(PRET)]),
        patch.object(prets, "get_legal_interest_rate", return_value=Decimal("0.0352")),
    ):
        donnees = saisies.enrich_payslip(dict(donnees), employee_id, ANNEE, MOIS)
        return prets.enrich_payslip_loans(donnees, employee_id, ANNEE, MOIS)


@pytest.mark.parametrize("profil", DEUX_GENERATEURS)
def test_retenues_et_ajouts_au_net_ne_levent_pas_b06(banc, profil):  # noqa: F811
    banc.base.tables["expense_reports"] = [{"employee_id": f"salarie-{profil}", **NOTE_DE_FRAIS}]
    donnees = banc.generer(profil, saisies=[ACOMPTE], fiche_en_plus=IMPOT)
    assert donnees["synthese_net"]["impot_prelevement_a_la_source"]["montant"] > 0

    # L'acompte et la note de frais sont passés par le moteur : son net avant
    # impôt les porte, B06 ne doit rien y voir.
    assert donnees["synthese_net"]["acompte_verse"] == pytest.approx(200.0)
    assert any("frais" in str(p.get("libelle")).lower() for p in donnees.get("primes_non_soumises") or [])
    assert _b06(donnees) == []

    net_du_moteur = float(donnees["net_a_payer"])
    enrichi = _retenir_apres_le_moteur(donnees, f"salarie-{profil}")

    assert enrichi["retenues_saisies"]["total_preleve"] == pytest.approx(150.0)
    assert enrichi["remboursements_avances"]["total_rembourse"] == pytest.approx(100.0)
    assert enrichi["remboursements_prets"]["total_rembourse"] == pytest.approx(80.0)
    assert enrichi["net_a_payer"] == pytest.approx(net_du_moteur - 330.0)
    assert _b06(enrichi) == []
    assert [a.rule_id for a in anomalies_critiques_actives(enrichi) if a.rule_id == "B06"] == []


@pytest.mark.parametrize("profil", DEUX_GENERATEURS)
def test_un_net_faux_apres_retenues_leve_b06(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, fiche_en_plus=IMPOT)
    enrichi = _retenir_apres_le_moteur(donnees, f"salarie-{profil}")
    enrichi["net_a_payer"] = round(float(enrichi["net_a_payer"]) + 50.0, 2)

    (alerte,) = _b06(enrichi)
    assert alerte.delta_eur == pytest.approx(50.0)
    assert [a.rule_id for a in anomalies_critiques_actives(enrichi)] == ["B06"]
