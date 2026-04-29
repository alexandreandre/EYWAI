"""Routeur global : agrège les routers des modules app.modules."""

import json
import logging

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

from app.modules.access_control.api.router import router as access_control_router
from app.modules.absences.api.router import router as absences_router
from app.modules.annual_reviews.api.router import router as annual_reviews_router
from app.modules.interview_templates.api.router import router as interview_templates_router
from app.modules.certifications.api.router import router as certifications_router
from app.modules.objectives.api.router import router as objectives_router
from app.modules.training.api.router import router as training_router
from app.modules.training_budget.api.router import router as training_budget_router
from app.modules.legal_obligations.api.router import router as legal_obligations_router
from app.modules.competencies.api.router import router as competencies_router
from app.modules.auth.api.router import router as auth_router
from app.modules.bonus_types.api.router import router as bonus_types_router
from app.modules.companies.api.router import router as companies_router
from app.modules.contract_parser.api.router import router as contract_parser_router
from app.modules.copilot.api.router import (
    router as copilot_router,
    router_agent as copilot_agent_router,
)
from app.modules.collective_agreements.api.router import (
    router as collective_agreements_router,
    router_chat as collective_agreements_chat_router,
)
from app.modules.company_groups.api.router import router as company_groups_router
from app.modules.cse.api.router import router as cse_router
from app.modules.dashboard.api.router import router as dashboard_router
from app.modules.employees.api.router import router as employees_router
from app.modules.employee_exits.api.router import router as employee_exits_router
from app.modules.exports.api.router import router as exports_router
from app.modules.expenses.api.router import router as expenses_router
from app.modules.monthly_inputs.api.router import router as monthly_inputs_router
from app.modules.notifications.api.router import router as notifications_router
from app.modules.maintenance_settings.api.router import router as maintenance_settings_router
from app.modules.document_library.api.router import router as document_library_router
from app.modules.documents.api.router import router as documents_router
from app.modules.medical_follow_up.api.router import router as medical_follow_up_router
from app.modules.mutuelle_types.api.router import router as mutuelle_types_router
from app.modules.participation.api.router import router as participation_router
from app.modules.payroll.api.router import router as payroll_simulation_router
from app.modules.payslips.api.router import router as payslips_router
from app.modules.promotions.api.router import router as promotions_router
from app.modules.rates.api.router import router as rates_router
from app.modules.recruitment.api.router import router as recruitment_router
from app.modules.repos_compensateur.api.router import (
    router as repos_compensateur_router,
)
from app.modules.saisies_avances.api.router import router as saisies_avances_router
from app.modules.scraping.api.router import router as scraping_router
from app.modules.residence_permits.api.router import router as residence_permits_router
from app.modules.rib_alerts.api.router import router as rib_alerts_router
from app.modules.badgeuse.api.router import (
    router_me as badgeuse_router_me,
    router_rh as badgeuse_router_rh,
)
from app.modules.schedules.api.router import (
    router as schedules_router,
    router_me as schedules_router_me,
    router_rh as schedules_router_rh,
)
from app.modules.super_admin.api.router import router as super_admin_router
from app.modules.support.api.router import router as support_router
from app.modules.uploads.api.router import router as uploads_router
from app.modules.users.api.router import router as users_router

router = APIRouter()

router.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
router.include_router(access_control_router)
router.include_router(annual_reviews_router)
router.include_router(interview_templates_router)
router.include_router(certifications_router)
router.include_router(objectives_router)
router.include_router(training_router)
router.include_router(training_budget_router)
router.include_router(legal_obligations_router)
router.include_router(competencies_router)
router.include_router(companies_router, prefix="/api/company")
router.include_router(contract_parser_router)
router.include_router(copilot_router, prefix="/api/copilot")
router.include_router(copilot_agent_router, prefix="/api/copilot")
router.include_router(collective_agreements_router)
router.include_router(collective_agreements_chat_router)
router.include_router(company_groups_router)
router.include_router(cse_router)
router.include_router(dashboard_router)
router.include_router(employees_router)
router.include_router(employee_exits_router)
router.include_router(exports_router)
router.include_router(absences_router)
router.include_router(monthly_inputs_router)
router.include_router(notifications_router)
router.include_router(maintenance_settings_router)
router.include_router(document_library_router)
router.include_router(documents_router)
router.include_router(expenses_router)
router.include_router(medical_follow_up_router, prefix="/api/medical-follow-up")
router.include_router(mutuelle_types_router)
router.include_router(bonus_types_router)
router.include_router(participation_router)
router.include_router(payslips_router)
router.include_router(payroll_simulation_router)
router.include_router(promotions_router)
router.include_router(recruitment_router)
router.include_router(repos_compensateur_router)
router.include_router(saisies_avances_router)
router.include_router(scraping_router)
router.include_router(residence_permits_router)
router.include_router(rib_alerts_router)
router.include_router(rates_router, prefix="/api/rates", tags=["Rates"])
router.include_router(schedules_router)
router.include_router(schedules_router_me)
router.include_router(schedules_router_rh)
router.include_router(super_admin_router)
router.include_router(support_router)
router.include_router(users_router)
router.include_router(uploads_router)
router.include_router(badgeuse_router_me)
router.include_router(badgeuse_router_rh)


@router.post("/webhooks/yousign")
async def yousign_webhook(request: Request) -> Response:
    """
    Webhook public Yousign (pas de JWT). Valide le HMAC puis met à jour annual_reviews.
    Toujours 200 après traitement pour éviter les réessaies infinies (sauf 401 si signature invalide).
    """
    from app.core.database import supabase
    from app.modules.annual_reviews.application import commands
    from app.modules.annual_reviews.application.service import get_repository
    from app.services.yousign_service import yousign_service

    body_bytes = await request.body()
    sig_header = request.headers.get("X-Yousign-Signature-256") or ""
    if not yousign_service.validate_webhook(body_bytes, sig_header):
        return Response(status_code=401, content="Invalid signature")

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return Response(status_code=200)

    event_name = str(payload.get("event_name") or "")
    data = payload.get("data") or {}
    sr = data.get("signature_request") or {}
    procedure_id = sr.get("id")
    if not procedure_id:
        return Response(status_code=200)

    repo = get_repository()
    row = repo.get_by_yousign_procedure_id(str(procedure_id))
    if not row:
        return Response(status_code=200)

    review_id = str(row["id"])
    company_id = str(row["company_id"])

    try:
        if event_name == "signature_request.done":
            pdf = yousign_service.download_signed_document(str(procedure_id))
            path = f"{company_id}/{review_id}/signed_document.pdf"
            supabase.storage.from_("annual_reviews").upload(
                path,
                pdf,
                file_options={"content-type": "application/pdf", "x-upsert": "true"},
            )
            signed_r = supabase.storage.from_("annual_reviews").create_signed_url(
                path,
                31536000,
                options={"download": True},
            )
            signed_url = None
            if isinstance(signed_r, dict):
                signed_url = signed_r.get("signedURL") or signed_r.get("signedUrl")
            commands.update_signature_status(
                review_id,
                "signed",
                repo,
                signed_pdf_url=signed_url,
            )
        elif event_name == "signature_request.expired":
            commands.update_signature_status(review_id, "expired", repo)
        elif event_name in ("signer.declined", "signature_request.declined"):
            commands.update_signature_status(review_id, "refused", repo)
    except Exception as e:
        logger.exception("Erreur traitement webhook Yousign: %s", e)

    return Response(status_code=200)
