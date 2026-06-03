"""Auto-réparation supervisée d'un parser déterministe (cas B uniquement).

Règles non négociables (architecture v2) :
1. Réparation À L'AVEUGLE : on ne donne JAMAIS la valeur cible au modèle (sinon il
   code en dur ou s'ajuste sur le chiffre). On lui donne le HTML + l'intention.
2. Le parser EXTRAIT, il ne hardcode jamais : le modèle propose un sélecteur
   (CSS + regex + transformation) ; c'est le CODE qui l'exécute et décide.
3. Oracle d'arrêt = invariants structurels (ScraperCheck min/max) ET reproduction
   de la valeur validée par l'humain — JAMAIS « converge avec l'IA ».
4. L'IA est un stagiaire, pas un commiteur : la sortie est un PATCH PROPOSÉ, jamais
   auto-mergé sur le tier critique (relecture humaine obligatoire).
5. N tentatives max + kill-switch global → au-delà, escalade humaine.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ENV_REPAIR_DISABLED = "EYWAI_PARSER_REPAIR_DISABLED"
DEFAULT_MAX_ATTEMPTS = 3
# Tolérance par défaut sur la reproduction de la valeur validée (valeurs en €/taux).
DEFAULT_ABS_TOL = 0.01

_NUMBER_RE = re.compile(r"[-+]?\d[\d\s.,]*")


@dataclass
class RepairProposal:
    """Proposition du modèle : un sélecteur, pas une valeur."""

    css_selector: str
    value_regex: str = r"[-+]?\d[\d\s.,]*"
    transform: str = "float"  # "float" | "percent" | "eur"
    rationale: str = ""


@dataclass
class RepairResult:
    success: bool
    attempts: int
    escalate: bool
    proposal: Optional[RepairProposal] = None
    extracted_value: Optional[float] = None
    reason: str = ""
    history: List[str] = field(default_factory=list)


def repair_disabled() -> bool:
    return os.environ.get(ENV_REPAIR_DISABLED, "").strip() in ("1", "true", "yes")


def _to_float(raw: str) -> Optional[float]:
    """Convertit un nombre français/anglais ('12,31', '1 867.02') en float."""
    cleaned = raw.strip().replace("\u00a0", " ").replace(" ", "")
    if cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def apply_proposal(html: str, proposal: RepairProposal) -> Optional[float]:
    """Exécute le sélecteur proposé sur le HTML et renvoie la valeur extraite.

    Totalement déterministe et sandboxé : aucun code arbitraire n'est exécuté,
    seulement un select CSS + une regex numérique + une transformation connue.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("Parsing HTML échoué: %s", exc)
        return None

    try:
        nodes = soup.select(proposal.css_selector)
    except Exception as exc:
        logger.warning("Sélecteur CSS invalide (%s): %s", proposal.css_selector, exc)
        return None
    if not nodes:
        return None

    text = " ".join(node.get_text(" ", strip=True) for node in nodes)
    try:
        pattern = re.compile(proposal.value_regex)
    except re.error:
        pattern = _NUMBER_RE
    match = pattern.search(text)
    if not match:
        return None

    value = _to_float(match.group(0))
    if value is None:
        return None

    if proposal.transform == "percent":
        return round(value / 100.0, 6)
    if proposal.transform == "eur":
        return round(value, 2)
    return value


def passes_invariants(
    value: float,
    *,
    invariant_min: Optional[float] = None,
    invariant_max: Optional[float] = None,
    checks: Optional[tuple] = None,
) -> bool:
    """Vérifie les bornes structurelles (ScraperCheck min/max ou min/max explicites)."""
    bounds: List[tuple] = []
    if invariant_min is not None or invariant_max is not None:
        bounds.append((invariant_min, invariant_max))
    for check in checks or ():
        cmin = getattr(check, "min", None)
        cmax = getattr(check, "max", None)
        if cmin is not None or cmax is not None:
            bounds.append((cmin, cmax))
    for cmin, cmax in bounds:
        if cmin is not None and value < cmin:
            return False
        if cmax is not None and value > cmax:
            return False
    return True


def reproduces_validated(
    value: float,
    validated_value: float,
    abs_tol: float = DEFAULT_ABS_TOL,
) -> bool:
    return abs(value - validated_value) <= abs_tol


def _default_propose_fn(
    html: str,
    intent: str,
    attempt: int,
    feedback: Optional[str],
) -> Optional[RepairProposal]:
    """Demande au modèle un SÉLECTEUR (jamais la valeur). Réseau requis."""
    try:
        from openrouter_client import (
            MODEL_WEB_SEARCH,
            chat_completions_create,
            require_api_key,
        )

        require_api_key()
    except Exception as exc:
        logger.warning("Proposition IA indisponible: %s", exc)
        return None

    # On tronque le HTML pour rester dans le budget tokens.
    html_excerpt = html[:18000]
    feedback_hint = f"\nLa tentative précédente a échoué : {feedback}" if feedback else ""
    system = (
        "Tu es un ingénieur d'extraction de données. On te donne le HTML d'une page "
        "officielle et l'intention d'extraction. Tu proposes UNIQUEMENT un moyen de "
        "LIRE la valeur depuis la structure : un sélecteur CSS, une regex numérique, "
        "et une transformation. Tu ne fournis JAMAIS de valeur en dur. Réponds en JSON."
    )
    user = (
        f"Intention : {intent}{feedback_hint}\n\n"
        f"HTML (tronqué) :\n{html_excerpt}"
    )
    schema = {
        "type": "object",
        "properties": {
            "css_selector": {"type": "string"},
            "value_regex": {"type": "string"},
            "transform": {"type": "string", "enum": ["float", "percent", "eur"]},
            "rationale": {"type": "string"},
        },
        "required": ["css_selector", "value_regex", "transform", "rationale"],
        "additionalProperties": False,
    }
    try:
        resp = chat_completions_create(
            model=MODEL_WEB_SEARCH,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "parser_repair",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        import json

        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        return RepairProposal(
            css_selector=data["css_selector"],
            value_regex=data.get("value_regex") or r"[-+]?\d[\d\s.,]*",
            transform=data.get("transform") or "float",
            rationale=data.get("rationale", ""),
        )
    except Exception as exc:
        logger.warning("Proposition de réparation IA échouée: %s", exc)
        return None


def repair_parser(
    *,
    html: str,
    intent: str,
    validated_value: float,
    invariant_min: Optional[float] = None,
    invariant_max: Optional[float] = None,
    checks: Optional[tuple] = None,
    abs_tol: float = DEFAULT_ABS_TOL,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    propose_fn: Optional[Callable[..., Optional[RepairProposal]]] = None,
) -> RepairResult:
    """Boucle de réparation à l'aveugle.

    Condition d'arrêt = passe les invariants structurels ET reproduit la valeur
    validée (à abs_tol près). Sinon, après N tentatives, escalade humaine.
    """
    history: List[str] = []

    if repair_disabled():
        return RepairResult(
            success=False,
            attempts=0,
            escalate=True,
            reason="Auto-réparation désactivée (kill-switch global).",
            history=history,
        )

    propose = propose_fn or _default_propose_fn
    feedback: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        proposal = propose(html, intent, attempt, feedback)
        if proposal is None:
            feedback = "aucune proposition exploitable"
            history.append(f"Tentative {attempt}: pas de proposition.")
            continue

        value = apply_proposal(html, proposal)
        if value is None:
            feedback = "le sélecteur ne correspond à aucune valeur numérique"
            history.append(f"Tentative {attempt}: sélecteur sans valeur.")
            continue

        if not passes_invariants(
            value,
            invariant_min=invariant_min,
            invariant_max=invariant_max,
            checks=checks,
        ):
            # Feedback à l'aveugle : on signale « hors plage plausible », jamais la cible.
            feedback = "la valeur extraite est hors de la plage plausible attendue"
            history.append(
                f"Tentative {attempt}: valeur {value} hors invariants."
            )
            continue

        if not reproduces_validated(value, validated_value, abs_tol):
            feedback = "la valeur extraite ne correspond pas à la structure attendue"
            history.append(
                f"Tentative {attempt}: valeur {value} ne reproduit pas la référence."
            )
            continue

        history.append(f"Tentative {attempt}: succès (valeur {value}).")
        return RepairResult(
            success=True,
            attempts=attempt,
            escalate=False,
            proposal=proposal,
            extracted_value=value,
            reason="Sélecteur validé : invariants OK et valeur validée reproduite.",
            history=history,
        )

    return RepairResult(
        success=False,
        attempts=max_attempts,
        escalate=True,
        reason="Échec après N tentatives — escalade humaine.",
        history=history,
    )


def format_repair_patch(proposal: RepairProposal, scraper_name: str) -> str:
    """Patch proposé lisible (jamais auto-mergé sur le critique)."""
    return (
        f"# Proposition de réparation pour {scraper_name} (relecture humaine requise)\n"
        f"# Justification : {proposal.rationale}\n"
        f"css_selector = {proposal.css_selector!r}\n"
        f"value_regex = {proposal.value_regex!r}\n"
        f"transform = {proposal.transform!r}\n"
    )


def _first_numeric_from_config(config_data: Any) -> Optional[float]:
    """Extrait un scalaire représentatif d'une config (oracle simplifié)."""
    if isinstance(config_data, (int, float)):
        return float(config_data)
    if not isinstance(config_data, dict):
        return None
    for key in (
        "cas_general",
        "smic_horaire_brut",
        "annuel",
        "mensuel",
        "patronal",
        "salarial",
        "value",
    ):
        val = config_data.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    for val in config_data.values():
        found = _first_numeric_from_config(val)
        if found is not None:
            return found
    return None


def maybe_propose_parser_repair(
    supabase,
    *,
    scraper_name: str,
    config_key: str,
    source_id: Optional[str],
    source_links: List[str],
) -> None:
    """Cas B + vérité terrain humaine : propose un patch (alerte, jamais auto-merge)."""
    from core.pending import get_last_approved_change

    approved = get_last_approved_change(supabase, config_key)
    if approved is None:
        logger.info(
            "Réparation parser : pas de vérité terrain approuvée pour %s — skip.",
            config_key,
        )
        return

    ground = _first_numeric_from_config(approved.get("proposed_config_data"))
    if ground is None:
        logger.info(
            "Réparation parser : config approuvée non scalaire pour %s — skip.", config_key
        )
        return

    url = source_links[0] if source_links else None
    try:
        from agent.source_registry import fetch_official_source

        official = fetch_official_source(supabase, scraper_name)
        if official and official.primary_url:
            url = official.primary_url
    except Exception:
        pass
    if not url:
        logger.info("Réparation parser : aucune URL source pour %s — skip.", scraper_name)
        return

    try:
        from core.http import fetch_html

        html = fetch_html(url, timeout=25)
    except Exception as exc:
        logger.warning("Réparation parser : fetch HTML échoué (%s): %s", url, exc)
        return

    from scraper_manifest import checks_for

    checks = checks_for(scraper_name)
    cmin = checks[0].min if checks else None
    cmax = checks[0].max if checks else None

    result = repair_parser(
        html=html,
        intent=f"Extraire le taux/valeur officielle pour {scraper_name} ({config_key})",
        validated_value=ground,
        invariant_min=cmin,
        invariant_max=cmax,
        checks=checks,
    )

    if result.success and result.proposal:
        try:
            from agent.jobs import enqueue_repair_job
            from agent.source_registry import fetch_official_source
            from agent.triggers import FailureKind

            official = fetch_official_source(supabase, scraper_name)
            enqueue_repair_job(
                supabase,
                scraper_name=scraper_name,
                trigger="parser_repair",
                source_id=source_id,
                error_message=result.reason or "Parser repair cas B — patch proposé",
                context={
                    "failure_kind": FailureKind.DOM_CHANGE.value,
                    "official_primary_url": official.primary_url if official else url,
                    "config_key": config_key,
                    "patch_preview": format_repair_patch(result.proposal, scraper_name)[:2000],
                },
            )
            logger.info("Job repair enqueued pour parser_repair %s.", scraper_name)
        except Exception as exc:
            logger.warning("Enqueue parser_repair (%s): %s", scraper_name, exc)
    elif result.escalate:
        try:
            from agent.jobs import enqueue_repair_job
            from agent.source_registry import fetch_official_source
            from agent.triggers import FailureKind

            official = fetch_official_source(supabase, scraper_name)
            enqueue_repair_job(
                supabase,
                scraper_name=scraper_name,
                trigger="parser_repair",
                source_id=source_id,
                error_message=f"Parser repair escaladé après {result.attempts} tentatives",
                context={
                    "failure_kind": FailureKind.DOM_CHANGE.value,
                    "official_primary_url": official.primary_url if official else url,
                    "config_key": config_key,
                },
            )
        except Exception as exc:
            logger.warning("Enqueue parser_repair escalade (%s): %s", scraper_name, exc)
        logger.warning(
            "Réparation parser escaladée pour %s après %s tentatives.",
            scraper_name,
            result.attempts,
        )
