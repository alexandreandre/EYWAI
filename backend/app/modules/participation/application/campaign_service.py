"""Service applicatif — campagnes bulletin d'option."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.documents.application.commands import update_document_status
from app.modules.documents.schemas.requests import UpdateDocumentStatusRequest
from app.modules.monthly_inputs.application.commands import create_monthly_inputs_batch
from app.modules.monthly_inputs.schemas.requests import MonthlyInput
from app.modules.participation.application.participation_notifications import (
    notify_bulletin_reminder,
    notify_bulletin_to_respond,
    notify_rh_default_pee_applied,
    notify_rh_late_bulletins,
)
from app.modules.participation.domain.bulletin_rules import (
    DEFAULT_CLAUSE_15J,
    ChoiceType,
    compute_net_after_advances,
    dispositif_label,
    document_type_for_dispositif,
    payroll_flags_for_amount,
    split_amount_by_choice,
)
from app.modules.participation.infrastructure.campaign_repository import (
    campaign_repository,
)
from app.modules.participation.infrastructure.repository import (
    ParticipationSimulationRepository,
)
from app.modules.participation.schemas.campaign_requests import (
    BulletinRespondRequest,
    GeneratePayrollLinesRequest,
    ParticipationCampaignCreate,
)
from app.modules.participation.schemas.campaign_responses import (
    CampaignStats,
    ParticipationBulletinItem,
    ParticipationCampaignDetail,
    ParticipationCampaignListItem,
)
from app.services.document_service import document_service

logger = logging.getLogger(__name__)

_sim_repo = ParticipationSimulationRepository()


def _fmt_money_fr(value: Decimal | float) -> str:
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    s = f"{d:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def _stats_from_counts(counts: Dict[str, int]) -> CampaignStats:
    return CampaignStats(
        total=sum(counts.values()),
        pending=counts.get("pending", 0),
        sent=counts.get("sent", 0),
        responded=counts.get("responded", 0),
        default_pee=counts.get("default_pee", 0),
        cancelled=counts.get("cancelled", 0),
    )


def _campaign_detail(row: Dict[str, Any]) -> ParticipationCampaignDetail:
    counts = campaign_repository.count_bulletins_by_status(str(row["id"]))
    return ParticipationCampaignDetail(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        simulation_id=str(row["simulation_id"]) if row.get("simulation_id") else None,
        year=int(row["year"]),
        exercise_label=str(row.get("exercise_label") or ""),
        status=str(row["status"]),
        payroll_year=int(row["payroll_year"]) if row.get("payroll_year") else None,
        payroll_month=int(row["payroll_month"]) if row.get("payroll_month") else None,
        sent_at=row.get("sent_at"),
        deadline_at=row.get("deadline_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stats=_stats_from_counts(counts),
    )


def _bulletin_item(
    row: Dict[str, Any],
    *,
    campaign: Optional[Dict[str, Any]] = None,
) -> ParticipationBulletinItem:
    emp = row.get("employees") if isinstance(row.get("employees"), dict) else {}
    camp = row.get("participation_campaigns")
    if isinstance(camp, dict):
        campaign = camp
    return ParticipationBulletinItem(
        id=str(row["id"]),
        campaign_id=str(row["campaign_id"]),
        employee_id=str(row["employee_id"]),
        employee_first_name=emp.get("first_name") if emp else None,
        employee_last_name=emp.get("last_name") if emp else None,
        dispositif_type=str(row["dispositif_type"]),
        gross_amount=float(row.get("gross_amount") or 0),
        csg_non_deductible=float(row.get("csg_non_deductible") or 0),
        csg_deductible=float(row.get("csg_deductible") or 0),
        advance_amount=float(row.get("advance_amount") or 0),
        advance_label=str(row.get("advance_label") or ""),
        net_amount=float(row.get("net_amount") or 0),
        generated_document_id=str(row["generated_document_id"])
        if row.get("generated_document_id")
        else None,
        status=str(row["status"]),
        choice_type=row.get("choice_type"),
        choice_cash_amount=float(row["choice_cash_amount"])
        if row.get("choice_cash_amount") is not None
        else None,
        pee_amount=float(row["pee_amount"]) if row.get("pee_amount") is not None else None,
        cash_amount=float(row["cash_amount"]) if row.get("cash_amount") is not None else None,
        responded_at=row.get("responded_at"),
        deadline_at=campaign.get("deadline_at") if campaign else None,
        exercise_label=str(campaign.get("exercise_label") or "") if campaign else None,
        year=int(campaign["year"]) if campaign and campaign.get("year") else None,
    )


def _load_company(company_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    if not r or not r.data:
        raise LookupError("Entreprise introuvable.")
    return dict(r.data)


def _load_employee(employee_id: str, company_id: str) -> Dict[str, Any]:
    r = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not r or not r.data:
        raise LookupError(f"Salarié introuvable : {employee_id}")
    return dict(r.data)


def _resolve_template_id(company_id: str, document_type: str) -> str:
    bundle = document_service.get_active_template(company_id, document_type)
    if bundle and bundle.get("template"):
        return str(bundle["template"]["id"])
    label = "participation" if document_type == "bulletin_participation" else "intéressement"
    raise ValueError(
        f"Aucun modèle de bulletin d'option {label} configuré — "
        "importez un fichier dans la bibliothèque de documents."
    )


def _build_bulletin_context(
    *,
    year: int,
    dispositif_type: str,
    gross: float,
    advance_amount: float,
    advance_label: str,
) -> Dict[str, str]:
    non_ded, ded, net_before, net_final = compute_net_after_advances(gross, advance_amount)
    today = date.today()
    exercise_start = date(year, 1, 1)
    exercise_end = date(year, 12, 31)
    return {
        "exercice": str(year),
        "exercice_debut": exercise_start.strftime("%d/%m/%Y"),
        "exercice_fin": exercise_end.strftime("%d/%m/%Y"),
        "date_emission": today.strftime("%d/%m/%Y"),
        "montant_brut": _fmt_money_fr(gross),
        "csg_non_deductible": _fmt_money_fr(non_ded),
        "csg_deductible": _fmt_money_fr(ded),
        "acompte": _fmt_money_fr(advance_amount) if advance_amount > 0 else "0,00 €",
        "acompte_libelle": advance_label or "",
        "net_a_payer": _fmt_money_fr(net_before),
        "net_a_payer_final": _fmt_money_fr(net_final),
        "type_dispositif": dispositif_label(dispositif_type),
        "clause_defaut_15j": DEFAULT_CLAUSE_15J,
    }


def _amounts_from_simulation(
    simulation_id: str, company_id: str
) -> List[Tuple[str, float, float]]:
    sim = _sim_repo.get_by_id(simulation_id, company_id)
    if not sim:
        raise LookupError("Simulation introuvable.")
    raw = sim.results_data or {}
    out: List[Tuple[str, float, float]] = []
    for emp_id, data in raw.items():
        if not isinstance(data, dict):
            continue
        part = float(data.get("participationAmount") or 0)
        inter = float(data.get("interessementAmount") or 0)
        if part > 0.005 or inter > 0.005:
            out.append((str(emp_id), part, inter))
    return out


def create_campaign(
    company_id: str,
    created_by: str,
    body: ParticipationCampaignCreate,
) -> Tuple[ParticipationCampaignDetail, int]:
    amounts: List[Tuple[str, float, float]] = []
    if body.amounts:
        for a in body.amounts:
            amounts.append((a.employee_id, a.participation_amount, a.interessement_amount))
    elif body.simulation_id:
        amounts = _amounts_from_simulation(body.simulation_id, company_id)
    else:
        raise ValueError("Fournissez simulation_id ou amounts.")

    exercise_label = body.exercise_label.strip() or f"PARTICIPATION {body.year}"

    campaign = campaign_repository.create_campaign(
        {
            "company_id": company_id,
            "simulation_id": body.simulation_id,
            "year": body.year,
            "exercise_label": exercise_label,
            "status": "draft",
            "payroll_year": body.payroll_year,
            "payroll_month": body.payroll_month,
            "created_by": created_by,
        }
    )
    campaign_id = str(campaign["id"])

    advance_map = {a.employee_id: a for a in body.advances}
    if body.advances:
        campaign_repository.upsert_advances(
            campaign_id,
            [
                {
                    "employee_id": a.employee_id,
                    "amount": a.amount,
                    "label": a.label,
                }
                for a in body.advances
            ],
        )

    bulletin_rows: List[Dict[str, Any]] = []
    for emp_id, part_amt, inter_amt in amounts:
        adv = advance_map.get(emp_id)
        advance_amount = float(adv.amount) if adv else 0.0
        advance_label = adv.label if adv else ""

        if part_amt > 0.005:
            non_ded, ded, _, net_final = compute_net_after_advances(
                part_amt, advance_amount
            )
            bulletin_rows.append(
                {
                    "campaign_id": campaign_id,
                    "company_id": company_id,
                    "employee_id": emp_id,
                    "dispositif_type": "participation",
                    "gross_amount": round(part_amt, 2),
                    "csg_non_deductible": float(non_ded),
                    "csg_deductible": float(ded),
                    "advance_amount": round(advance_amount, 2),
                    "advance_label": advance_label,
                    "net_amount": float(net_final),
                    "status": "pending",
                }
            )
        if inter_amt > 0.005:
            non_ded, ded, _, net_final = compute_net_after_advances(inter_amt, 0)
            bulletin_rows.append(
                {
                    "campaign_id": campaign_id,
                    "company_id": company_id,
                    "employee_id": emp_id,
                    "dispositif_type": "interessement",
                    "gross_amount": round(inter_amt, 2),
                    "csg_non_deductible": float(non_ded),
                    "csg_deductible": float(ded),
                    "advance_amount": 0,
                    "advance_label": "",
                    "net_amount": float(net_final),
                    "status": "pending",
                }
            )

    if not bulletin_rows:
        raise ValueError("Aucun montant participation/intéressement à traiter.")

    campaign_repository.insert_bulletins(bulletin_rows)
    refreshed = campaign_repository.get_campaign(campaign_id, company_id)
    assert refreshed
    return _campaign_detail(refreshed), len(bulletin_rows)


def list_campaigns(
    company_id: str, year: Optional[int] = None
) -> List[ParticipationCampaignListItem]:
    rows = campaign_repository.list_campaigns(company_id, year)
    items: List[ParticipationCampaignListItem] = []
    for row in rows:
        detail = _campaign_detail(row)
        items.append(
            ParticipationCampaignListItem(
                id=detail.id,
                year=detail.year,
                exercise_label=detail.exercise_label,
                status=detail.status,
                sent_at=detail.sent_at,
                deadline_at=detail.deadline_at,
                created_at=detail.created_at,
                stats=detail.stats,
            )
        )
    return items


def get_campaign_detail(
    campaign_id: str, company_id: str
) -> ParticipationCampaignDetail:
    row = campaign_repository.get_campaign(campaign_id, company_id)
    if not row:
        raise LookupError("Campagne introuvable.")
    return _campaign_detail(row)


def list_campaign_bulletins(
    campaign_id: str, company_id: str
) -> List[ParticipationBulletinItem]:
    campaign = campaign_repository.get_campaign(campaign_id, company_id)
    if not campaign:
        raise LookupError("Campagne introuvable.")
    rows = campaign_repository.list_bulletins(campaign_id)
    return [_bulletin_item(r, campaign=campaign) for r in rows]


def publish_campaign(
    campaign_id: str,
    company_id: str,
    published_by: str,
) -> ParticipationCampaignDetail:
    campaign = campaign_repository.get_campaign(campaign_id, company_id)
    if not campaign:
        raise LookupError("Campagne introuvable.")
    if campaign["status"] not in ("draft", "open"):
        raise ValueError("Cette campagne ne peut plus être publiée.")

    company_data = _load_company(company_id)
    year = int(campaign["year"])
    bulletins = campaign_repository.list_bulletins(campaign_id, status="pending")
    if not bulletins:
        bulletins = [
            b
            for b in campaign_repository.list_bulletins(campaign_id)
            if b.get("status") == "sent"
        ]

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=15)
    deadline_str = deadline.strftime("%d/%m/%Y")

    for bulletin in bulletins:
        if bulletin.get("status") not in ("pending",):
            continue
        emp_id = str(bulletin["employee_id"])
        dispositif = str(bulletin["dispositif_type"])
        doc_type = document_type_for_dispositif(dispositif)
        template_id = _resolve_template_id(company_id, doc_type)
        employee_data = _load_employee(emp_id, company_id)
        ctx_fields = _build_bulletin_context(
            year=year,
            dispositif_type=dispositif,
            gross=float(bulletin["gross_amount"]),
            advance_amount=float(bulletin.get("advance_amount") or 0),
            advance_label=str(bulletin.get("advance_label") or ""),
        )
        gen = document_service.generate_document(
            company_id=company_id,
            employee_id=emp_id,
            document_type=doc_type,
            category="attestation_courante",
            employee_data=employee_data,
            company_data=company_data,
            context={"custom_fields": ctx_fields},
            generated_by=published_by,
            template_id_override=template_id,
        )
        doc_id = str(gen.get("document_id") or "")
        if doc_id:
            update_document_status(
                doc_id,
                company_id,
                UpdateDocumentStatusRequest(status="envoye"),
                updated_by_user_id=published_by,
            )
        campaign_repository.update_bulletin(
            str(bulletin["id"]),
            {
                "generated_document_id": doc_id or None,
                "status": "sent",
            },
        )
        notify_bulletin_to_respond(
            emp_id,
            company_id,
            dispositif_label=dispositif_label(dispositif),
            year=year,
            deadline_str=deadline_str,
        )

    updated = campaign_repository.update_campaign(
        campaign_id,
        {
            "status": "open",
            "sent_at": now.isoformat(),
            "deadline_at": deadline.isoformat(),
        },
    )
    return _campaign_detail(updated)


def respond_to_bulletin(
    bulletin_id: str,
    employee_id: str,
    company_id: str,
    body: BulletinRespondRequest,
) -> ParticipationBulletinItem:
    bulletin = campaign_repository.get_bulletin_for_employee(bulletin_id, employee_id)
    if not bulletin or str(bulletin.get("company_id")) != company_id:
        raise LookupError("Bulletin introuvable.")
    if bulletin.get("status") != "sent":
        raise ValueError("Ce bulletin n'est plus en attente de réponse.")

    choice: ChoiceType = body.choice_type
    net = float(bulletin.get("net_amount") or 0)
    if choice == "partial_cash":
        if body.choice_cash_amount is None:
            raise ValueError("Indiquez le montant en numéraire.")
        if body.choice_cash_amount <= 0 or body.choice_cash_amount > net:
            raise ValueError("Montant en numéraire invalide.")

    split = split_amount_by_choice(choice, net, body.choice_cash_amount)
    now = datetime.now(timezone.utc).isoformat()
    updated = campaign_repository.update_bulletin(
        bulletin_id,
        {
            "status": "responded",
            "choice_type": choice,
            "choice_cash_amount": float(body.choice_cash_amount or 0)
            if choice == "partial_cash"
            else None,
            "pee_amount": float(split.pee_amount),
            "cash_amount": float(split.cash_amount),
            "responded_at": now,
        },
    )
    campaign = campaign_repository.get_campaign(str(bulletin["campaign_id"]), company_id)
    return _bulletin_item(updated, campaign=campaign)


def close_defaults(
    campaign_id: str, company_id: str, rh_employee_id: Optional[str] = None
) -> Tuple[ParticipationCampaignDetail, int]:
    campaign = campaign_repository.get_campaign(campaign_id, company_id)
    if not campaign:
        raise LookupError("Campagne introuvable.")

    pending = campaign_repository.list_bulletins(campaign_id, status="sent")
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for bulletin in pending:
        net = float(bulletin.get("net_amount") or 0)
        split = split_amount_by_choice("full_pee", net)
        campaign_repository.update_bulletin(
            str(bulletin["id"]),
            {
                "status": "default_pee",
                "choice_type": "full_pee",
                "pee_amount": float(split.pee_amount),
                "cash_amount": float(split.cash_amount),
                "responded_at": now,
            },
        )
        count += 1

    if rh_employee_id and count > 0:
        notify_rh_default_pee_applied(
            rh_employee_id,
            company_id,
            count=count,
            year=int(campaign["year"]),
        )

    updated = campaign_repository.update_campaign(campaign_id, {"status": "closed"})
    return _campaign_detail(updated), count


def remind_late(
    campaign_id: str, company_id: str, rh_employee_id: Optional[str] = None
) -> int:
    campaign = campaign_repository.get_campaign(campaign_id, company_id)
    if not campaign:
        raise LookupError("Campagne introuvable.")
    if campaign.get("status") != "open":
        return 0

    deadline = campaign.get("deadline_at")
    days_left = 5
    if deadline:
        try:
            if isinstance(deadline, str):
                dl = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            else:
                dl = deadline
            days_left = max(0, (dl - datetime.now(timezone.utc)).days)
        except (ValueError, TypeError):
            pass

    late = campaign_repository.list_bulletins(campaign_id, status="sent")
    year = int(campaign["year"])
    for bulletin in late:
        notify_bulletin_reminder(
            str(bulletin["employee_id"]),
            company_id,
            dispositif_label=dispositif_label(str(bulletin["dispositif_type"])),
            year=year,
            days_left=days_left,
        )

    if rh_employee_id and late:
        notify_rh_late_bulletins(
            rh_employee_id, company_id, count=len(late), year=year
        )
    return len(late)


def generate_payroll_lines(
    campaign_id: str,
    company_id: str,
    body: GeneratePayrollLinesRequest,
) -> Tuple[ParticipationCampaignDetail, int]:
    campaign = campaign_repository.get_campaign(campaign_id, company_id)
    if not campaign:
        raise LookupError("Campagne introuvable.")

    bulletins = campaign_repository.list_bulletins(campaign_id)
    actionable = [
        b
        for b in bulletins
        if b.get("status") in ("responded", "default_pee")
        and b.get("choice_type")
    ]
    if not actionable:
        raise ValueError("Aucune réponse enregistrée pour générer les saisies.")

    year = int(campaign["year"])
    payloads: List[MonthlyInput] = []

    for bulletin in actionable:
        emp_id = str(bulletin["employee_id"])
        dispositif = str(bulletin["dispositif_type"])
        label = dispositif_label(dispositif)
        cash = float(bulletin.get("cash_amount") or 0)
        pee = float(bulletin.get("pee_amount") or 0)
        bulletin_id = str(bulletin["id"])

        if cash > 0.005:
            social, taxable = payroll_flags_for_amount(True)
            payloads.append(
                MonthlyInput(
                    employee_id=emp_id,  # type: ignore[arg-type]
                    year=body.payroll_year,
                    month=body.payroll_month,
                    name=f"{label} {year} — numéraire",
                    description=f"{label} exercice {year} (partie versée)",
                    amount=round(cash, 2),
                    is_socially_taxed=social,
                    is_taxable=taxable,
                )
            )
        if pee > 0.005:
            social, taxable = payroll_flags_for_amount(False)
            payloads.append(
                MonthlyInput(
                    employee_id=emp_id,  # type: ignore[arg-type]
                    year=body.payroll_year,
                    month=body.payroll_month,
                    name=f"{label} {year} — PEE",
                    description=f"{label} exercice {year} (partie placée PEE)",
                    amount=round(pee, 2),
                    is_socially_taxed=social,
                    is_taxable=taxable,
                )
            )

    if not payloads:
        raise ValueError("Aucune ligne de paie à créer.")

    create_monthly_inputs_batch(payloads)
    # Traçabilité campagne sur les lignes créées (best effort)
    try:
        supabase.table("monthly_inputs").update(
            {"participation_campaign_id": campaign_id}
        ).eq("year", body.payroll_year).eq("month", body.payroll_month).is_(
            "participation_campaign_id", "null"
        ).execute()
    except Exception as exc:
        logger.info("[participation] campaign_id trace skipped: %s", exc)

    updated = campaign_repository.update_campaign(campaign_id, {"status": "closed"})
    return _campaign_detail(updated), len(payloads)


def list_employee_bulletins(
    employee_id: str, company_id: str
) -> List[ParticipationBulletinItem]:
    rows = campaign_repository.list_bulletins_for_employee(employee_id, company_id)
    return [_bulletin_item(r) for r in rows]


def get_employee_bulletin(
    bulletin_id: str, employee_id: str, company_id: str
) -> ParticipationBulletinItem:
    row = campaign_repository.get_bulletin_for_employee(bulletin_id, employee_id)
    if not row or str(row.get("company_id")) != company_id:
        raise LookupError("Bulletin introuvable.")
    campaign = campaign_repository.get_campaign(str(row["campaign_id"]), company_id)
    return _bulletin_item(row, campaign=campaign)
