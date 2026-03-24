"""Routeur global : agrège les routers des modules app.modules."""
from fastapi import APIRouter

from app.modules.access_control.api.router import router as access_control_router
from app.modules.absences.api.router import router as absences_router
from app.modules.annual_reviews.api.router import router as annual_reviews_router
from app.modules.auth.api.router import router as auth_router
from app.modules.bonus_types.api.router import router as bonus_types_router
from app.modules.companies.api.router import router as companies_router
from app.modules.contract_parser.api.router import router as contract_parser_router
from app.modules.copilot.api.router import router as copilot_router, router_agent as copilot_agent_router
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
from app.modules.medical_follow_up.api.router import router as medical_follow_up_router
from app.modules.mutuelle_types.api.router import router as mutuelle_types_router
from app.modules.participation.api.router import router as participation_router
from app.modules.payslips.api.router import router as payslips_router
from app.modules.promotions.api.router import router as promotions_router
from app.modules.rates.api.router import router as rates_router
from app.modules.recruitment.api.router import router as recruitment_router
from app.modules.repos_compensateur.api.router import router as repos_compensateur_router
from app.modules.saisies_avances.api.router import router as saisies_avances_router
from app.modules.scraping.api.router import router as scraping_router
from app.modules.residence_permits.api.router import router as residence_permits_router
from app.modules.rib_alerts.api.router import router as rib_alerts_router
from app.modules.schedules.api.router import (
    router as schedules_router,
    router_me as schedules_router_me,
    router_rh as schedules_router_rh,
)
from app.modules.super_admin.api.router import router as super_admin_router
from app.modules.uploads.api.router import router as uploads_router
from app.modules.users.api.router import router as users_router

router = APIRouter()

router.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
router.include_router(access_control_router)
router.include_router(annual_reviews_router)
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
router.include_router(expenses_router)
router.include_router(medical_follow_up_router, prefix="/api/medical-follow-up")
router.include_router(mutuelle_types_router)
router.include_router(bonus_types_router)
router.include_router(participation_router)
router.include_router(payslips_router)
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
router.include_router(users_router)
router.include_router(uploads_router)
