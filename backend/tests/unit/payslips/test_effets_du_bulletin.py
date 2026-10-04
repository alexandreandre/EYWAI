"""Recalculer ou supprimer un bulletin défait ce qu'il avait écrit hors de lui.

Audit du 04/10/2026 : générer un bulletin retient l'échéance d'un prêt, solde
une avance, applique des dépôts CET et crédite le compte de modulation. Le
recalculer perdait l'échéance et l'avance (déjà « payées », plus rien à
retenir), payait de nouveau les heures déposées au CET et comptait deux fois
les heures créditées en modulation ; le supprimer ne rendait rien.

Désormais, avant de recalculer et quand on supprime, le bulletin défait ses
effets ; le recalcul les refait une seule fois. Ce que l'on ne peut pas défaire
proprement est refusé avec une phrase qui dit quoi faire.

Tout passe ici par une base en mémoire et par le vrai code : génération
(`generate_payslip`), enrichissement (avances, prêts), crochets CET et
modulation, suppression (`delete_payslip`). Seul le moteur de calcul est
remplacé : il rend un net de 3 000 € et les heures de son calendrier.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core import database
from app.modules.payslips.application import commands
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipBadRequestError,
)
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = [pytest.mark.unit, pytest.mark.effets_en_base]

SAL, SOC = "salarie-1", "societe-1"
AN, MOIS = 2026, 9
NET_DU_MOTEUR = 3000.0

SALARIE = {
    "id": SAL,
    "company_id": SOC,
    "first_name": "Camille",
    "last_name": "Essai",
    "employment_status": "actif",
}


def _echeances() -> list[dict]:
    lignes = []
    for n in range(1, 11):
        annee, mois = AN + (MOIS + n - 2) // 12, (MOIS + n - 2) % 12 + 1
        lignes.append(
            {
                "id": f"echeance-{n}",
                "loan_id": "pret-1",
                "installment_number": n,
                "year": annee,
                "month": mois,
                "capital_part": 225.0,
                "interest_part": 0.0,
                "total_due": 225.0,
                "status": "pending",
                "capital_paid": 0.0,
                "interest_paid": 0.0,
                "payslip_id": None,
            }
        )
    return lignes


def _base_initiale(*, statut_avance: str = "paid", verse: float = 800.0) -> BaseEnMemoire:
    """Ce que la gestionnaire saisit : un acompte de 800 € versé, un prêt de
    2 250 € à 225 €/mois, 4 h déposées au CET, et le compte de modulation."""
    return BaseEnMemoire(
        {
            "payslips": [],
            "employee_schedules": [{"employee_id": SAL, "year": AN, "month": MOIS, "cumuls": None}],
            "salary_advances": [
                {
                    "id": "avance-1",
                    "employee_id": SAL,
                    "company_id": SOC,
                    "status": statut_avance,
                    "advance_type": "acompte_salaire",
                    "accounting_account": "4251",
                    "requested_amount": 800.0,
                    "approved_amount": 800.0,
                    "remaining_amount": 800.0,
                    "repayment_mode": "single",
                    "repayment_months": 1,
                    "requested_date": "2026-09-10",
                    "payment_date": "2026-09-10",
                }
            ],
            "salary_advance_payments": [
                {"id": "versement-1", "advance_id": "avance-1", "payment_amount": verse}
            ],
            "salary_advance_repayments": [],
            "salary_seizures": [],
            "salary_seizure_deductions": [],
            "employee_loans": [
                {
                    "id": "pret-1",
                    "employee_id": SAL,
                    "company_id": SOC,
                    "principal_amount": 2250.0,
                    "annual_interest_rate": 0.0,
                    "duration_months": 10,
                    "monthly_payment": 225.0,
                    "status": "active",
                    "remaining_capital": 2250.0,
                    "reason": "Achat véhicule",
                }
            ],
            "employee_loan_installments": _echeances(),
            "employee_loan_repayments": [],
            "company_cet_settings": [
                {"company_id": SOC, "hs_debit_timing": "on_payroll", "cp_debit_timing": "on_validation"}
            ],
            "employee_cet_movements": [
                {
                    "id": "cet-1",
                    "company_id": SOC,
                    "employee_id": SAL,
                    "year": AN,
                    "month": MOIS,
                    "movement_type": "deposit_hs",
                    "hours": 4.0,
                    "status": "validated",
                    "metadata": {},
                }
            ],
            "company_modulation_settings": [
                {
                    "company_id": SOC,
                    "hour_account_enabled": True,
                    "hs_routing_policy": "franchise",
                    "hs_franchise_hours_per_period": 10,
                }
            ],
            "employee_modulation_movements": [],
            "employee_modulation_counters": [],
            "employee_overtime_routing_decisions": [],
        }
    )


class _Moteur:
    """Le générateur de bulletins, moteur de calcul compris, réduit à l'essentiel :
    les crochets CET et modulation réels sur un calendrier de 20 jours de 7 h et
    15 h sup, un net de 3 000 €, puis l'enregistrement et l'enrichissement
    réels (avances, prêts) — exactement ce que fait la génération après calcul."""

    def __init__(self) -> None:
        self.appels = 0

    def generate_heures(self, *, employee_id: str, year: int, month: int) -> dict:
        from app.modules.cet.application.payroll_hook import (
            apply_cet_deposits_to_calendar,
            finalize_cet_payroll_application,
        )
        from app.modules.employee_loans.application.payroll_integration import (
            enrich_payslip_after_upsert,
        )
        from app.modules.modulation.application.payroll_hook import (
            apply_modulation_hour_account_to_calendar,
            finalize_modulation_payroll_application,
        )

        self.appels += 1
        calendrier = [{"type": "travail", "heures": 7.0} for _ in range(20)]
        calendrier.append({"type": "travail_hs25", "heures": 15.0})
        calendrier, ids_modulation, _ = apply_modulation_hour_account_to_calendar(
            SOC, employee_id, year, month, calendrier
        )
        calendrier, ids_cet = apply_cet_deposits_to_calendar(employee_id, year, month, calendrier)
        if ids_modulation:
            finalize_modulation_payroll_application(
                ids_modulation, employee_id=employee_id, year=year, month=month
            )
        if ids_cet:
            finalize_cet_payroll_application(ids_cet)
        donnees = {
            "net_a_payer": NET_DU_MOTEUR,
            "salaire_brut": 3900.0,
            "heures_payees": round(sum(j["heures"] for j in calendrier if j["type"] == "travail"), 2),
            "heures_sup_payees": round(
                sum(j["heures"] for j in calendrier if j["type"] == "travail_hs25"), 2
            ),
        }
        enregistre = (
            database.supabase.table("payslips")
            .upsert(
                {
                    "company_id": SOC,
                    "employee_id": employee_id,
                    "year": year,
                    "month": month,
                    "status": "brouillon",
                    "payslip_data": donnees,
                },
                on_conflict="company_id,employee_id,year,month",
            )
            .execute()
        )
        payslip_id = enregistre.data[0]["id"]
        enrichi = enrich_payslip_after_upsert(donnees, employee_id, year, month, payslip_id)
        return {
            "status": "success",
            "message": "ok",
            "download_url": None,
            "payslip_id": payslip_id,
            "net_a_payer": enrichi["net_a_payer"],
        }


@pytest.fixture
def base(monkeypatch):
    memoire = _base_initiale()
    memoire.brancher(monkeypatch)
    moteur = _Moteur()
    with (
        patch.object(commands, "_employee_repository") as fiches,
        patch.object(commands, "enrich_employee_with_exit_context", side_effect=lambda e: e),
        patch.object(commands, "_raison_de_blocage_du_salarie", return_value=None),
        patch.object(commands, "payslip_employment_period_block_reason", return_value=None),
        patch.object(commands, "raison_de_blocage_avant_bascule", return_value=None),
        patch.object(commands, "_periode_a_saisir"),
        patch.object(commands, "_check_heures_sur_jour_d_arret"),
        patch.object(commands, "_check_calendar_guard", return_value=None),
        patch.object(commands, "_archive_before_regeneration"),
        patch.object(commands.employee_statut_reader, "get_employee_statut", return_value="Non-Cadre"),
        patch.object(commands, "payslip_generator_provider", moteur),
        patch(
            "app.modules.payslips.infrastructure.repository.recalculer_credits_repos_employe"
        ),
    ):
        fiches.get_by_id_only.return_value = dict(SALARIE)
        memoire.moteur = moteur
        yield memoire


def _generer() -> None:
    resultat = commands.generate_payslip(GeneratePayslipInput(employee_id=SAL, year=AN, month=MOIS))
    assert resultat.status == "success"


def _bulletin_id(base: BaseEnMemoire) -> str:
    return base.ligne("payslips", employee_id=SAL, year=AN, month=MOIS)["id"]


def _etat(base: BaseEnMemoire) -> dict:
    """Tout ce que la gestionnaire lit dans ses compteurs, au centime."""
    bulletins = base.lignes("payslips", employee_id=SAL, year=AN, month=MOIS)
    donnees = bulletins[0]["payslip_data"] if bulletins else None
    avance = base.ligne("salary_advances", id="avance-1")
    pret = base.ligne("employee_loans", id="pret-1")
    credits = base.lignes("employee_modulation_movements", employee_id=SAL, movement_type="credit_hs")
    return {
        "bulletin": None
        if donnees is None
        else {
            "net_a_payer": round(float(donnees["net_a_payer"]), 2),
            "acomptes_et_avances": donnees["remboursements_avances"]["total_rembourse"],
            "pret": donnees["remboursements_prets"]["total_rembourse"],
            "heures_payees": donnees["heures_payees"],
            "heures_sup_payees": donnees["heures_sup_payees"],
        },
        "avance": (avance["status"], round(float(avance["remaining_amount"]), 2)),
        "remboursements_avance": sorted(
            round(float(l["repayment_amount"]), 2) for l in base.lignes("salary_advance_repayments")
        ),
        "pret": (pret["status"], round(float(pret["remaining_capital"]), 2)),
        "echeances": [
            (e["installment_number"], e["status"], round(float(e["capital_paid"]), 2))
            for e in base.lignes("employee_loan_installments")
            if e["installment_number"] <= 2
        ],
        "retenues_pret": sorted(
            round(float(l["capital_amount"]), 2) for l in base.lignes("employee_loan_repayments")
        ),
        "cet": base.ligne("employee_cet_movements", id="cet-1")["status"],
        "credits_modulation": sorted(round(float(m["hours"]), 2) for m in credits),
    }


ETAT_INITIAL = {
    "bulletin": None,
    "avance": ("paid", 800.0),
    "remboursements_avance": [],
    "pret": ("active", 2250.0),
    "echeances": [(1, "pending", 0.0), (2, "pending", 0.0)],
    "retenues_pret": [],
    "cet": "validated",
    "credits_modulation": [],
}

ETAT_APRES_GENERATION = {
    "bulletin": {
        # 3 000 − 800 (acompte) − 225 (échéance) : chacun retenu une fois.
        "net_a_payer": 1975.0,
        "acomptes_et_avances": 800.0,
        "pret": 225.0,
        # 140 h − 4 h déposées au CET ; 15 h sup − 10 h créditées en modulation.
        "heures_payees": 136.0,
        "heures_sup_payees": 5.0,
    },
    "avance": ("paid", 0.0),
    "remboursements_avance": [800.0],
    "pret": ("active", 2025.0),
    "echeances": [(1, "paid", 225.0), (2, "pending", 0.0)],
    "retenues_pret": [225.0],
    "cet": "applied_payroll",
    "credits_modulation": [10.0],
}


def test_la_premiere_generation_retient_chaque_chose_une_fois(base):
    assert _etat(base) == ETAT_INITIAL

    _generer()

    assert _etat(base) == ETAT_APRES_GENERATION


def test_recalculer_redonne_le_meme_bulletin_et_les_memes_compteurs(base):
    """Avant : échéance et acompte perdus (net 3 000 €), 4 h CET payées de
    nouveau, 15 h sup payées alors que 10 h restaient créditées."""
    _generer()

    _generer()
    assert _etat(base) == ETAT_APRES_GENERATION

    _generer()
    assert _etat(base) == ETAT_APRES_GENERATION


def test_supprimer_rend_tout_puis_regenerer_retient_de_nouveau_une_fois(base):
    _generer()

    assert commands.delete_payslip(_bulletin_id(base)) is True
    assert _etat(base) == ETAT_INITIAL

    _generer()
    assert _etat(base) == ETAT_APRES_GENERATION


def test_une_echeance_reglee_n_est_pas_effacee_avec_le_bulletin(base):
    """La clé `employee_loan_installments.payslip_id` part en cascade avec le
    bulletin : l'échéance réglée par ce bulletin disparaissait de l'échéancier."""
    _generer()
    supprime = _bulletin_id(base)
    commands.delete_payslip(supprime)

    # Plus aucune échéance ne pointe vers lui : la cascade n'a rien à emporter.
    assert base.lignes("employee_loan_installments", payslip_id=supprime) == []
    assert len(base.lignes("employee_loan_installments", loan_id="pret-1")) == 10


def test_une_avance_en_partie_versee_redevient_approuvee_a_la_suppression(monkeypatch):
    """La retenue passe l'avance « approuvée » à « versée » ; la défaire lui
    rend son statut d'après ses versements (500 € versés sur 800 €)."""
    memoire = _base_initiale(statut_avance="approved", verse=500.0)
    memoire.brancher(monkeypatch)
    from app.modules.payslips.application import effets_du_bulletin as effets
    from app.modules.saisies_avances.application.service import enrich_payslip

    memoire.tables["payslips"].append({"id": "bulletin-1", "employee_id": SAL, "year": AN, "month": MOIS})
    enrich_payslip({"net_a_payer": NET_DU_MOTEUR}, SAL, AN, MOIS, payslip_id="bulletin-1")
    assert memoire.ligne("salary_advances", id="avance-1")["status"] == "paid"

    effets.defaire_effets_du_bulletin(SAL, AN, MOIS, payslip_id="bulletin-1")

    avance = memoire.ligne("salary_advances", id="avance-1")
    assert (avance["status"], float(avance["remaining_amount"])) == ("approved", 800.0)
    assert memoire.lignes("salary_advance_repayments") == []


def test_un_depot_cet_debite_a_la_validation_n_est_pas_rouvert(monkeypatch):
    """Réglage « débit à la validation » : le dépôt est marqué appliqué dès sa
    validation, pas par la paie. Défaire le bulletin ne doit pas le rouvrir,
    sinon le recalcul retirerait ces heures du bulletin."""
    memoire = _base_initiale()
    memoire.ligne("employee_cet_movements", id="cet-1")["status"] = "applied_payroll"
    memoire.brancher(monkeypatch)
    from app.modules.payslips.application import effets_du_bulletin as effets

    effets.defaire_effets_du_bulletin(SAL, AN, MOIS, payslip_id=None)

    assert memoire.ligne("employee_cet_movements", id="cet-1")["status"] == "applied_payroll"


def test_une_decision_de_routage_redevient_valide_pour_le_recalcul(base):
    """Routage manuel : la paie passe la décision « appliquée » ; au recalcul,
    elle n'était plus « validée » et toutes les heures sup étaient payées."""
    base.ligne("company_modulation_settings", company_id=SOC)["hs_routing_policy"] = "manual"
    base.tables["employee_overtime_routing_decisions"].append(
        {
            "id": "decision-1",
            "company_id": SOC,
            "employee_id": SAL,
            "year": AN,
            "month": MOIS,
            "total_hs_hours": 15,
            "hours_to_account": 12,
            "hours_to_pay": 3,
            "status": "validated",
        }
    )

    _generer()
    _generer()

    assert _etat(base)["bulletin"]["heures_sup_payees"] == 3.0
    assert _etat(base)["credits_modulation"] == [12.0]
    assert base.ligne("employee_overtime_routing_decisions", id="decision-1")["status"] == "applied_payroll"

    commands.delete_payslip(_bulletin_id(base))
    assert base.ligne("employee_overtime_routing_decisions", id="decision-1")["status"] == "validated"
    assert _etat(base)["credits_modulation"] == []


# --- Ce qui ne se défait pas proprement est refusé, avec quoi faire ---


def test_recalcul_refuse_si_le_pret_a_ete_annule_depuis(base):
    _generer()
    avant = _etat(base)
    base.ligne("employee_loans", id="pret-1").update({"status": "cancelled", "remaining_capital": 0})

    with pytest.raises(PayslipBadRequestError) as refus:
        _generer()

    phrase = str(refus.value)
    assert "225,00 €" in phrase and "Achat véhicule" in phrase and "annulé" in phrase
    assert "tel quel" in phrase
    assert base.moteur.appels == 1
    apres = _etat(base)
    assert apres["retenues_pret"] == avant["retenues_pret"]
    assert apres["avance"] == avant["avance"] and apres["cet"] == avant["cet"]


def test_suppression_refusee_si_le_pret_est_suspendu_et_dit_quoi_faire(base):
    _generer()
    base.ligne("employee_loans", id="pret-1")["status"] = "suspended"

    with pytest.raises(PayslipBadRequestError) as refus:
        commands.delete_payslip(_bulletin_id(base))

    phrase = str(refus.value)
    assert "suspendu" in phrase and "Réactivez le prêt" in phrase and "supprimer" in phrase
    assert base.lignes("payslips", employee_id=SAL)
    assert _etat(base)["retenues_pret"] == [225.0]


def test_la_garde_d_entree_des_corrections_refuse_aussi(base):
    """`corriger_bulletin` appelle `salarie_generable` avant d'écrire la moindre
    variable du mois : le refus y est, une correction n'écrit donc rien."""
    _generer()
    base.ligne("employee_loans", id="pret-1")["status"] = "defaulted"

    with pytest.raises(PayslipBadRequestError):
        commands.salarie_generable(SAL, AN, MOIS)
