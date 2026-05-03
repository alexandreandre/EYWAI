"""
Router API du module employees.

Délègue toute la logique à la couche application. Aucune logique métier ni accès DB.
Comportement HTTP identique à api/routers/employees.py (legacy).
"""

import json
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.security import get_current_user
from app.modules.audit.infrastructure.repository import audit_repository
from app.modules.webhooks.infrastructure.repository import webhook_repository
from app.modules.employees.application import commands, queries
from app.modules.employees.application.dto import EmployeeCreateValidationError
from app.modules.employees.schemas.requests import NewFullEmployee, UpdateEmployee
from app.modules.documents.application.commands import generate_document
from app.modules.documents.schemas.requests import GenerateDocumentRequest
from app.modules.employees.schemas.salary import (
    ApplicationCollectiveRequest,
    ApplicationCollectiveResultat,
    EmployeSimule,
    GenerationAvenantsLotRequest,
    GenerationAvenantsLotResultat,
    SalaryHistoryEntry,
    SalaryUpdateResponse,
    SimulationAugmentationRequest,
    SimulationCollectiveRequest,
    SimulationCollectiveResultat,
    SimulationResultat,
    UpdateSalaryRequest,
)
from app.modules.employees.schemas.responses import (
    ContractResponse,
    EmployeeRhAccess,
    FullEmployee,
    NewEmployeeResponse,
    PromotionListItem,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/employees", tags=["Employees"])


def _require_rh_access(company_id: str | None, current_user: User) -> str:
    """Entreprise active, accès entreprise et profil RH."""
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Impossible de déterminer l'entreprise.",
        )
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise.",
        )
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")
    return company_id


def _handle_application_errors(e: Exception) -> None:
    """Erreurs applicatives → HTTP (pattern modules documents)."""
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e)) from e
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e)) from e


def _valeur_salaire_float(salaire: Any) -> float:
    """Extrait la composante valeur pour la réponse métier."""
    if salaire is None:
        return 0.0
    if isinstance(salaire, dict) and "valeur" in salaire:
        try:
            return float(salaire["valeur"])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _ancien_salaire_dict(salaire_de_base: Any) -> Dict[str, Any]:
    """Normalise salaire_de_base employé pour historique."""
    if salaire_de_base is None:
        return {"valeur": 0.0}
    if isinstance(salaire_de_base, dict) and "valeur" in salaire_de_base:
        return dict(salaire_de_base)
    return {"valeur": 0.0}


TAUX_SALARIE = 0.2284  # ~22,84 % cotisations salariales moyennes (simulation)
TAUX_PATRONAL = 0.4200  # ~42 % cotisations patronales moyennes (simulation)


def _nouveau_brut_collectif(
    ancien: float,
    type_augmentation: str,
    valeur: float,
) -> float:
    if type_augmentation == "pourcentage":
        return ancien * (1 + valeur / 100)
    return ancien + valeur


def _estimer_paie(salaire_brut: float, employee: Dict[str, Any]) -> Dict[str, float]:
    """
    Estimation rapide sans moteur paie ni fichier.
    employee réservé pour extensions futures (profil, région, etc.).
    """
    _ = employee
    net_estime = salaire_brut * (1 - TAUX_SALARIE)
    charges_patronales = salaire_brut * TAUX_PATRONAL
    cout_employeur = salaire_brut + charges_patronales
    return {
        "net_estime": net_estime,
        "charges_patronales": charges_patronales,
        "cout_employeur": cout_employeur,
    }


# ----- Liste et détail -----


@router.get("", response_model=List[FullEmployee])
def get_employees(current_user: User = Depends(get_current_user)):
    """Récupère la liste de tous les salariés de l'entreprise active."""
    try:
        company_id = current_user.active_company_id
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise de l'utilisateur connecté.",
            )
        return queries.get_employees(company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


@router.post("/simulate-augmentation-collective", response_model=SimulationCollectiveResultat)
def simulate_augmentation_collective(
    body: SimulationCollectiveRequest,
    current_user: User = Depends(get_current_user),
):
    """Simulation d'impact sur une sélection filtrée de salariés actifs."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        f = body.filtres
        rows = queries.get_employees_filtered(
            company_id,
            service_id=f.service_id,
            statut=f.statut,
            contract_type=f.contract_type,
            anciennete_min_mois=f.anciennete_min_mois,
            salaire_min=f.salaire_min,
            salaire_max=f.salaire_max,
        )

        employes_simules: List[EmployeSimule] = []
        masse_avant = 0.0
        masse_apres = 0.0

        for emp in rows:
            ancien = _valeur_salaire_float(emp.get("salaire_de_base"))
            nouveau = _nouveau_brut_collectif(
                ancien, body.type_augmentation, body.valeur
            )
            diff_b = nouveau - ancien
            masse_avant += ancien
            masse_apres += nouveau
            taux_r = ((nouveau - ancien) / ancien * 100) if ancien > 0 else 0.0
            fn = str(emp.get("first_name") or "").strip()
            ln = str(emp.get("last_name") or "").strip()
            nom_complet = f"{fn} {ln}".strip() or str(emp.get("id"))
            sid = emp.get("service_id")
            employes_simules.append(
                EmployeSimule(
                    employee_id=str(emp["id"]),
                    nom_complet=nom_complet,
                    poste=emp.get("job_title"),
                    service_id=str(sid) if sid else None,
                    ancien_salaire_brut=ancien,
                    nouveau_salaire_brut=nouveau,
                    difference_brut=diff_b,
                    taux_augmentation_reel=taux_r,
                )
            )

        diff_masse = masse_apres - masse_avant
        cout_charges_pat_supp = diff_masse * TAUX_PATRONAL
        cout_total_supp = diff_masse + cout_charges_pat_supp

        return SimulationCollectiveResultat(
            nb_employes=len(rows),
            employes=employes_simules,
            masse_salariale_avant=masse_avant,
            masse_salariale_apres=masse_apres,
            difference_masse_salariale=diff_masse,
            cout_charges_patronales_supplementaires=cout_charges_pat_supp,
            cout_total_supplementaire=cout_total_supp,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/appliquer-augmentation-collective", response_model=ApplicationCollectiveResultat)
def appliquer_augmentation_collective(
    body: ApplicationCollectiveRequest,
    current_user: User = Depends(get_current_user),
):
    """Applique une augmentation aux salariés listés (best effort)."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        erreurs: List[str] = []
        nb_ok = 0
        created_by = str(current_user.id)
        eff = body.effective_date.isoformat()

        for eid in body.employee_ids:
            try:
                emp = queries.get_employee_row(eid, company_id)
                if emp is None:
                    erreurs.append(f"{eid}: employé introuvable.")
                    continue
                ancien = _valeur_salaire_float(emp.get("salaire_de_base"))
                nouveau = _nouveau_brut_collectif(
                    ancien, body.type_augmentation, body.valeur
                )
                ancien_dict = _ancien_salaire_dict(emp.get("salaire_de_base"))
                nouveau_dict = {"valeur": nouveau}
                commands.apply_salary_update(
                    employee_id=eid,
                    company_id=company_id,
                    ancien_salaire=ancien_dict,
                    nouveau_salaire=nouveau_dict,
                    motif=body.motif,
                    effective_date=eff,
                    created_by=created_by,
                )
                nb_ok += 1
            except Exception as ex:
                erreurs.append(f"{eid}: {ex}")

        return ApplicationCollectiveResultat(
            nb_appliques=nb_ok,
            nb_erreurs=len(erreurs),
            erreurs=erreurs,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/generer-avenants-lot", response_model=GenerationAvenantsLotResultat)
def generer_avenants_lot(
    body: GenerationAvenantsLotRequest,
    current_user: User = Depends(get_current_user),
):
    """Génère des avenants salaire en lot (best effort)."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        uid = str(current_user.id)
        doc_ids: List[str] = []
        erreurs: List[str] = []
        ns_map = body.nouveau_salaire_par_employe or {}

        for eid in body.employee_ids:
            try:
                emp = queries.get_employee_row(eid, company_id)
                if emp is None:
                    erreurs.append(f"{eid}: employé introuvable.")
                    continue
                ns_raw = ns_map.get(eid)
                nouveau_opt = float(ns_raw) if ns_raw is not None else None
                req = GenerateDocumentRequest(
                    employee_id=eid,
                    document_type="avenant_salaire",
                    category="avenant",
                    date_effet=body.effective_date,
                    motif=body.motif,
                    template_id=body.template_id,
                    nouveau_salaire=nouveau_opt,
                )
                row = generate_document(company_id, uid, req)
                rid = row.get("id")
                if rid:
                    doc_ids.append(str(rid))
                else:
                    erreurs.append(f"{eid}: document sans identifiant.")
            except Exception as ex:
                erreurs.append(f"{eid}: {ex}")

        return GenerationAvenantsLotResultat(
            nb_generes=len(doc_ids),
            nb_erreurs=len(erreurs),
            document_ids=doc_ids,
            erreurs=erreurs,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/me/contract", response_model=ContractResponse)
def get_my_contract(current_user: User = Depends(get_current_user)):
    """(Espace Employé) URL signée de téléchargement du contrat de l'employé connecté."""
    try:
        url = queries.get_my_contract_url(str(current_user.id))
        if url is None:
            return ContractResponse(url=None)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/me/published-exit-documents")
def get_my_published_exit_documents(
    current_user: User = Depends(get_current_user),
):
    """(Espace Employé) Liste des documents de sortie publiés pour l'employé connecté."""
    try:
        return queries.get_my_published_exit_documents(str(current_user.id))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}", response_model=FullEmployee)
def get_employee_details(
    employee_id: str, current_user: User = Depends(get_current_user)
):
    """Récupère les détails complets d'un salarié."""
    try:
        company_id = current_user.active_company_id
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise.",
            )
        data = queries.get_employee_by_id(employee_id, company_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        return data
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


# ----- Création (POST) -----


@router.post("", response_model=NewEmployeeResponse, status_code=201)
async def create_employee(
    request: Request,
    data: str = Form(...),
    file: Optional[UploadFile] = File(None),
    identity_file: Optional[UploadFile] = File(None),
    generate_pdf_contract: str = Form("false"),
    current_user: User = Depends(get_current_user),
):
    """Crée un nouvel employé (Auth + profil + employees + storage + PDF + RIB)."""
    company_id = queries.get_company_id_for_creator(str(current_user.id))
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Impossible de déterminer l'entreprise de l'utilisateur connecté.",
        )

    data_dict = json.loads(data)
    for key in (
        "residence_permit_expiry_date",
        "residence_permit_type",
        "residence_permit_number",
    ):
        if key in data_dict and data_dict[key] == "":
            data_dict[key] = None
    cleaned_data = json.dumps(data_dict)

    try:
        employee_data = NewFullEmployee.model_validate_json(cleaned_data)
    except ValidationError as ve:
        validation_errors = {}
        for error in ve.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            validation_errors[field_path] = error["msg"]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Erreur de validation des données JSON",
                "field_errors": validation_errors,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Données JSON invalides: {e}")

    contract_content: Optional[bytes] = None
    contract_content_type: Optional[str] = None
    if file:
        contract_content = await file.read()
        contract_content_type = file.content_type or "application/pdf"

    identity_content: Optional[bytes] = None
    identity_filename: Optional[str] = None
    identity_content_type: Optional[str] = None
    if identity_file:
        identity_content = await identity_file.read()
        identity_filename = identity_file.filename
        identity_content_type = identity_file.content_type

    try:
        result = await commands.create_employee(
            employee_data=employee_data.model_dump(),
            company_id=company_id,
            contract_file_content=contract_content,
            contract_content_type=contract_content_type,
            identity_file_content=identity_content,
            identity_filename=identity_filename,
            identity_content_type=identity_content_type,
            generate_pdf_contract=generate_pdf_contract.lower() == "true",
            granted_by_user_id=str(current_user.id),
        )
        eid = str(result.get("id") or "")
        if eid:
            audit_repository.log(
                company_id=str(company_id),
                user_id=str(current_user.id),
                user_email=current_user.email,
                action="employee.create",
                resource_type="employee",
                resource_id=eid,
                details={"email": employee_data.email},
                ip_address=request.client.host if request.client else None,
            )
            webhook_repository.trigger_event(
                str(company_id),
                "employee.hired",
                {"employee_id": eid, "email": employee_data.email},
            )
        return result
    except EmployeeCreateValidationError as e:
        return JSONResponse(
            status_code=400,
            content={
                "detail": e.message,
                "field_errors": e.field_errors,
            },
        )
    except HTTPException:
        raise


# ----- Mise à jour et suppression -----


@router.put("/{employee_id}", response_model=FullEmployee)
async def update_employee(
    employee_id: str,
    employee_data: UpdateEmployee,
    current_user: User = Depends(get_current_user),
):
    """Met à jour les informations d'un salarié."""
    try:
        update_data = employee_data.model_dump(exclude_unset=True)
        return commands.update_employee(employee_id, update_data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


@router.delete("/{employee_id}", status_code=204)
async def delete_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un employé, son profil et son utilisateur d'authentification."""
    try:
        commands.delete_employee(employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur lors de la suppression: {str(e)}",
        )


# ----- URLs signées (contrat, credentials, pièce d'identité) -----


@router.get("/{employee_id}/credentials-pdf", response_model=ContractResponse)
def get_employee_credentials_pdf_url(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """(Espace RH) URL signée du PDF de création de compte."""
    try:
        url = queries.get_credentials_pdf_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/identity-document", response_model=ContractResponse)
def get_employee_identity_document_url(
    employee_id: str, current_user: User = Depends(get_current_user)
):
    """(Espace RH) URL signée de la pièce d'identité."""
    try:
        url = queries.get_identity_document_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/contract", response_model=ContractResponse)
def get_employee_contract_url(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """(Espace RH) URL signée du contrat PDF."""
    try:
        url = queries.get_contract_url(employee_id)
        return ContractResponse(url=url)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


# ----- Promotions et accès RH -----


@router.get("/{employee_id}/promotions", response_model=List[PromotionListItem])
def get_employee_promotions(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Liste des promotions d'un employé."""
    try:
        company_id = queries.get_employee_company_id(employee_id)
        if not company_id:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        if current_user.active_company_id != company_id and not getattr(
            current_user, "is_super_admin", False
        ):
            raise HTTPException(
                status_code=403, detail="Accès non autorisé à cet employé."
            )
        return queries.get_employee_promotions(company_id, employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/{employee_id}/rh-access", response_model=EmployeeRhAccess)
def get_employee_rh_access_info(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Accès RH actuel et rôles disponibles pour un employé (RH uniquement)."""
    try:
        company_id = queries.get_employee_company_id(employee_id)
        if not company_id:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        if current_user.active_company_id != company_id and not getattr(
            current_user, "is_super_admin", False
        ):
            raise HTTPException(
                status_code=403, detail="Accès non autorisé à cet employé."
            )
        if not getattr(current_user, "has_rh_access_in_company", lambda _: False)(
            company_id
        ) and not getattr(current_user, "is_super_admin", False):
            raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
        return queries.get_employee_rh_access(employee_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


# ----- Salaire et historique (RH) -----


@router.put("/{employee_id}/salary", response_model=SalaryUpdateResponse)
def update_employee_salary(
    request: Request,
    employee_id: str,
    body: UpdateSalaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le salaire de base et enregistre une ligne d'historique."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        employee = queries.get_employee_row(employee_id, company_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")

        ancien_salaire = _ancien_salaire_dict(employee.get("salaire_de_base"))
        nouveau_salaire = {"valeur": body.nouveau_salaire}
        hist = commands.apply_salary_update(
            employee_id=employee_id,
            company_id=company_id,
            ancien_salaire=ancien_salaire,
            nouveau_salaire=nouveau_salaire,
            motif=body.motif,
            effective_date=body.effective_date.isoformat(),
            created_by=str(current_user.id),
        )
        audit_repository.log(
            company_id=str(company_id),
            user_id=str(current_user.id),
            user_email=current_user.email,
            action="salary.update",
            resource_type="employee",
            resource_id=str(employee_id),
            details={
                "nouveau_salaire": body.nouveau_salaire,
                "history_entry_id": str(hist["id"]),
            },
            ip_address=request.client.host if request.client else None,
        )
        webhook_repository.trigger_event(
            str(company_id),
            "employee.salary_updated",
            {
                "employee_id": str(employee_id),
                "history_entry_id": str(hist["id"]),
                "nouveau_salaire": body.nouveau_salaire,
            },
        )
        return SalaryUpdateResponse(
            success=True,
            ancien_salaire=_valeur_salaire_float(ancien_salaire),
            nouveau_salaire=body.nouveau_salaire,
            history_entry_id=str(hist["id"]),
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{employee_id}/salary-history", response_model=List[SalaryHistoryEntry])
def get_employee_salary_history(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Historique des évolutions de salaire pour un collaborateur."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        rows = queries.get_salary_history_rows(employee_id, company_id)
        out: List[SalaryHistoryEntry] = []
        for row in rows:
            out.append(
                SalaryHistoryEntry(
                    id=str(row["id"]),
                    ancien_salaire=dict(row["ancien_salaire"])
                    if isinstance(row.get("ancien_salaire"), dict)
                    else {},
                    nouveau_salaire=dict(row["nouveau_salaire"])
                    if isinstance(row.get("nouveau_salaire"), dict)
                    else {},
                    motif=row.get("motif"),
                    effective_date=row["effective_date"],
                    created_at=row["created_at"],
                )
            )
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{employee_id}/simulate-augmentation", response_model=SimulationResultat)
def simulate_augmentation(
    employee_id: str,
    body: SimulationAugmentationRequest,
    current_user: User = Depends(get_current_user),
):
    """Simulation d'augmentation (nets et charges estimés par taux moyens)."""
    try:
        company_id = _require_rh_access(current_user.active_company_id, current_user)
        employee = queries.get_employee_row(employee_id, company_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")

        salaire_brut_actuel = _valeur_salaire_float(employee.get("salaire_de_base"))

        if body.type_augmentation == "pourcentage":
            nouveau_salaire_brut = salaire_brut_actuel * (1 + body.valeur / 100)
        else:
            nouveau_salaire_brut = salaire_brut_actuel + body.valeur

        est_avant = _estimer_paie(salaire_brut_actuel, employee)
        est_apres = _estimer_paie(nouveau_salaire_brut, employee)

        diff_brut = nouveau_salaire_brut - salaire_brut_actuel
        if salaire_brut_actuel > 0:
            taux_augmentation_reel = (nouveau_salaire_brut - salaire_brut_actuel) / (
                salaire_brut_actuel
            ) * 100
        else:
            taux_augmentation_reel = 0.0

        return SimulationResultat(
            ancien_salaire_brut=salaire_brut_actuel,
            nouveau_salaire_brut=nouveau_salaire_brut,
            difference_brut=diff_brut,
            ancien_net_estime=est_avant["net_estime"],
            nouveau_net_estime=est_apres["net_estime"],
            difference_net=est_apres["net_estime"] - est_avant["net_estime"],
            anciennes_charges_patronales=est_avant["charges_patronales"],
            nouvelles_charges_patronales=est_apres["charges_patronales"],
            difference_charges_patronales=est_apres["charges_patronales"]
            - est_avant["charges_patronales"],
            cout_total_employeur_avant=est_avant["cout_employeur"],
            cout_total_employeur_apres=est_apres["cout_employeur"],
            difference_cout_employeur=est_apres["cout_employeur"]
            - est_avant["cout_employeur"],
            taux_augmentation_reel=taux_augmentation_reel,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
