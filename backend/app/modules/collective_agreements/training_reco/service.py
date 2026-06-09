"""Service d'extraction et persistance des propositions formation CC."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
from app.modules.collective_agreements.domain.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.infrastructure.providers import (
    AgreementTextCacheProvider,
)
from app.modules.collective_agreements.rules.service import _hash_text
from app.modules.collective_agreements.training_reco.extractor import CcTrainingExtractor
from app.modules.collective_agreements.training_reco.repository import (
    CcTrainingRecommendationsRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingExtractionOutcome:
    success: bool
    idcc: str
    agreement_id: Optional[str]
    count: int = 0
    recommendations: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    tokens_used: int = 0


class CcTrainingRecommendationsService:
    """Orchestration : texte CC → extraction IA → persistance."""

    def __init__(
        self,
        *,
        repo: Optional[CcTrainingRecommendationsRepository] = None,
        agreements_service: Optional[CollectiveAgreementsService] = None,
        extractor: Optional[CcTrainingExtractor] = None,
        text_cache: Optional[AgreementTextCacheProvider] = None,
    ):
        self._repo = repo or CcTrainingRecommendationsRepository()
        self._agreements = agreements_service or get_collective_agreements_service()
        self._extractor = extractor or CcTrainingExtractor()
        self._text_cache = text_cache or AgreementTextCacheProvider()

    def extract_and_persist_by_agreement_id(
        self,
        agreement_id: str,
        *,
        dry_run: bool = False,
    ) -> TrainingExtractionOutcome:
        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")
        idcc = str(agreement.get("idcc") or "").strip()
        if not idcc:
            raise ValidationError("IDCC manquant sur la convention")

        if dry_run:
            rows = self._repo.list_by_idcc(idcc)
            return TrainingExtractionOutcome(
                success=True,
                idcc=idcc,
                agreement_id=agreement_id,
                count=len(rows),
                recommendations=rows,
                error="dry_run: extraction IA non exécutée",
            )

        full_text = self._ensure_full_text(agreement_id, agreement)
        _hash_text(full_text)

        doc, tokens, extract_error = self._extractor.extract_from_text(
            full_text, idcc=idcc
        )
        if extract_error or doc is None:
            return TrainingExtractionOutcome(
                success=False,
                idcc=idcc,
                agreement_id=agreement_id,
                error=extract_error or "Extraction échouée",
                tokens_used=tokens,
            )

        items = [
            {
                "title": f.title,
                "obligation_level": f.obligation_level,
                "pedagogical_objective": f.pedagogical_objective,
                "legal_reference": f.legal_reference,
                "target_roles": f.target_roles,
                "periodicity": f.periodicity,
            }
            for f in doc.formations
        ]
        rows = self._repo.upsert_ai_recommendations(
            idcc=idcc,
            agreement_id=agreement_id,
            items=items,
            extraction_model=self._extractor._model,
        )
        return TrainingExtractionOutcome(
            success=True,
            idcc=idcc,
            agreement_id=agreement_id,
            count=len(rows),
            recommendations=rows,
            tokens_used=tokens,
        )

    def list_by_agreement_id(
        self, agreement_id: str, *, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")
        idcc = str(agreement.get("idcc") or "").strip()
        if not idcc:
            return []
        return self._repo.list_by_idcc(idcc, active_only=active_only)

    def update_recommendation(
        self, recommendation_id: str, patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        row = self._repo.update_item(recommendation_id, patch)
        if not row:
            raise NotFoundError("Proposition de formation non trouvée")
        return row

    def get_recommendation(self, recommendation_id: str) -> Dict[str, Any]:
        row = self._repo.get_by_id(recommendation_id)
        if not row:
            raise NotFoundError("Proposition de formation non trouvée")
        return row

    def list_active_by_idcc(self, idcc: str) -> List[Dict[str, Any]]:
        return self._repo.list_by_idcc(idcc, active_only=True)

    def _ensure_full_text(
        self, agreement_id: str, agreement: Dict[str, Any]
    ) -> str:
        cached = self._text_cache.get_full_text(agreement_id)
        if cached:
            return cached
        if not agreement.get("rules_pdf_path"):
            raise ValidationError(
                "Aucun texte disponible — importez depuis Légifrance ou uploadez un PDF"
            )
        from app.modules.collective_agreements.infrastructure.providers import (
            AgreementStorageProvider,
        )

        storage = AgreementStorageProvider()
        pdf_url = storage.create_signed_url(str(agreement["rules_pdf_path"]), 3600)
        if not pdf_url:
            raise ValidationError("Impossible de générer l'URL du PDF")
        return self._agreements._get_or_cache_pdf_text(
            agreement_id, pdf_url, agreement.get("name", "")
        )


def get_cc_training_recommendations_service() -> CcTrainingRecommendationsService:
    return CcTrainingRecommendationsService()
