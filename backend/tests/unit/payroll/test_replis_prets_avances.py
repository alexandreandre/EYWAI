"""Prêts, avances et saisies : une écriture ou une lecture ratée se voit sur le bulletin.

Audit de modernisation du 03/11/2026 (annexe 7, point 8 du temps 2) : les
écritures de l'enregistrement d'une retenue (ligne de remboursement, reste dû,
échéance) étaient avalées par des `except Exception: pass`, et quelques
lectures retombaient en silence sur une valeur supposée (taux légal, capital du
prêt, barème). Aucun montant ne change ici : l'échec est journalisé, le
bulletin porte une alerte de repli, et l'enregistrement s'arrête avant de
toucher au reste dû quand la ligne de retenue n'a pas pu être écrite (le
recalcul défait le bulletin d'après cette ligne).
"""

from __future__ import annotations

import inspect
import re
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.employee_loans.application import enrichment, payroll_integration
from app.modules.employee_loans.infrastructure import payroll_queries
from app.modules.payroll.engine import lectures
from app.modules.payroll.engine.lectures import LectureIndispensable
from app.modules.saisies_avances.application import service

pytestmark = pytest.mark.unit

A_RECALCULER = "repli_retenues_a_recalculer"
RESTE_DU = "repli_reste_du_non_mis_a_jour"
PRETS = "repli_prets"
AVANTAGE_PRET = "repli_avantage_pret"


@pytest.fixture(autouse=True)
def _sans_pause(monkeypatch):
    monkeypatch.setattr(lectures, "PAUSE", 0)


def _codes(bulletin: dict) -> list[str]:
    return [a.get("code") for a in bulletin.get("alertes_baremes") or []]


def _passagere():
    return httpx.ConnectError("connexion interrompue")


# ── Avances ────────────────────────────────────────────────────────────────

AVANCE = {
    "id": "avance-1",
    "status": "approved",
    "advance_type": "avance_salaire",
    "accounting_account": "425",
    "approved_amount": 800.0,
    "remaining_amount": 800.0,
    "repayment_mode": "single",
    "repayment_months": 1,
    "requested_date": "2026-09-10",
}


def _enrichir_avance(*, insertion=None, mise_a_jour=None, payslip_id="bulletin-1", avances=None):
    depot = MagicMock()
    if mise_a_jour is not None:
        depot.update.side_effect = mise_a_jour
    inserer = MagicMock(side_effect=insertion)
    journal = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[]),
        patch.object(
            service,
            "get_advances_to_repay",
            **({"side_effect": avances} if avances else {"return_value": [dict(AVANCE)]}),
        ),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "get_retenues_sur_le_net_du_mois", return_value=[]),
        patch.object(service, "insert_advance_repayment", inserer),
        patch.object(service, "advance_repository", depot),
        patch.object(service, "logger", journal),
    ):
        bulletin = service.enrich_payslip(
            {"net_a_payer": 2000.0}, "e1", 2026, 9, payslip_id=payslip_id
        )
    return bulletin, inserer, depot, journal


def test_avance_sans_ligne_de_remboursement_le_reste_du_ne_bouge_pas():
    """Le reste dû baissait avant que le remboursement soit écrit : le recalcul,
    qui défait d'après cette ligne, ne rendait rien et retenait l'avance une
    seconde fois."""
    bulletin, inserer, depot, journal = _enrichir_avance(insertion=RuntimeError("base"))

    assert inserer.called
    depot.update.assert_not_called()
    assert _codes(bulletin) == [A_RECALCULER]
    assert journal.exception.called
    # Le bulletin garde sa retenue : aucun montant ne change.
    assert bulletin["net_a_payer"] == pytest.approx(1200.0)
    assert bulletin["remboursements_avances"]["total_rembourse"] == 800.0


def test_avance_remboursement_ecrit_reste_du_rate_se_signale():
    bulletin, inserer, depot, journal = _enrichir_avance(mise_a_jour=RuntimeError("base"))

    assert inserer.called and depot.update.called
    assert _codes(bulletin) == [RESTE_DU]
    assert journal.exception.called
    assert bulletin["net_a_payer"] == pytest.approx(1200.0)


def test_avance_enregistree_l_ordre_est_ligne_puis_reste_du():
    ordre = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[]),
        patch.object(service, "get_advances_to_repay", return_value=[dict(AVANCE)]),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "get_retenues_sur_le_net_du_mois", return_value=[]),
        patch.object(service, "insert_advance_repayment", ordre.ligne),
        patch.object(service, "advance_repository", ordre.depot),
    ):
        bulletin = service.enrich_payslip({"net_a_payer": 2000.0}, "e1", 2026, 9, payslip_id="b1")

    assert [c[0] for c in ordre.mock_calls] == ["ligne", "depot.update"]
    assert _codes(bulletin) == []


def test_avance_sans_bulletin_enregistre_rien_n_est_ecrit():
    bulletin, inserer, depot, _ = _enrichir_avance(payslip_id=None)

    inserer.assert_not_called()
    depot.update.assert_not_called()
    assert bulletin["remboursements_avances"]["total_rembourse"] == 800.0


def test_avances_relues_sur_coupure_passagere():
    lectures_faites = iter([_passagere(), [dict(AVANCE)]])

    def lire(*_a, **_k):
        valeur = next(lectures_faites)
        if isinstance(valeur, Exception):
            raise valeur
        return valeur

    bulletin, _, _, _ = _enrichir_avance(avances=lire)
    assert bulletin["remboursements_avances"]["total_rembourse"] == 800.0


# ── Saisies ────────────────────────────────────────────────────────────────

SAISIE = {
    "id": "saisie-1",
    "type": "saisie_arret",
    "calculation_mode": "fixe",
    "amount": 46.49,
    "priority": 4,
    "start_date": "2026-07-01",
    "creditor_name": "Créancier",
    "reference_legale": None,
}


def _enrichir_saisie(*, insertion=None, suppression=None):
    from tests.unit.saisies_avances.test_quotite_saisissable_legale import BAREME

    journal = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[dict(SAISIE)]),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=BAREME),
        patch.object(service, "get_advances_to_repay", return_value=[]),
        patch.object(service, "get_retenues_sur_le_net_du_mois", return_value=[]),
        patch.object(service, "insert_seizure_deduction", side_effect=insertion),
        patch.object(service, "supprimer_deductions_du_bulletin", side_effect=suppression),
        patch.object(service, "logger", journal),
    ):
        bulletin = service.enrich_payslip(
            {"net_a_payer": 1616.01, "salaire_brut": 2088.9}, "e1", 2026, 7, payslip_id="b1"
        )
    return bulletin, journal


def test_saisie_prelevement_non_enregistre_se_signale():
    bulletin, journal = _enrichir_saisie(insertion=RuntimeError("base"))

    assert _codes(bulletin) == [A_RECALCULER]
    assert journal.exception.called
    assert bulletin["retenues_saisies"]["total_preleve"] == 46.49


def test_saisie_ancien_prelevement_non_retire_se_signale():
    bulletin, journal = _enrichir_saisie(suppression=RuntimeError("base"))

    assert _codes(bulletin) == [A_RECALCULER]
    assert journal.exception.called


# ── Prêts ──────────────────────────────────────────────────────────────────


def _pret(*, capital_paid=0.0, capital_part=500.0, status="active"):
    return {
        "id": "pret-1",
        "remaining_capital": 5000,
        "annual_interest_rate": 0,
        "reason": "Prêt",
        "status": status,
        "installment": {
            "id": "ech-1",
            "installment_number": 1,
            "year": 2026,
            "month": 6,
            "capital_part": capital_part,
            "interest_part": 0,
            "capital_paid": capital_paid,
            "interest_paid": 0,
            "status": "partial" if capital_paid else "pending",
        },
    }


def _enrichir_pret(
    *,
    retenue=None,
    pret_maj=None,
    echeance=None,
    statut_echeance=None,
    suspendus=None,
    deja=None,
    pret=None,
    bareme=None,
):
    from tests.unit.saisies_avances.test_quotite_saisissable_legale import BAREME

    retenues = MagicMock()
    retenues.get_existing.side_effect = deja if deja is not None else (lambda *a: None)
    retenues.create.side_effect = retenue
    prets = MagicMock()
    prets.update.side_effect = pret_maj
    echeances = MagicMock()
    echeances.increment_paid.side_effect = echeance
    echeances.update.side_effect = statut_echeance
    journal = MagicMock()
    with (
        patch.object(
            enrichment,
            "get_suspended_loans_with_pending_installment",
            return_value=suspendus or [],
        ),
        patch.object(
            enrichment, "get_unsettled_installments_for_payroll", return_value=[pret or _pret()]
        ),
        patch.object(enrichment, "get_legal_interest_rate", return_value=Decimal("0.0352")),
        patch.object(
            enrichment,
            "get_bareme_quotite_saisissable",
            **({"side_effect": bareme} if bareme else {"return_value": BAREME}),
        ),
        patch.object(enrichment, "employee_loan_repayments_repository", retenues),
        patch.object(enrichment, "employee_loans_repository", prets),
        patch.object(enrichment, "employee_loan_installments_repository", echeances),
        patch.object(enrichment, "logger", journal),
    ):
        bulletin = enrichment.enrich_payslip_loans(
            {"net_a_payer": 2500.0, "salaire_brut": 3000.0}, "e1", 2026, 6, payslip_id="b1"
        )
    return bulletin, retenues, prets, echeances, journal


def test_pret_sans_ligne_de_retenue_capital_et_echeance_ne_bougent_pas():
    """Sans ligne de retenue, le recalcul ne défait rien : le capital baissé et
    l'échéance payée lui faisaient perdre la retenue."""
    bulletin, retenues, prets, echeances, journal = _enrichir_pret(retenue=RuntimeError("base"))

    assert retenues.create.called
    prets.update.assert_not_called()
    echeances.increment_paid.assert_not_called()
    assert _codes(bulletin) == [A_RECALCULER]
    assert journal.exception.called
    assert bulletin["net_a_payer"] == pytest.approx(2000.0)


def test_pret_capital_non_mis_a_jour_se_signale():
    bulletin, _, prets, echeances, journal = _enrichir_pret(pret_maj=RuntimeError("base"))

    assert prets.update.called and echeances.increment_paid.called
    assert _codes(bulletin) == [RESTE_DU]
    assert journal.exception.called
    assert bulletin["net_a_payer"] == pytest.approx(2000.0)


def test_pret_echeance_non_mise_a_jour_se_signale():
    bulletin, _, _, _, journal = _enrichir_pret(echeance=RuntimeError("base"))

    assert _codes(bulletin) == [RESTE_DU]
    assert journal.exception.called


def test_pret_echeance_soldee_non_marquee_se_signale():
    bulletin, _, _, _, journal = _enrichir_pret(
        pret=_pret(capital_paid=500.0), statut_echeance=RuntimeError("base")
    )

    assert _codes(bulletin) == [RESTE_DU]
    assert journal.exception.called


def test_pret_suspendu_echeance_non_sautee_se_signale():
    suspendu = {"id": "pret-2", "installment": {"id": "ech-9", "status": "pending"}}
    bulletin, _, _, _, journal = _enrichir_pret(
        suspendus=[suspendu], statut_echeance=RuntimeError("base")
    )

    assert RESTE_DU in _codes(bulletin)
    assert journal.exception.called


def test_pret_retenue_deja_enregistree_relue_sur_coupure_passagere():
    lectures_faites = iter([_passagere(), None])

    def lire(*_a):
        valeur = next(lectures_faites)
        if isinstance(valeur, Exception):
            raise valeur
        return valeur

    bulletin, retenues, _, _, _ = _enrichir_pret(deja=lire)
    assert retenues.get_existing.call_count == 2
    assert bulletin["remboursements_prets"]["total_rembourse"] == 500.0


def test_pret_bareme_illisible_n_est_pas_un_bareme_absent():
    """Une coupure n'est pas un barème absent : l'enrichissement des prêts
    s'arrête (le bulletin le dit, voir plus bas) au lieu d'annoncer « aucun
    barème » et de ne rien retenir."""
    with pytest.raises(LectureIndispensable):
        _enrichir_pret(bareme=RuntimeError("base"))


def test_pret_capital_du_mois_illisible_ne_retombe_plus_en_silence():
    pret = {"id": "pret-1", "start_date": "2026-01-01", "principal_amount": 6000}
    with (
        patch.object(enrichment, "get_capital_repayments", side_effect=RuntimeError("base")),
        pytest.raises(LectureIndispensable),
    ):
        enrichment._capital_du_au_debut_du_mois(pret, Decimal("5000"), 2026, 6)


# ── Taux légal et avantage en nature ───────────────────────────────────────


def _requete_taux(resultat=None, erreur=None):
    sb = MagicMock()
    execute = (
        sb.table.return_value.select.return_value.eq.return_value.is_.return_value
        .maybe_single.return_value.execute
    )
    if erreur is not None:
        execute.side_effect = erreur
    else:
        execute.return_value = resultat
    return sb


def test_taux_legal_illisible_arrete_au_lieu_du_taux_par_defaut():
    with (
        patch.object(payroll_queries, "supabase", _requete_taux(erreur=RuntimeError("base"))),
        pytest.raises(LectureIndispensable),
    ):
        payroll_queries.get_legal_interest_rate()


def test_taux_legal_absent_reste_le_taux_par_defaut():
    with patch.object(payroll_queries, "supabase", _requete_taux(resultat=None)):
        assert payroll_queries.get_legal_interest_rate() == payroll_queries.DEFAULT_LEGAL_INTEREST_RATE


def test_taux_legal_relu_sur_coupure_passagere():
    reponse = MagicMock(data={"config_data": {"taux_annuel": 0.0662}})
    sb = _requete_taux()
    (
        sb.table.return_value.select.return_value.eq.return_value.is_.return_value
        .maybe_single.return_value.execute
    ).side_effect = [_passagere(), reponse]
    with patch.object(payroll_queries, "supabase", sb):
        assert payroll_queries.get_legal_interest_rate() == Decimal("0.0662")


def test_sans_pret_l_avantage_ne_lit_pas_le_taux():
    with (
        patch.object(payroll_queries, "get_loans_for_benefit_in_kind", return_value=[]),
        patch.object(
            payroll_queries, "get_legal_interest_rate", side_effect=AssertionError("lu pour rien")
        ),
    ):
        assert payroll_queries.compute_total_loan_benefit_in_kind("e1", 2026, 6) == 0.0


def test_avantage_pret_illisible_arrete_le_bulletin():
    with (
        patch.object(
            payroll_queries,
            "compute_total_loan_benefit_in_kind",
            side_effect=LectureIndispensable("Les prêts du salarié n'ont pas pu être lus"),
        ),
        pytest.raises(LectureIndispensable),
    ):
        payroll_integration.inject_loan_benefit_in_kind({"remuneration": {}}, "e1", 2026, 6)


def test_avantage_pret_non_calcule_se_signale():
    from app.modules.payroll.engine.replis import fermer_collecte, ouvrir_collecte

    alertes: list = []
    jeton = ouvrir_collecte(alertes)
    try:
        with patch.object(
            payroll_queries, "compute_total_loan_benefit_in_kind", side_effect=ValueError("date")
        ):
            contrat = payroll_integration.inject_loan_benefit_in_kind(
                {"remuneration": {}}, "e1", 2026, 6
            )
    finally:
        fermer_collecte(jeton)
    assert [a["code"] for a in alertes] == [AVANTAGE_PRET]
    assert "pret_employeur" not in (contrat["remuneration"].get("avantages_en_nature") or {})


# ── Après l'enregistrement du bulletin ────────────────────────────────────


def _apres_upsert(*, prets=None, enregistrement=None, pdf=None):
    sb = MagicMock()
    if enregistrement is not None:
        sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = enregistrement
    with (
        patch(
            "app.modules.saisies_avances.application.service.enrich_payslip",
            side_effect=lambda donnees, *a, **k: donnees,
        ),
        patch(
            "app.modules.employee_loans.application.enrichment.enrich_payslip_loans",
            side_effect=prets or (lambda donnees, *a, **k: donnees),
        ),
        patch.object(payroll_integration, "supabase", sb),
        patch(
            "app.modules.payroll.documents.payslip_editor.regenerate_pdf_from_data",
            side_effect=pdf or (lambda *a, **k: None),
        ),
    ):
        config = payroll_integration.PdfRegenConfig(
            employee_id="e1",
            employee_folder_name="dossier",
            company_id="c1",
            month=9,
            year=2026,
            storage_path="c1/e1/2026-09.pdf",
        )
        bulletin = payroll_integration.enrich_payslip_after_upsert(
            {"net_a_payer": 1500.0, "alertes_baremes": [{"code": "autre"}]},
            "e1",
            2026,
            9,
            "bulletin-1",
            pdf_regen=config,
        )
    ecrit = None
    if sb.table.return_value.update.call_args:
        ecrit = sb.table.return_value.update.call_args.args[0]["payslip_data"]
    return bulletin, ecrit


def test_prets_avales_se_signalent_sur_le_bulletin():
    bulletin, ecrit = _apres_upsert(prets=RuntimeError("base injoignable"))

    assert _codes(bulletin) == ["autre", PRETS]
    assert _codes(ecrit) == ["autre", PRETS]
    assert bulletin["net_a_payer"] == 1500.0


def test_bulletin_enrichi_non_enregistre_le_dit_a_la_generation():
    bulletin, _ = _apres_upsert(enregistrement=RuntimeError("base injoignable"))

    assert _codes(bulletin) == ["autre", A_RECALCULER]


def test_pdf_enrichi_non_depose_est_dit_dans_le_bulletin_enregistre():
    bulletin, ecrit = _apres_upsert(pdf=RuntimeError("weasyprint"))

    assert _codes(ecrit) == ["autre", A_RECALCULER]
    assert _codes(bulletin) == ["autre", A_RECALCULER]


# ── Garde : plus de `pass` sur ces chemins ───────────────────────────────


@pytest.mark.parametrize("module", [enrichment, payroll_integration, payroll_queries, service])
def test_plus_aucune_erreur_avalee_sans_trace(module):
    source = inspect.getsource(module)
    assert not re.search(r"except Exception[^:\n]*:\s*(#[^\n]*)?\n\s*pass\b", source), module.__name__
