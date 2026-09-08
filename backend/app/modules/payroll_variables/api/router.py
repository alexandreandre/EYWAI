"""Router API variables paie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.payroll_variables.application.generate_monthly import (
    generate_monthly_variables,
)
from app.modules.payroll_variables.application.preset_astreinte_equipes import (
    apply_astreinte_equipes_preset,
)
from app.modules.payroll_variables.application.preset_shift_teams_payroll import (
    apply_shift_teams_payroll_preset,
)
from app.modules.payroll_variables.infrastructure import repository as repo
from app.modules.payroll_variables.schemas.requests import (
    AstreintePresetResponse,
    PeriodeVariablesSchema,
    PeriodeVariablesSurcharge,
    PeriodeVariablesUpdate,
    PayrollVariableGenerateResponse,
    PayrollVariablePreviewItem,
    PayrollVariableRuleSchema,
    SpecialPayrollDaySchema,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/payroll-variables", tags=["Variables paie"])


def _resolve_company_id(company_id: str | None, current_user: User) -> str:
    """Société visée, VÉRIFIÉE : le paramètre vient du client.

    Sans ce contrôle, passer le company_id d'une autre société donnait accès
    à ses réglages (audit sécurité 23/08/2026).
    """
    target = company_id or current_user.active_company_id
    if not target:
        raise HTTPException(status_code=400, detail="company_id requis.")
    if not current_user.is_platform_admin and not current_user.has_access_to_company(
        str(target)
    ):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé pour cette entreprise."
        )
    return str(target)


def _require_rh(user: User, company_id: str) -> None:
    """Droit RH DANS la société visée.

    `user.role` est un rôle plat qui renvoie False pour les rôles `custom` :
    les directeurs porteurs de 100 % de permissions RH étaient refusés, alors
    que le reste de l'application les accepte via has_rh_access_in_company.
    """
    if user.is_platform_admin:
        return
    if not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(status_code=403, detail="Accès RH requis.")


@router.get("/rules", response_model=list[PayrollVariableRuleSchema])
def list_rules(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    rows = repo.list_rules(str(cid))
    return [PayrollVariableRuleSchema(**r) for r in rows]


@router.post("/rules", response_model=PayrollVariableRuleSchema)
def create_rule(
    body: PayrollVariableRuleSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.upsert_rule(str(cid), data)
    return PayrollVariableRuleSchema(**row)


@router.put("/rules/{rule_id}", response_model=PayrollVariableRuleSchema)
def update_rule(
    rule_id: str,
    body: PayrollVariableRuleSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.upsert_rule(str(cid), data, rule_id=rule_id)
    return PayrollVariableRuleSchema(**row)


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    repo.delete_rule(str(cid), rule_id)
    return {"status": "ok"}


@router.post("/rules/preset/astreinte-equipes", response_model=AstreintePresetResponse)
def preset_astreinte_equipes(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    result = apply_astreinte_equipes_preset(str(cid))
    return AstreintePresetResponse(**result)


@router.post("/rules/preset/shift-teams-payroll", response_model=AstreintePresetResponse)
def preset_shift_teams_payroll(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    result = apply_shift_teams_payroll_preset(str(cid))
    return AstreintePresetResponse(**result)


@router.get("/special-days", response_model=list[SpecialPayrollDaySchema])
def list_special_days(
    year: int | None = Query(None),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    rows = repo.list_all_special_days(str(cid), year=year)
    return [SpecialPayrollDaySchema(**r) for r in rows]


@router.post("/special-days", response_model=SpecialPayrollDaySchema)
def create_special_day(
    body: SpecialPayrollDaySchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.create_special_day(str(cid), data)
    return SpecialPayrollDaySchema(**row)


@router.delete("/special-days/{day_id}")
def delete_special_day(
    day_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    repo.delete_special_day(str(cid), day_id)
    return {"status": "ok"}


@router.post("/generate", response_model=PayrollVariableGenerateResponse)
def generate_variables(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    dry_run: bool = Query(False),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    result = generate_monthly_variables(str(cid), year, month, dry_run=dry_run)
    return PayrollVariableGenerateResponse(
        company_id=result["company_id"],
        year=result["year"],
        month=result["month"],
        dry_run=result["dry_run"],
        preview=[PayrollVariablePreviewItem(**p) for p in result["preview"]],
        written_count=result["written_count"],
    )


# ---------------------------------------------------------------------------
# Fenêtre des variables — heures sup et paniers d'un mois.
#
# La gestionnaire de paie arrête les compteurs quand elle boucle la paie, et
# ce n'est pas la même date pour toutes les sociétés. Le début n'est jamais
# saisi : il est la suite du mois précédent, ce qui interdit de perdre une
# semaine ou de la payer deux fois.
# ---------------------------------------------------------------------------


@router.get("/period", response_model=PeriodeVariablesSchema)
def lire_periode_variables(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Fenêtre en vigueur pour ce mois — surcharge si elle existe, sinon règle."""
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.application.periode_variables_service import apercu_fenetre

    return apercu_fenetre(cid, year, month)


@router.put("/period", response_model=PeriodeVariablesSchema)
def enregistrer_periode_variables(
    body: PeriodeVariablesUpdate,
    current_user: User = Depends(get_current_user),
):
    """Arrête les variables du mois à la date choisie (semaine complète)."""
    cid = _resolve_company_id(body.company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.application.periode_variables_service import (
        apercu_fenetre,
        enregistrer_fenetre_variables,
    )

    try:
        enregistrer_fenetre_variables(
            cid, body.year, body.month, body.fin, user_id=str(current_user.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return apercu_fenetre(cid, body.year, body.month)


@router.get("/periods", response_model=list[PeriodeVariablesSurcharge])
def lister_surcharges_periode_variables(
    year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Mois de l'année dont la fenêtre a été corrigée à la main."""
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.infrastructure.variable_periods_repository import (
        list_variable_periods,
    )

    return [
        {
            "month": int(ligne["month"]),
            "debut": str(ligne["start_date"])[:10],
            "fin": str(ligne["end_date"])[:10],
        }
        for ligne in list_variable_periods(cid, year)
    ]
