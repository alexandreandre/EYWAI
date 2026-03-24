"""
Service applicatif collective_agreements.

Orchestration : domain (règles, interfaces) + infrastructure (repository, providers).
Convertit les exceptions du domain en HTTPException. Comportement identique au legacy.
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import HTTPException

from app.modules.collective_agreements.application.dto import (
    CatalogCreateInput,
    QuestionOutput,
    UploadUrlOutput,
)
from app.modules.collective_agreements.domain.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.domain.rules import (
    build_catalog_update_dict,
    generate_upload_path,
)
from app.modules.collective_agreements.infrastructure.mappers import (
    add_signed_url_to_agreement,
    serialize_dates,
)
from app.modules.collective_agreements.infrastructure.providers import (
    AgreementChatProvider,
    AgreementPdfTextExtractor,
    AgreementStorageProvider,
    AgreementTextCacheProvider,
    MAX_TEXT_CHARS,
)
from app.modules.collective_agreements.infrastructure.repository import (
    CollectiveAgreementRepository,
)


def _to_http(exc: Exception) -> HTTPException:
    """Convertit une exception du domain en HTTPException (comportement legacy)."""
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=403, detail=exc.message)
    if isinstance(exc, ValidationError):
        if "Aucune donnée" in exc.message or "Aucun PDF disponible" in exc.message:
            return HTTPException(status_code=400, detail=exc.message)
        return HTTPException(status_code=500, detail=exc.message)
    raise exc


class CollectiveAgreementsService:
    """Orchestration catalogue, assignations, storage, chat."""

    def __init__(
        self,
        repository: Optional[CollectiveAgreementRepository] = None,
        storage: Optional[AgreementStorageProvider] = None,
        text_cache: Optional[AgreementTextCacheProvider] = None,
        pdf_extractor: Optional[AgreementPdfTextExtractor] = None,
        chat_provider: Optional[AgreementChatProvider] = None,
    ):
        self._repo = repository or CollectiveAgreementRepository()
        self._storage = storage or AgreementStorageProvider()
        self._text_cache = text_cache or AgreementTextCacheProvider()
        self._pdf_extractor = pdf_extractor or AgreementPdfTextExtractor()
        self._chat = chat_provider or AgreementChatProvider()

    def list_catalog(
        self,
        *,
        sector: Optional[str] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> List[dict[str, Any]]:
        try:
            agreements = self._repo.list_catalog(
                sector=sector, search=search, active_only=active_only
            )
            for ag in agreements:
                url = self._storage.create_signed_url(ag.get("rules_pdf_path"), 3600)
                add_signed_url_to_agreement(ag, url)
            return agreements
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def get_catalog_item(self, agreement_id: str) -> Optional[dict[str, Any]]:
        try:
            agreement = self._repo.get_catalog_item(agreement_id)
            if not agreement:
                return None
            url = self._storage.create_signed_url(agreement.get("rules_pdf_path"), 3600)
            add_signed_url_to_agreement(agreement, url)
            return agreement
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def get_classifications(self, agreement_id: str) -> List[Any]:
        try:
            return self._repo.get_classifications_for_agreement(agreement_id)
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def get_upload_url(self, filename: str) -> UploadUrlOutput:
        try:
            path = generate_upload_path(filename)
            result = self._storage.create_signed_upload_url(path)
            return UploadUrlOutput(path=result["path"], signed_url=result["signedUrl"])
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def create_catalog_item(
        self, data: CatalogCreateInput, is_super_admin: bool
    ) -> dict[str, Any]:
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="Accès réservé au super administrateur")
        try:
            db_data = {
                "name": data.name,
                "idcc": data.idcc,
                "description": data.description,
                "sector": data.sector,
                "effective_date": data.effective_date,
                "is_active": data.is_active,
                "rules_pdf_path": data.rules_pdf_path,
                "rules_pdf_filename": data.rules_pdf_filename,
            }
            return self._repo.create_catalog_item(serialize_dates(db_data))
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def update_catalog_item(
        self, agreement_id: str, update_dict_raw: dict[str, Any], is_super_admin: bool
    ) -> Optional[dict[str, Any]]:
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="Accès réservé au super administrateur")
        try:
            update_dict = build_catalog_update_dict(update_dict_raw)
            if not update_dict:
                raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
            current_path = self._repo.get_catalog_item_rules_path(agreement_id)
            if "rules_pdf_path" in update_dict_raw and update_dict_raw["rules_pdf_path"] is None:
                if current_path:
                    self._storage.remove([current_path])
            return self._repo.update_catalog_item(agreement_id, serialize_dates(update_dict))
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def delete_catalog_item(self, agreement_id: str, is_super_admin: bool) -> bool:
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="Accès réservé au super administrateur")
        try:
            current_path = self._repo.get_catalog_item_rules_path(agreement_id)
            if current_path:
                self._storage.remove([current_path])
            return self._repo.delete_catalog_item(agreement_id)
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def get_my_company_agreements(
        self, company_id: str, has_rh_access: bool
    ) -> List[dict[str, Any]]:
        if not has_rh_access:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        try:
            assignments = self._repo.get_my_company_assignments(company_id)
            for assignment in assignments:
                details = assignment.get("agreement_details")
                if details and details.get("rules_pdf_path"):
                    url = self._storage.create_signed_url(details["rules_pdf_path"], 3600)
                    add_signed_url_to_agreement(details, url)
            return assignments
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def assign_to_company(
        self,
        company_id: str,
        collective_agreement_id: str,
        user_id: str,
        has_rh_access: bool,
    ) -> dict[str, Any]:
        if not has_rh_access:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        try:
            return self._repo.assign_to_company(
                company_id, collective_agreement_id, user_id
            )
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def unassign_from_company(
        self, assignment_id: str, company_id: str, has_rh_access: bool
    ) -> bool:
        if not has_rh_access:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        try:
            return self._repo.unassign_from_company(assignment_id, company_id)
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def get_all_assignments(self, is_super_admin: bool) -> List[dict[str, Any]]:
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="Accès réservé au super administrateur")
        try:
            result = self._repo.get_all_assignments_by_company()
            for item in result:
                for assignment in item.get("assigned_agreements", []):
                    details = assignment.get("agreement_details")
                    if details and details.get("rules_pdf_path"):
                        url = self._storage.create_signed_url(details["rules_pdf_path"], 3600)
                        add_signed_url_to_agreement(details, url)
            return result
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def _get_or_cache_pdf_text(
        self, agreement_id: str, pdf_url: str, agreement_name: str
    ) -> str:
        full_text = self._text_cache.get_full_text(agreement_id)
        if full_text:
            print(f"[INFO] ✓ Texte trouvé en cache pour {agreement_name}")
            return full_text
        print(f"[INFO] Extraction du texte du PDF pour {agreement_name}...")
        full_text = self._pdf_extractor.extract(pdf_url)
        if len(full_text) > MAX_TEXT_CHARS:
            full_text = (
                full_text[:MAX_TEXT_CHARS]
                + "\n\n[...Document tronqué pour respecter les limites de taille...]"
            )
        self._text_cache.set_full_text(agreement_id, full_text, len(full_text))
        return full_text

    def ask_question(
        self,
        agreement_id: str,
        question: str,
        company_id: str,
        has_rh_access: bool,
    ) -> QuestionOutput:
        if not has_rh_access:
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        try:
            if not self._repo.check_assignment_exists(company_id, agreement_id):
                raise ForbiddenError(
                    "Cette convention n'est pas assignée à votre entreprise"
                )
            agreement = self._repo.get_agreement_for_chat(agreement_id)
            if not agreement:
                raise NotFoundError("Convention collective non trouvée")
            if not agreement.get("rules_pdf_path"):
                raise ValidationError("Aucun PDF disponible pour cette convention")
            agreement_name = agreement["name"]
            agreement_idcc = agreement["idcc"]
            agreement_description = agreement.get("description", "")
            pdf_url = self._storage.create_signed_url(agreement["rules_pdf_path"], 3600)
            if not pdf_url:
                raise ValidationError("Impossible de générer l'URL du PDF")
            full_text = self._get_or_cache_pdf_text(
                agreement_id, pdf_url, agreement_name
            )
            system_prompt = f"""Tu es un assistant expert spécialisé dans la convention collective suivante :

📋 **Convention Collective : {agreement_name}**
🔢 **IDCC : {agreement_idcc}**
{f'📝 **Description : {agreement_description}**' if agreement_description else ''}

Tu as une connaissance complète et détaillée de cette convention collective. Ton rôle est de :

**🎯 Objectifs :**
1. Répondre aux questions sur cette convention collective de manière précise et professionnelle
2. Citer les articles ou sections pertinents de la convention
3. Expliquer clairement les droits et obligations des employeurs et employés
4. Donner des réponses pratiques et applicables

**📏 Règles strictes :**
- Base-toi UNIQUEMENT sur le texte de la convention collective fourni
- Si l'information n'est pas dans la convention, indique-le clairement
- Cite toujours les articles/sections pertinents
- Sois précis et factuel
- Si une question nécessite une interprétation juridique complexe ou sort du cadre de la convention, recommande de consulter un avocat spécialisé en droit du travail
- Utilise un ton professionnel mais accessible
- Structure tes réponses de manière claire (utilise des puces, des numéros, etc.)

**⚠️ Important :**
- Ne donne jamais de conseils juridiques définitifs
- En cas de doute, recommande de consulter un expert
- Mentionne si une disposition peut avoir évolué ou nécessite une vérification avec la version la plus récente"""
            user_prompt = f"""Voici le texte complet de la convention collective {agreement_name} (IDCC {agreement_idcc}) :

---
{full_text}
---

**Question de l'utilisateur :**
{question}

**Instructions :**
Réponds à cette question en te basant sur le texte de la convention collective ci-dessus. Cite les articles ou sections pertinents et structure ta réponse de manière claire."""
            answer = self._chat.answer(system_prompt, user_prompt)
            return QuestionOutput(answer=answer, agreement_name=agreement_name)
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)

    def refresh_text_cache(self, agreement_id: str, is_super_admin: bool) -> None:
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="Accès réservé au super administrateur")
        try:
            agreement = self._repo.get_agreement_for_chat(agreement_id)
            if not agreement:
                raise NotFoundError("Convention collective non trouvée")
            if not agreement.get("rules_pdf_path"):
                raise ValidationError("Aucun PDF disponible pour cette convention")
            pdf_url = self._storage.create_signed_url(agreement["rules_pdf_path"], 3600)
            if not pdf_url:
                raise ValidationError("Impossible de générer l'URL du PDF")
            self._text_cache.delete(agreement_id)
            self._get_or_cache_pdf_text(
                agreement_id, pdf_url, agreement.get("name", "")
            )
        except (NotFoundError, ForbiddenError, ValidationError) as e:
            raise _to_http(e)


def get_collective_agreements_service() -> CollectiveAgreementsService:
    """Factory : retourne le service avec les implémentations par défaut."""
    return CollectiveAgreementsService()
