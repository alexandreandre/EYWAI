"""Persistance Supabase des propositions de formation CC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CcTrainingRecommendationsRepository:
    """Repository cc_training_recommendations."""

    def list_by_idcc(
        self, idcc: str, *, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("cc_training_recommendations")
            .select("*")
            .eq("idcc", idcc)
            .order("obligation_level")
            .order("title")
        )
        if active_only:
            q = q.eq("is_active", True)
        r = q.execute()
        return [dict(x) for x in list(r.data or []) if r]

    def get_by_id(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("cc_training_recommendations")
            .select("*")
            .eq("id", recommendation_id)
            .maybe_single()
            .execute()
        )
        return dict(r.data) if r.data else None

    def upsert_ai_recommendations(
        self,
        *,
        idcc: str,
        agreement_id: str,
        items: List[Dict[str, Any]],
        extraction_model: str,
    ) -> List[Dict[str, Any]]:
        existing = self.list_by_idcc(idcc)
        active_by_title = {
            str(row.get("title") or "").strip().lower(): bool(row.get("is_active", True))
            for row in existing
            if str(row.get("source") or "") == "ai"
        }

        supabase.table("cc_training_recommendations").delete().eq("idcc", idcc).eq(
            "source", "ai"
        ).execute()

        if not items:
            return self.list_by_idcc(idcc)

        now = _now_iso()
        payload: List[Dict[str, Any]] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            key = title.lower()
            payload.append(
                {
                    "idcc": idcc,
                    "agreement_id": agreement_id,
                    "title": title,
                    "obligation_level": item.get("obligation_level") or "recommandee",
                    "pedagogical_objective": item.get("pedagogical_objective"),
                    "legal_reference": item.get("legal_reference"),
                    "target_roles": item.get("target_roles") or [],
                    "periodicity": item.get("periodicity"),
                    "is_active": active_by_title.get(key, True),
                    "source": "ai",
                    "confidence": item.get("confidence"),
                    "extracted_at": now,
                    "extraction_model": extraction_model,
                    "updated_at": now,
                }
            )

        if payload:
            ins = supabase.table("cc_training_recommendations").insert(payload).execute()
            if not ins.data:
                raise RuntimeError("Erreur lors de la persistance des propositions formation CC.")

        return self.list_by_idcc(idcc)

    def update_item(
        self,
        recommendation_id: str,
        patch: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not patch:
            return self.get_by_id(recommendation_id)
        payload = {**patch, "updated_at": _now_iso()}
        r = (
            supabase.table("cc_training_recommendations")
            .update(payload)
            .eq("id", recommendation_id)
            .execute()
        )
        if not r.data:
            return None
        return self.get_by_id(recommendation_id)
