"""Analyse mobilité interne et recommandations formations (OpenAI)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from openai import OpenAI

MOBILITY_PROMPT = """
Tu es un expert RH spécialisé en mobilité interne et développement
des talents.

PROFIL DU SALARIÉ :
Nom : {employee_name}
Poste actuel : {job_title}

COMPÉTENCES ACTUELLES (scores sur échelle 0-4, 4 = niveau max) :
{competencies_list}

GAPS IDENTIFIÉS (compétences en dessous du niveau requis) :
{gaps_list}

CATALOGUE FORMATIONS ACTIVES (titre et identifiant) :
{catalogue_text}

POSTES DISPONIBLES DANS L'ENTREPRISE (intitulés distincts) :
{available_positions}

Analyse ce profil et réponds UNIQUEMENT en JSON valide :
{{
  "mobilite_score": <entier 0-100>,
  "potentiel_evolution": "<Fort|Moyen|Faible>",
  "postes_recommandes": [
    {{
      "poste": "<intitulé>",
      "compatibilite": <entier 0-100>,
      "points_forts": ["<point>"],
      "competences_a_developper": ["<compétence>"]
    }}
  ],
  "formations_recommandees": [
    {{
      "training_id": "<id ou null>",
      "titre": "<titre formation>",
      "priorite": "<Haute|Moyenne|Faible>",
      "competence_ciblee": "<nom compétence>",
      "impact_estime": "<description courte>"
    }}
  ],
  "synthese": "<paragraphe de synthèse 2-3 lignes>"
}}

Limite à 3 postes recommandés et 5 formations max.
Préfère remplir training_id avec un id du catalogue lorsque c'est pertinent.
Si les données sont insuffisantes, indiquer "Données
insuffisantes" dans la synthèse et retourner des listes vides.
"""


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip().startswith("json"):
                s = s.lstrip()[4:].lstrip()
    return s.strip()


class TalentAIService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if not self._client:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY non définie")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def analyze_mobility(
        self,
        employee: Dict[str, Any],
        competencies: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
        available_trainings: List[Dict[str, Any]],
        available_positions: List[str],
    ) -> Dict[str, Any]:
        """
        Analyse le profil de mobilité d'un salarié.
        Retourne un dict avec mobilite_score, potentiel_evolution,
        postes_recommandes, formations_recommandees, synthese.
        """
        comp_text = "\n".join(
            [
                f"- {c.get('name', '')}: {c.get('score', 0)}/4"
                for c in competencies
            ]
        ) or "Aucune compétence évaluée"

        def _gap_line(g: Dict[str, Any]) -> str:
            cur = g.get("current_score", g.get("score", 0))
            req = g.get("required_level", 0)
            return (
                f"- {g.get('competency_name', '')}: "
                f"niveau actuel {cur}/4, requis {req}/4"
            )

        gaps_text = "\n".join([_gap_line(g) for g in gaps]) or "Aucun gap identifié"

        cat_lines = []
        for t in available_trainings:
            tid = t.get("id")
            title = (t.get("title") or "").strip()
            if tid is not None and title:
                cat_lines.append(f"- {title} (id: {tid})")
        catalogue_text = "\n".join(cat_lines) or "Aucune formation active"

        positions_text = "\n".join([f"- {p}" for p in available_positions[:10]]) or "Non renseignés"

        prompt = MOBILITY_PROMPT.format(
            employee_name=(
                f"{employee.get('first_name', '')} {employee.get('last_name', '')}"
            ).strip()
            or "Collaborateur",
            job_title=employee.get("job_title") or "Non renseigné",
            competencies_list=comp_text,
            gaps_list=gaps_text,
            catalogue_text=catalogue_text,
            available_positions=positions_text,
        )

        client = self._get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = _strip_json_fence(raw)
        result = json.loads(raw)

        mobilite = int(result.get("mobilite_score", 0))
        result["mobilite_score"] = max(0, min(100, mobilite))

        pe = str(result.get("potentiel_evolution") or "").strip()
        if pe not in ("Fort", "Moyen", "Faible"):
            score = int(result["mobilite_score"])
            if score >= 70:
                result["potentiel_evolution"] = "Fort"
            elif score >= 40:
                result["potentiel_evolution"] = "Moyen"
            else:
                result["potentiel_evolution"] = "Faible"
        else:
            result["potentiel_evolution"] = pe

        posts = result.get("postes_recommandes")
        if not isinstance(posts, list):
            posts = []
        norm_posts: List[Dict[str, Any]] = []
        for p in posts[:3]:
            if not isinstance(p, dict):
                continue
            co = int(p.get("compatibilite", 0))
            pts = p.get("points_forts")
            cds = p.get("competences_a_developper")
            norm_posts.append(
                {
                    "poste": str(p.get("poste") or ""),
                    "compatibilite": max(0, min(100, co)),
                    "points_forts": [str(x) for x in pts] if isinstance(pts, list) else [],
                    "competences_a_developper": [str(x) for x in cds]
                    if isinstance(cds, list)
                    else [],
                }
            )
        result["postes_recommandes"] = norm_posts

        forms = result.get("formations_recommandees")
        if not isinstance(forms, list):
            forms = []
        norm_forms: List[Dict[str, Any]] = []
        for f in forms[:5]:
            if not isinstance(f, dict):
                continue
            tid = f.get("training_id")
            if tid is not None and tid != "null":
                tid = str(tid).strip() or None
            else:
                tid = None
            pr = str(f.get("priorite") or "Moyenne").strip()
            if pr not in ("Haute", "Moyenne", "Faible"):
                pr = "Moyenne"
            norm_forms.append(
                {
                    "training_id": tid,
                    "titre": str(f.get("titre") or ""),
                    "priorite": pr,
                    "competence_ciblee": str(f.get("competence_ciblee") or ""),
                    "impact_estime": str(f.get("impact_estime") or ""),
                }
            )
        result["formations_recommandees"] = norm_forms

        syn = result.get("synthese")
        result["synthese"] = str(syn) if syn is not None else ""

        # Croiser formations_recommandees avec training_catalog
        id_set = {str(t.get("id")) for t in available_trainings if t.get("id") is not None}
        for rec in norm_forms:
            tid = rec.get("training_id")
            if tid and str(tid) in id_set:
                continue
            titre = (rec.get("titre") or "").strip()
            if not titre:
                continue
            words = [w for w in titre.split() if len(w) > 4]
            for t in available_trainings:
                t_title = (t.get("title") or "").lower()
                if any(kw.lower() in t_title for kw in words):
                    rec["training_id"] = str(t.get("id")) if t.get("id") is not None else None
                    break

        return result


talent_ai_service = TalentAIService()
