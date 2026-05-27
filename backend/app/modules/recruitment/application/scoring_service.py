# app/modules/recruitment/application/scoring_service.py
"""Scoring IA candidat vs fiche de poste (OpenRouter)."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.shared.infrastructure.ai import (
    MODEL_RECRUITMENT_SCORING,
    chat_completions_create,
    require_llm_api_key,
)

SCORING_PROMPT = """Tu es un expert RH chargé d'évaluer l'adéquation d'un candidat
à une offre d'emploi.

FICHE DE POSTE :
Titre : {job_title}
Description : {job_description}
Type de contrat : {contract_type}
Localisation : {location}
Tags / compétences recherchées : {tags}

PROFIL CANDIDAT :
Nom : {candidate_name}
Source : {source}
Notes d'entretien disponibles : {notes}
Avis des interviewers : {opinions}

Évalue l'adéquation et réponds UNIQUEMENT en JSON valide,
sans aucun texte avant ou après :

{{
  "score": <entier 0-100>,
  "mention": "<Excellent|Bon|Moyen|Faible>",
  "points_forts": ["<point 1>", "<point 2>", "<point 3>"],
  "points_faibles": ["<point 1>", "<point 2>"],
  "recommandation": "<phrase de synthèse 1-2 lignes>"
}}

Règles de scoring :
- 80-100 : Excellent — profil très aligné
- 60-79 : Bon — profil aligné avec quelques réserves
- 40-59 : Moyen — profil partiellement aligné
- 0-39 : Faible — profil peu aligné

Si les informations sont insuffisantes, baser le score
sur les éléments disponibles et l'indiquer dans
la recommandation.
"""


class ScoringService:
    def score_candidate(
        self,
        candidate: Dict[str, Any],
        job: Dict[str, Any],
        notes: List[Dict[str, Any]],
        opinions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        notes_text = "\n".join(
            f"- {n.get('content', '')}" for n in notes
        )
        if not notes_text.strip():
            notes_text = "Aucune note disponible"

        def _opinion_line(o: Dict[str, Any]) -> str:
            rating = (o.get("rating") or "").lower()
            label = (
                "Favorable"
                if rating == "favorable"
                else "Défavorable"
                if rating == "defavorable"
                else str(o.get("rating") or "—")
            )
            who = (
                f"{o.get('author_first_name', '')} {o.get('author_last_name', '')}".strip()
                or "Intervieweur"
            )
            cm = o.get("comment")
            suffix = f" — {cm}" if cm else ""
            return f"- {who} : {label}{suffix}"

        opinions_text = "\n".join(_opinion_line(o) for o in opinions)
        if not opinions_text.strip():
            opinions_text = "Aucun avis disponible"

        prompt = SCORING_PROMPT.format(
            job_title=job.get("title", ""),
            job_description=job.get("description", "") or "Non précisée",
            contract_type=job.get("contract_type", "") or "Non précisé",
            location=job.get("location", "") or "Non précisée",
            tags=", ".join(job.get("tags") or []) or "Non précisées",
            candidate_name=(
                f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}"
            ).strip(),
            source=candidate.get("source", "") or "Non précisée",
            notes=notes_text,
            opinions=opinions_text,
        )

        require_llm_api_key()
        response = chat_completions_create(
            model=MODEL_RECRUITMENT_SCORING,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()

        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
                if raw.lstrip().startswith("json"):
                    raw = raw.lstrip()[4:].lstrip()

        result = json.loads(raw.strip())

        result["score"] = max(0, min(100, int(result.get("score", 0))))
        valid_mentions = ["Excellent", "Bon", "Moyen", "Faible"]
        if result.get("mention") not in valid_mentions:
            score = int(result["score"])
            if score >= 80:
                result["mention"] = "Excellent"
            elif score >= 60:
                result["mention"] = "Bon"
            elif score >= 40:
                result["mention"] = "Moyen"
            else:
                result["mention"] = "Faible"

        for key in ("points_forts", "points_faibles"):
            val = result.get(key)
            if not isinstance(val, list):
                result[key] = []
            else:
                result[key] = [str(x) for x in val]
        if not isinstance(result.get("recommandation"), str):
            result["recommandation"] = str(result.get("recommandation", ""))

        return result


scoring_service = ScoringService()
