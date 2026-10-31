"""
Enrichissement bulletin : remboursements de prêts employeur sur le net à payer.
Remboursement glissant : reprise de l'échéance non soldée mois après mois.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

from app.modules.employee_loans.domain.rules import (
    capital_du_au_debut_du_mois,
    compute_installment_remaining,
    compute_interest_benefit_in_kind,
    compute_loan_repayment_cap,
    is_installment_settled,
    message_pret_retenu_en_partie,
    retenue_dans_le_plafond,
)
from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_capital_repayments,
    get_legal_interest_rate,
    get_suspended_loans_with_pending_installment,
    get_unsettled_installments_for_payroll,
)
from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loan_repayments_repository,
    employee_loans_repository,
)
from app.modules.saisies_avances.domain.rules import (
    base_saisissable,
    calculate_seizable_amount,
    resoudre_bareme_quotite,
)
from app.modules.saisies_avances.infrastructure.queries import (
    get_bareme_quotite_saisissable,
)

logger = get_logger("modules.employee_loans.enrichment")


def process_suspended_loan_installments(
    employee_id: str,
    year: int,
    month: int,
) -> None:
    """Marque skipped les échéances pending/partial des prêts suspendus pour ce mois."""
    suspended = get_suspended_loans_with_pending_installment(employee_id, year, month)
    for item in suspended:
        installment = item.get("installment") or {}
        inst_id = installment.get("id")
        if inst_id:
            try:
                employee_loan_installments_repository.update(
                    inst_id, {"status": "skipped"}
                )
            except Exception:
                pass


def enrich_payslip_loans(
    payslip_json_data: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
    payslip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Applique les retenues de remboursement de prêt sur le net à payer.
    Reprend la plus ancienne échéance non soldée ; plafonné à ce qui reste de la
    quotité saisissable du mois après les saisies sur salaire (Cass. soc.,
    15 janvier 2014, n° 12-19.739), et au net encore disponible.
    Une échéance retenue en partie, ou pas du tout, le dit au bulletin
    (`alertes_baremes`) : combien, sur combien, la règle et le reliquat.
    """
    process_suspended_loan_installments(employee_id, year, month)

    net_a_payer = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
    quotite_du_mois, annee_bareme, pris_par_les_saisies = _quotite_du_mois(
        payslip_json_data, year, month
    )
    net_restant = net_a_payer
    pris_par_les_prets = Decimal("0")

    loans_due = get_unsettled_installments_for_payroll(employee_id, year, month)
    legal_rate = get_legal_interest_rate()

    total_capital = Decimal("0")
    total_interest = Decimal("0")
    total_an = Decimal("0")
    remboursements: List[Dict[str, Any]] = []

    def _alerter(
        loan: Dict[str, Any],
        installment: Dict[str, Any],
        capital: Decimal,
        interets: Decimal,
        prevu: Decimal,
        reliquat: Decimal,
        quotite_restante: Decimal,
        net_disponible: Decimal,
    ) -> None:
        payslip_json_data.setdefault("alertes_baremes", []).append(
            {
                "code": CODE_ALERTE_RETENUE_PARTIELLE,
                "severity": "warning",
                "message": message_pret_retenu_en_partie(
                    motif=loan.get("reason"),
                    numero=installment.get("installment_number"),
                    capital_retenu=capital,
                    interets_retenus=interets,
                    prevu=prevu,
                    reliquat=reliquat,
                    quotite_du_mois=quotite_du_mois,
                    annee_bareme=annee_bareme,
                    pris_par_les_saisies=pris_par_les_saisies,
                    quotite_restante=quotite_restante,
                    net_disponible=net_disponible,
                ),
            }
        )

    for item in loans_due:
        loan = item
        installment = item.get("installment") or {}
        loan_id = loan["id"]
        inst_id = installment.get("id")

        if payslip_id:
            existing = employee_loan_repayments_repository.get_existing(
                loan_id, payslip_id
            )
            if existing:
                cap = Decimal(str(existing.get("capital_amount", 0)))
                intr = Decimal(str(existing.get("interest_amount", 0)))
                total_capital += cap
                total_interest += intr
                total_an += Decimal(
                    str(existing.get("avantage_nature_amount", 0))
                )
                remboursements.append(
                    _build_remboursement_entry(
                        loan, installment, cap, intr,
                        Decimal(str(existing.get("remaining_after", 0))),
                        existing.get("installment_id"),
                    )
                )
                continue

        capital_part = Decimal(str(installment.get("capital_part", 0)))
        interest_part = Decimal(str(installment.get("interest_part", 0)))
        capital_paid_so_far = Decimal(str(installment.get("capital_paid") or 0))
        interest_paid_so_far = Decimal(str(installment.get("interest_paid") or 0))
        remaining_capital = Decimal(str(loan.get("remaining_capital", 0)))

        due_capital, due_interest = compute_installment_remaining(
            capital_part,
            interest_part,
            capital_paid_so_far,
            interest_paid_so_far,
        )

        if quotite_du_mois is None:
            quotite_restante = Decimal("0")
            plafond = Decimal("0")
        else:
            quotite_restante = quotite_du_mois - pris_par_les_saisies - pris_par_les_prets
            plafond = compute_loan_repayment_cap(
                quotite_du_mois=quotite_du_mois,
                deja_pris=pris_par_les_saisies + pris_par_les_prets,
                net_disponible=net_restant,
            )

        if plafond <= 0:
            # Plus rien à retenir ce mois-ci (net nul, quotité prise par les
            # saisies ou un autre prêt, barème absent) : l'échéance reste due,
            # et le bulletin le dit.
            if due_capital > 0 or due_interest > 0:
                du = _money(due_capital + due_interest)
                _alerter(
                    loan, installment, Decimal("0"), Decimal("0"), du, du,
                    quotite_restante, net_restant,
                )
            continue

        if due_capital <= 0 and due_interest <= 0:
            if inst_id:
                try:
                    employee_loan_installments_repository.update(
                        inst_id, {"status": "paid", "payslip_id": payslip_id}
                    )
                except Exception:
                    pass
            continue

        capital_paid_this, interest_paid_this = retenue_dans_le_plafond(
            due_capital, due_interest, plafond, remaining_capital
        )

        # L'avantage en nature du mois : l'intérêt épargné sur le capital dû au
        # début du mois, comme la ligne « Avantages en nature » du brut
        # (`compute_total_loan_benefit_in_kind`). Il ne dépend pas de ce que le
        # bulletin a pu retenir : réduit au prorata du capital retenu, il
        # valait 4,10 € quand la ligne imprimée disait 5,04 € (rejeu G.3).
        an_amount = compute_interest_benefit_in_kind(
            _capital_du_au_debut_du_mois(loan, remaining_capital, year, month),
            legal_rate,
            Decimal(str(loan.get("annual_interest_rate", 0))),
        )

        net_avant = net_restant
        pris_par_les_prets += capital_paid_this + interest_paid_this
        net_restant -= capital_paid_this + interest_paid_this
        total_capital += capital_paid_this
        total_interest += interest_paid_this
        total_an += an_amount

        remaining_after = _money(
            max(Decimal("0"), remaining_capital - capital_paid_this)
        )
        new_capital_paid = capital_paid_so_far + capital_paid_this
        new_interest_paid = interest_paid_so_far + interest_paid_this

        reliquat_capital, reliquat_interest = compute_installment_remaining(
            capital_part,
            interest_part,
            new_capital_paid,
            new_interest_paid,
        )
        reliquat_apres = _money(reliquat_capital + reliquat_interest)
        solde = (
            is_installment_settled(
                capital_part, interest_part, new_capital_paid, new_interest_paid
            )
            or remaining_after <= 0
        )
        if not solde and reliquat_apres > 0:
            _alerter(
                loan,
                installment,
                capital_paid_this,
                interest_paid_this,
                _money(due_capital + due_interest),
                reliquat_apres,
                quotite_restante,
                net_avant,
            )

        remboursements.append(
            _build_remboursement_entry(
                loan,
                installment,
                capital_paid_this,
                interest_paid_this,
                remaining_after,
                inst_id,
                reliquat_apres=reliquat_apres,
            )
        )

        total_paid_this_month = capital_paid_this + interest_paid_this
        if total_paid_this_month > 0 and payslip_id:
            settled = is_installment_settled(
                capital_part,
                interest_part,
                new_capital_paid,
                new_interest_paid,
            ) or remaining_after <= 0
            inst_status = "paid" if settled else "partial"

            try:
                repayment_payload: Dict[str, Any] = {
                    "loan_id": loan_id,
                    "payslip_id": payslip_id,
                    "year": year,
                    "month": month,
                    "capital_amount": float(capital_paid_this),
                    "interest_amount": float(interest_paid_this),
                    "avantage_nature_amount": float(an_amount),
                    "remaining_after": float(remaining_after),
                }
                if inst_id:
                    repayment_payload["installment_id"] = inst_id
                employee_loan_repayments_repository.create(repayment_payload)
            except Exception:
                pass

            try:
                update_loan: Dict[str, Any] = {
                    "remaining_capital": float(remaining_after),
                }
                if remaining_after <= 0:
                    update_loan["status"] = "repaid"
                employee_loans_repository.update(loan_id, update_loan)
            except Exception:
                pass

            if inst_id:
                try:
                    employee_loan_installments_repository.increment_paid(
                        inst_id,
                        float(capital_paid_this),
                        float(interest_paid_this),
                        inst_status,
                        payslip_id=payslip_id if settled else None,
                    )
                except Exception:
                    pass

    total_rembourse = total_capital + total_interest
    payslip_json_data["remboursements_prets"] = {
        "total_rembourse": float(total_rembourse),
        "total_capital": float(total_capital),
        "total_interets": float(total_interest),
        "avantage_nature_interets": float(total_an),
        "prets": remboursements,
    }

    if total_rembourse > 0:
        current_net = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
        payslip_json_data["net_a_payer"] = float(
            max(Decimal("0"), current_net - total_rembourse)
        )

    return payslip_json_data


CODE_ALERTE_RETENUE_PARTIELLE = "pret_employeur_retenue_partielle"


def _quotite_du_mois(
    bulletin: Dict[str, Any], year: int, month: int
) -> tuple[Optional[Decimal], Optional[int], Decimal]:
    """La quotité saisissable du mois, l'année de son barème et ce que les saisies
    sur salaire en ont déjà pris. La base est celle des saisies, prise avant les
    retenues : les saisies et les avances déjà retirées du net y reviennent. Les
    personnes à charge sont celles de la saisie en cours, sinon aucune. Sans
    barème : (None, None, pris)."""
    saisies = bulletin.get("retenues_saisies") or {}
    pris = Decimal(str(saisies.get("total_preleve") or 0)) + Decimal(
        str(saisies.get("total_en_variables") or 0)
    )
    try:
        bareme, _messages = resoudre_bareme_quotite(
            get_bareme_quotite_saisissable(), year, month
        )
    except Exception:  # noqa: BLE001 — sans barème, rien n'est retenu et le bulletin le dit
        logger.warning("Barème de la quotité saisissable illisible", exc_info=True)
        bareme = None
    if bareme is None:
        return None, None, pris
    avances = Decimal(
        str((bulletin.get("remboursements_avances") or {}).get("total_rembourse") or 0)
    )
    base = base_saisissable(bulletin) + Decimal(str(saisies.get("total_preleve") or 0)) + avances
    personnes = int(saisies.get("personnes_a_charge") or 0)
    return calculate_seizable_amount(base, personnes, bareme), int(bareme["annee"]), pris


def _capital_du_au_debut_du_mois(
    loan: Dict[str, Any], remaining_capital: Decimal, year: int, month: int
) -> Decimal:
    """Le capital dû au début du mois du bulletin, comme pour la ligne du brut ;
    à défaut de date de début, le capital restant du prêt."""
    if not loan.get("start_date") or loan.get("principal_amount") is None:
        return remaining_capital
    try:
        remboursements = get_capital_repayments([str(loan["id"])])
        return capital_du_au_debut_du_mois(loan, remboursements, year, month)
    except Exception:  # noqa: BLE001 — l'avantage retombe sur le capital restant
        return remaining_capital


def _build_remboursement_entry(
    loan: Dict[str, Any],
    installment: Dict[str, Any],
    capital: Decimal,
    interest: Decimal,
    remaining_after: Decimal,
    installment_id: Optional[str],
    reliquat_apres: Optional[Decimal] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "loan_id": loan["id"],
        "installment_id": installment_id,
        "installment_number": installment.get("installment_number"),
        "montant_capital": float(capital),
        "montant_interets": float(interest),
        "reste_apres": float(remaining_after),
        "motif": loan.get("reason"),
    }
    if reliquat_apres is not None:
        entry["reliquat_apres"] = float(reliquat_apres)
    return entry


def _money(value: Decimal) -> Decimal:
    from decimal import ROUND_HALF_UP

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
