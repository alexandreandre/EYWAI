# app/modules/recruitment/application/scoring_service.py
"""Scoring IA candidat vs fiche de poste (OpenRouter, gpt-4o-mini)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.shared.infrastructure.ai import (
    MODEL_RECRUITMENT_SCORING,
    chat_completions_create,
    require_llm_api_key,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es un expert RH senior spécialisé en recrutement et évaluation
de candidats. Ta mission : estimer l'adéquation d'un candidat à une offre d'emploi
de manière objective, factuelle et reproductible.

RÈGLES IMPÉRATIVES :
1. Base-toi UNIQUEMENT sur les informations fournies. N'invente jamais de compétence,
   diplôme, expérience ou qualité non mentionnée explicitement.
2. Évalue d'abord chaque critère sur 0-100, puis calcule le score global comme
   moyenne pondérée (voir pondérations dans le message utilisateur).
3. Les avis défavorables d'interviewers doivent peser significativement sur le score.
4. Si les données sont insuffisantes, abaisse le score ET indique confiance "Faible"
   avec des limites explicites. Ne sur-interprète pas un CV minimal.
5. Le score global doit être cohérent avec les sous-scores et la mention.
6. Réponds UNIQUEMENT en JSON valide, sans texte avant ou après."""

USER_PROMPT = """=== OFFRE D'EMPLOI ===
Titre : {job_title}
Description : {job_description}
Type de contrat : {contract_type}
Localisation : {location}
Compétences / tags recherchés : {tags}

=== CANDIDAT ===
Nom : {candidate_name}
Source de candidature : {source}
Étape pipeline actuelle : {pipeline_stage}

=== CV ===
{cv_section}

=== ENTRETIENS ===
{interviews_section}

=== NOTES D'ENTRETIEN ===
{notes_section}

=== AVIS DES INTERVIEWERS ===
{opinions_section}
Synthèse quantitative : {opinions_summary}

=== QUALITÉ DES DONNÉES ===
{data_quality_section}

=== GRILLE D'ÉVALUATION (pondérations) ===
Calcule chaque sous-score (0-100) puis le score global :
- competences_experience (35 %) : adéquation compétences techniques et expérience
  professionnelle vs exigences du poste
- formation_parcours (20 %) : formation, certifications, cohérence du parcours
- soft_skills_motivation (20 %) : soft skills, motivation, culture fit (notes et
  entretiens)
- retours_interviewers (15 %) : consensus des avis favorables / défavorables
- adequation_pratique (10 %) : mobilité, type de contrat, localisation, disponibilité

Barème score global :
- 80-100 : Excellent — profil très aligné, peu de réserves
- 60-79 : Bon — profil aligné avec réserves mineures
- 40-59 : Moyen — adéquation partielle, écarts significatifs
- 0-39 : Faible — profil peu aligné ou données insuffisantes pour recommander

Réponds en JSON :
{{
  "criteres": {{
    "competences_experience": <0-100>,
    "formation_parcours": <0-100>,
    "soft_skills_motivation": <0-100>,
    "retours_interviewers": <0-100>,
    "adequation_pratique": <0-100>
  }},
  "score": <entier 0-100, moyenne pondérée arrondie>,
  "mention": "<Excellent|Bon|Moyen|Faible>",
  "confiance": "<Haute|Moyenne|Faible>",
  "points_forts": ["<point factuel 1>", "<point factuel 2>", "<point factuel 3>"],
  "points_faibles": ["<point factuel 1>", "<point factuel 2>"],
  "limites": "<limites de l'analyse : données manquantes ou incertitudes>",
  "recommandation": "<synthèse actionnable 1-2 phrases pour le recruteur>"
}}"""

CRITERION_WEIGHTS: Dict[str, float] = {
    "competences_experience": 0.35,
    "formation_parcours": 0.20,
    "soft_skills_motivation": 0.20,
    "retours_interviewers": 0.15,
    "adequation_pratique": 0.10,
}

VALID_MENTIONS = ("Excellent", "Bon", "Moyen", "Faible")
VALID_CONFIDENCE = ("Haute", "Moyenne", "Faible")


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip().startswith("json"):
                s = s.lstrip()[4:].lstrip()
    return s.strip()


def _sort_by_created(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda x: str(x.get("created_at") or ""))


def _format_notes(notes: List[Dict[str, Any]]) -> str:
    ordered = _sort_by_created(notes)
    lines: List[str] = []
    for n in ordered:
        content = (n.get("content") or "").strip()
        if not content:
            continue
        author = (
            f"{n.get('author_first_name', '')} {n.get('author_last_name', '')}".strip()
            or "Auteur inconnu"
        )
        date = str(n.get("created_at") or "")[:10]
        lines.append(f"- [{date}] {author} : {content}")
    return "\n".join(lines) if lines else "Aucune note disponible"


def _format_opinions(opinions: List[Dict[str, Any]]) -> Tuple[str, str]:
    ordered = _sort_by_created(opinions)
    lines: List[str] = []
    fav = unfav = other = 0
    for o in ordered:
        rating = (o.get("rating") or "").lower()
        if rating == "favorable":
            label = "Favorable"
            fav += 1
        elif rating == "defavorable":
            label = "Défavorable"
            unfav += 1
        else:
            label = str(o.get("rating") or "—")
            other += 1
        who = (
            f"{o.get('author_first_name', '')} {o.get('author_last_name', '')}".strip()
            or "Intervieweur"
        )
        date = str(o.get("created_at") or "")[:10]
        cm = (o.get("comment") or "").strip()
        suffix = f" — {cm}" if cm else ""
        lines.append(f"- [{date}] {who} : {label}{suffix}")

    text = "\n".join(lines) if lines else "Aucun avis disponible"
    if not opinions:
        summary = "Aucun avis enregistré"
    else:
        parts = []
        if fav:
            parts.append(f"{fav} favorable(s)")
        if unfav:
            parts.append(f"{unfav} défavorable(s)")
        if other:
            parts.append(f"{other} autre(s)")
        summary = ", ".join(parts)
    return text, summary


def _format_interviews(interviews: List[Dict[str, Any]]) -> str:
    if not interviews:
        return "Aucun entretien enregistré"
    ordered = sorted(interviews, key=lambda x: str(x.get("scheduled_at") or ""))
    lines: List[str] = []
    for i in ordered:
        itype = i.get("interview_type") or "Entretien"
        status = i.get("status") or "—"
        date = str(i.get("scheduled_at") or "")[:10]
        summary = (i.get("summary") or "").strip()
        line = f"- [{date}] {itype} ({status})"
        if summary:
            line += f" — Compte-rendu : {summary}"
        else:
            line += " — Pas de compte-rendu"
        lines.append(line)
    return "\n".join(lines)


def _build_data_quality_section(
    *,
    has_cv: bool,
    cv_status: str | None,
    notes_count: int,
    opinions_count: int,
    interviews_count: int,
    interview_summaries_count: int,
) -> str:
    signals: List[str] = []
    if has_cv:
        signals.append(f"CV analysable ({cv_status or 'texte extrait'})")
    elif cv_status:
        signals.append(f"CV : {cv_status}")
    else:
        signals.append("CV : absent")

    signals.append(f"Notes d'entretien : {notes_count}")
    signals.append(f"Avis interviewers : {opinions_count}")
    signals.append(
        f"Entretiens : {interviews_count} "
        f"({interview_summaries_count} avec compte-rendu)"
    )

    richness = sum(
        [
            1 if has_cv else 0,
            1 if notes_count > 0 else 0,
            1 if opinions_count > 0 else 0,
            1 if interview_summaries_count > 0 else 0,
        ]
    )
    if richness >= 3:
        guidance = "Données riches — confiance peut être Haute si cohérent."
    elif richness == 2:
        guidance = "Données partielles — confiance Moyenne au plus."
    elif richness == 1:
        guidance = "Données limitées — confiance Faible ou Moyenne, score prudent."
    else:
        guidance = (
            "Données très insuffisantes — confiance Faible obligatoire, "
            "score ≤ 45, mention Faible ou Moyen."
        )
    return "\n".join(f"- {s}" for s in signals) + f"\n\nConsigne : {guidance}"


def _mention_from_score(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Bon"
    if score >= 40:
        return "Moyen"
    return "Faible"


def _weighted_score(criteres: Dict[str, Any]) -> Optional[int]:
    total = 0.0
    for key, weight in CRITERION_WEIGHTS.items():
        raw = criteres.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        val = max(0.0, min(100.0, val))
        total += val * weight
    return int(round(total))


def _normalize_criteres(raw: Any) -> Dict[str, int]:
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, int] = {}
    for key in CRITERION_WEIGHTS:
        try:
            out[key] = max(0, min(100, int(src.get(key, 0))))
        except (TypeError, ValueError):
            out[key] = 0
    return out


def _apply_calibration(
    score: int,
    *,
    opinions: List[Dict[str, Any]],
    has_cv: bool,
    notes_count: int,
    opinions_count: int,
    interview_summaries_count: int,
) -> int:
    """Ajustements légers pour éviter les scores incohérents avec les faits."""
    fav = sum(
        1 for o in opinions if (o.get("rating") or "").lower() == "favorable"
    )
    unfav = sum(
        1 for o in opinions if (o.get("rating") or "").lower() == "defavorable"
    )

    if unfav >= 2 and fav == 0 and score > 55:
        score = min(score, 55)
    elif unfav >= fav + 2 and unfav >= 2 and score > 65:
        score = min(score, 65)

    richness = sum(
        [
            1 if has_cv else 0,
            1 if notes_count > 0 else 0,
            1 if opinions_count > 0 else 0,
            1 if interview_summaries_count > 0 else 0,
        ]
    )
    if richness == 0:
        score = min(score, 40)
    elif richness == 1 and not has_cv and score > 60:
        score = min(score, 60)

    return max(0, min(100, score))


class ScoringService:
    def score_candidate(
        self,
        candidate: Dict[str, Any],
        job: Dict[str, Any],
        notes: List[Dict[str, Any]],
        opinions: List[Dict[str, Any]],
        interviews: Optional[List[Dict[str, Any]]] = None,
        cv_text: str = "",
        cv_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        interviews = interviews or []
        has_cv = bool((cv_text or "").strip())
        interview_summaries_count = sum(
            1 for i in interviews if (i.get("summary") or "").strip()
        )

        notes_section = _format_notes(notes)
        opinions_section, opinions_summary = _format_opinions(opinions)
        interviews_section = _format_interviews(interviews)

        if has_cv:
            cv_section = cv_text.strip()
        elif cv_status:
            cv_section = f"Non exploitable — {cv_status}"
        else:
            cv_section = "Aucun CV joint"

        data_quality_section = _build_data_quality_section(
            has_cv=has_cv,
            cv_status=cv_status,
            notes_count=len(notes),
            opinions_count=len(opinions),
            interviews_count=len(interviews),
            interview_summaries_count=interview_summaries_count,
        )

        user_prompt = USER_PROMPT.format(
            job_title=job.get("title", ""),
            job_description=job.get("description", "") or "Non précisée",
            contract_type=job.get("contract_type", "") or "Non précisé",
            location=job.get("location", "") or "Non précisée",
            tags=", ".join(job.get("tags") or []) or "Non précisées",
            candidate_name=(
                f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}"
            ).strip(),
            source=candidate.get("source", "") or "Non précisée",
            pipeline_stage=candidate.get("current_stage_name")
            or "Non renseignée",
            cv_section=cv_section,
            interviews_section=interviews_section,
            notes_section=notes_section,
            opinions_section=opinions_section,
            opinions_summary=opinions_summary,
            data_quality_section=data_quality_section,
        )

        require_llm_api_key()
        raw = self._call_model(user_prompt)
        result = json.loads(_strip_json_fence(raw))
        return self._normalize_result(
            result,
            opinions=opinions,
            has_cv=has_cv,
            notes_count=len(notes),
            opinions_count=len(opinions),
            interview_summaries_count=interview_summaries_count,
            cv_status=cv_status,
        )

    def _call_model(self, user_prompt: str) -> str:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = chat_completions_create(
                    model=MODEL_RECRUITMENT_SCORING,
                    max_tokens=1400,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Scoring IA tentative %s échouée: %s", attempt + 1, exc
                )
        if last_error:
            raise last_error
        raise RuntimeError("Réponse vide du modèle IA")

    def _normalize_result(
        self,
        result: Dict[str, Any],
        *,
        opinions: List[Dict[str, Any]],
        has_cv: bool,
        notes_count: int,
        opinions_count: int,
        interview_summaries_count: int,
        cv_status: Optional[str],
    ) -> Dict[str, Any]:
        criteres = _normalize_criteres(result.get("criteres"))
        raw_criteres = result.get("criteres")

        try:
            score = int(result.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        if isinstance(raw_criteres, dict) and any(
            raw_criteres.get(k) is not None for k in CRITERION_WEIGHTS
        ):
            computed = _weighted_score(criteres)
            if computed is not None and abs(score - computed) > 15:
                score = computed

        score = _apply_calibration(
            score,
            opinions=opinions,
            has_cv=has_cv,
            notes_count=notes_count,
            opinions_count=opinions_count,
            interview_summaries_count=interview_summaries_count,
        )
        score = max(0, min(100, score))

        mention = str(result.get("mention") or "").strip()
        if mention not in VALID_MENTIONS:
            mention = _mention_from_score(score)
        elif _mention_from_score(score) != mention:
            expected = _mention_from_score(score)
            if (
                (score >= 80 and mention != "Excellent")
                or (score < 40 and mention == "Excellent")
                or (score < 60 and mention == "Excellent")
            ):
                mention = expected

        confiance = str(result.get("confiance") or "").strip()
        if confiance not in VALID_CONFIDENCE:
            richness = sum(
                [
                    1 if has_cv else 0,
                    1 if notes_count > 0 else 0,
                    1 if opinions_count > 0 else 0,
                    1 if interview_summaries_count > 0 else 0,
                ]
            )
            if richness >= 3:
                confiance = "Haute"
            elif richness >= 2:
                confiance = "Moyenne"
            else:
                confiance = "Faible"

        points_forts: List[str] = []
        raw_pf = result.get("points_forts")
        if isinstance(raw_pf, list):
            points_forts = [str(x).strip() for x in raw_pf if str(x).strip()][:5]

        points_faibles: List[str] = []
        raw_pfb = result.get("points_faibles")
        if isinstance(raw_pfb, list):
            points_faibles = [str(x).strip() for x in raw_pfb if str(x).strip()][:5]

        limites = str(result.get("limites") or "").strip()
        if not limites:
            missing: List[str] = []
            if not has_cv:
                missing.append("CV absent ou non lisible")
            if notes_count == 0:
                missing.append("aucune note d'entretien")
            if opinions_count == 0:
                missing.append("aucun avis interviewer")
            if interview_summaries_count == 0:
                missing.append("aucun compte-rendu d'entretien")
            limites = (
                "Analyse basée sur : "
                + (", ".join(missing) if missing else "données partielles")
            )

        recommandation = str(result.get("recommandation") or "").strip()
        if not recommandation:
            recommandation = (
                f"Profil {mention.lower()} ({score}/100) — "
                "compléter les entretiens pour affiner l'évaluation."
            )

        return {
            "score": score,
            "mention": mention,
            "confiance": confiance,
            "criteres": criteres,
            "points_forts": points_forts,
            "points_faibles": points_faibles,
            "limites": limites,
            "recommandation": recommandation,
            "sources": {
                "cv": has_cv,
                "cv_status": cv_status,
                "notes": notes_count,
                "opinions": opinions_count,
                "interviews": interview_summaries_count,
            },
        }


scoring_service = ScoringService()
