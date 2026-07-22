#!/usr/bin/env python3
"""Orchestrateur générique piloté par RateSpec."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from core.alerting import emit_scraping_warnings
from core.consensus import (
    consensus_satisfied,
    merge_source_links,
    prefer_primary_on_divergence,
)
from core.decision import classify_decision
from core.partial_consensus import (
    format_out_of_scope_divergence_warning,
    format_target_divergence_reason,
    partial_targets_diverge,
    signature_has_bundle_items,
    sync_target_item_ids,
    wrap_signatures_equal_for_targets,
)
from cotisation_sync import is_full_cotisations_sync
from utils import is_ai_scraper_label
from core.env import BACKEND_ROOT, ensure_scraping_path, load_env
from core.pending import (
    build_ai_candidate,
    config_changed,
    create_pending_change,
    requires_human_gate,
    resolve_source_id,
)
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.supabase_io import (
    emit_orchestrator_result,
    fetch_active_config,
    init_supabase_client,
    persist_cotisations,
    persist_full_config,
    touch_last_checked_at,
)
from scraper_manifest import tier_for
from utils import is_non_blocking_scraper_label, run_labeled_script

logger = logging.getLogger(__name__)


def is_dry_run(argv: list[str] | None = None) -> bool:
    if os.environ.get("EYWAI_SCRAPING_DRY_RUN", "").strip() in ("1", "true", "yes"):
        return True
    return "--dry-run" in (argv or sys.argv)


def is_ai_disabled(argv: list[str] | None = None) -> bool:
    if os.environ.get("EYWAI_SCRAPING_DISABLE_AI", "").strip() in ("1", "true", "yes"):
        return True
    return "--no-ai" in (argv or sys.argv)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _sig_valid_default(sig: Any) -> bool:
    return sig is not None


def _maybe_enqueue_orchestrator_repair(spec: RateSpec, error: str) -> None:
    """Dépose un job repair agent après échec orchestrateur (hors dry-run optionnel)."""
    from agent.models import agent_disabled

    if agent_disabled():
        return
    try:
        supabase = init_supabase_client()
        from agent.orchestrator import enqueue_from_orchestrator_failure

        enqueue_from_orchestrator_failure(
            supabase,
            scraper_name=spec.scraper_name,
            source_id=resolve_source_id(supabase, spec.source_key or spec.scraper_name),
            error=error,
        )
    except Exception as exc:
        logger.warning("Enqueue repair orchestrateur échoué : %s", exc)


def run_orchestrator(spec: RateSpec, *, argv: list[str] | None = None) -> int:
    """Exécute le pipeline complet pour un taux."""
    ensure_scraping_path()
    load_env()
    setup_logging()
    dry = is_dry_run(argv)
    skip_ai = is_ai_disabled(argv)

    if dry:
        logger.info("Mode --dry-run : aucune écriture Supabase")
    if skip_ai:
        logger.info("Mode --no-ai : scripts *_AI.py ignorés")
    dual_required = spec.requires_scraper_sonar_consensus()
    if dual_required and skip_ai:
        logger.error(
            "Consensus scraper + Sonar requis pour %s — relancez sans --no-ai.",
            spec.scraper_name,
        )
        raise SystemExit(2)

    warnings: List[str] = []
    logger.info("--- DÉBUT Orchestrateur %s ---", spec.scraper_name)

    try:
        payloads: List[Dict[str, Any]] = []
        labels: List[str] = []
        cwd = str(BACKEND_ROOT)

        for script in spec.scripts:
            if not script.enabled:
                continue
            if skip_ai and is_ai_scraper_label(script.label):
                logger.info("IA ignorée (--no-ai): %s", script.label)
                continue
            res = _run_one(script, cwd=cwd, timeout=spec.script_timeout)
            if res is None:
                continue
            if spec.accept_payload and not spec.accept_payload(script.label, res):
                logger.warning("Payload rejeté pour %s", script.label)
                continue
            payloads.append(res)
            labels.append(script.label)

        if not payloads:
            raise SystemExit(2)

        sigs: List[Any] = []
        valid_payloads: List[Dict[str, Any]] = []
        valid_labels: List[str] = []
        for i, p in enumerate(payloads):
            try:
                sig = spec.extract_signature(p)
            except (ValueError, SystemExit) as e:
                logger.warning("Signature ignorée (%s): %s", labels[i], e)
                continue
            sigs.append(sig)
            valid_payloads.append(p)
            valid_labels.append(labels[i])

        if not sigs:
            raise SystemExit(2)

        business_sigs: List[Any] = []
        business_payloads: List[Dict[str, Any]] = []
        business_labels: List[str] = []
        for i, sig in enumerate(sigs):
            check = spec.validate_signature(sig)
            if not check.ok:
                logger.warning(
                    "Signature métier ignorée (%s): %s",
                    valid_labels[i],
                    check.message,
                )
                continue
            business_sigs.append(sig)
            business_payloads.append(valid_payloads[i])
            business_labels.append(valid_labels[i])

        if not business_sigs:
            logger.error("Aucune signature métier valide")
            raise SystemExit(2)

        sync_targets = sync_target_item_ids()
        signatures_equal_eff = wrap_signatures_equal_for_targets(
            spec.signatures_equal,
            sync_targets,
        )
        partial_failure_reason: Optional[str] = None
        if dual_required and sync_targets and len(business_sigs) >= 2:
            primary_idx = next(
                (
                    i
                    for i, lab in enumerate(business_labels)
                    if lab == spec.primary_label
                ),
                None,
            )
            ai_idx = next(
                (i for i, lab in enumerate(business_labels) if is_ai_scraper_label(lab)),
                None,
            )
            if (
                primary_idx is not None
                and ai_idx is not None
                and isinstance(business_sigs[primary_idx], dict)
                and isinstance(business_sigs[ai_idx], dict)
            ):
                divergent_targets = partial_targets_diverge(
                    business_sigs[primary_idx],
                    business_sigs[ai_idx],
                    sync_targets,
                    signatures_equal=spec.signatures_equal,
                )
                if divergent_targets:
                    partial_failure_reason = format_target_divergence_reason(
                        divergent_targets
                    )

        decision = classify_decision(
            business_labels,
            business_sigs,
            primary_label=spec.primary_label,
            signatures_equal=signatures_equal_eff,
            dual_source_consensus=dual_required,
            partial_failure_reason=partial_failure_reason,
        )

        if dual_required:
            if not decision.ok:
                logger.error("%s", decision.reason)
                emit_scraping_warnings(
                    spec.scraper_name,
                    [decision.reason],
                    single_source=decision.ai_count == 0,
                )
                raise SystemExit(2)
            if sync_targets and not is_full_cotisations_sync():
                primary_idx = decision.ref_idx
                ai_idx = next(
                    (
                        i
                        for i, lab in enumerate(business_labels)
                        if is_ai_scraper_label(lab)
                    ),
                    None,
                )
                if (
                    ai_idx is not None
                    and isinstance(business_sigs[primary_idx], dict)
                    and isinstance(business_sigs[ai_idx], dict)
                    and signature_has_bundle_items(
                        business_sigs[primary_idx], sync_targets
                    )
                ):
                    all_keys = set(business_sigs[primary_idx]) | set(
                        business_sigs[ai_idx]
                    )
                    out_of_scope = sorted(all_keys - sync_targets)
                    divergent_other = partial_targets_diverge(
                        business_sigs[primary_idx],
                        business_sigs[ai_idx],
                        set(out_of_scope),
                        signatures_equal=spec.signatures_equal,
                    )
                    if divergent_other:
                        msg = format_out_of_scope_divergence_warning(
                            divergent_other
                        )
                        logger.warning(msg)
                        warnings.append(msg)
            final_sig = business_sigs[decision.ref_idx]
        else:
            ok, ref_idx = consensus_satisfied(business_sigs, spec.signatures_equal)
            if len(business_sigs) == 1 and spec.warn_single_source:
                msg = "Une seule source valide — pas de concordance croisée"
                logger.warning(msg)
                warnings.append(msg)
                emit_scraping_warnings(
                    spec.scraper_name,
                    warnings,
                    single_source=True,
                )

            if not ok and spec.primary_label:
                ok, ref_idx = prefer_primary_on_divergence(
                    ok,
                    ref_idx,
                    business_labels,
                    business_sigs,
                    spec.primary_label,
                    _sig_valid_default,
                )
                if ok:
                    warnings.append(
                        f"Divergence secondaires — référence {spec.primary_label}"
                    )

            if not ok:
                logger.error("Divergence entre sources")
                raise SystemExit(2)

            final_sig = business_sigs[ref_idx]

        validation = spec.validate_signature(final_sig)
        if not validation.ok:
            logger.error("Validation métier échouée: %s", validation.message)
            raise SystemExit(2)
        ai_candidate = build_ai_candidate(
            business_labels,
            business_sigs,
            business_payloads,
            is_ai=is_ai_scraper_label,
        )

        source_links = merge_source_links(business_payloads)
        sources_used = [p.get("__script", "?") for p in business_payloads]

        emit_data = (
            spec.signature_for_emit(final_sig)
            if spec.signature_for_emit
            else (
                final_sig
                if isinstance(final_sig, dict)
                else {"value": final_sig}
            )
        )

        effective_tier = spec.tier or tier_for(spec.scraper_name)
        requires_review = False
        current_emit: Optional[Dict[str, Any]] = None
        proposed_emit: Optional[Dict[str, Any]] = None

        if not dry:
            emit_scraping_warnings(spec.scraper_name, warnings)
            supabase = init_supabase_client()
            current_row = fetch_active_config(supabase, spec.config_key)
            new_data = spec.build_config_data(final_sig, current_row)
            comment = spec.comment or f"Mise à jour automatique: {spec.config_key}"
            changed = config_changed(
                spec.persistence_mode.value, current_row, new_data
            )
            gate = requires_human_gate(
                effective_tier,
                changed,
                decision.case,
                decision.ai_divergence,
            )

            if gate:
                # Gate : tier critique — aucune écriture directe, validation humaine.
                # On ne dépose une revue que s'il y a vraiment quelque chose à
                # valider (changement réel ou IA divergente). Une valeur critique
                # confirmée inchangée (ex. source unique, cas B) ne doit pas créer
                # de pending « no-op » : on rafraîchit simplement last_checked_at.
                if changed or decision.ai_divergence:
                    requires_review = True
                    current_emit = (current_row or {}).get("config_data")
                    proposed_emit = new_data
                    if decision.ai_divergence:
                        warnings.append("IA divergente — valeur à valider (tripwire).")
                    create_pending_change(
                        supabase,
                        scraper_name=spec.scraper_name,
                        config_key=spec.config_key,
                        tier=effective_tier,
                        persistence_mode=spec.persistence_mode.value,
                        proposed_config_data=new_data,
                        current_row=current_row,
                        source_links=source_links,
                        decision_case=decision.case,
                        sources_agreement=decision.sources_agreement,
                        discrepancies=decision.discrepancies,
                        ai_candidate=ai_candidate,
                        warnings=warnings,
                        source_id=resolve_source_id(
                            supabase, spec.source_key or spec.scraper_name
                        ),
                    )
                    logger.info(
                        "Tier critique : changement déposé en validation humaine "
                        "(payroll_config inchangé)."
                    )
                    if decision.case == "B":
                        from core.parser_repair import maybe_propose_parser_repair

                        maybe_propose_parser_repair(
                            supabase,
                            scraper_name=spec.scraper_name,
                            config_key=spec.config_key,
                            source_id=resolve_source_id(
                                supabase, spec.source_key or spec.scraper_name
                            ),
                            source_links=source_links,
                        )
                else:
                    logger.info(
                        "Tier critique : valeur confirmée inchangée — "
                        "aucune revue nécessaire, last_checked_at mis à jour."
                    )
                touch_last_checked_at(
                    supabase,
                    config_key=spec.config_key,
                    persistence_mode=spec.persistence_mode.value,
                    current_row=current_row,
                    source_links=source_links,
                )
            elif spec.persistence_mode == PersistenceMode.COTISATIONS:
                persist_cotisations(
                    supabase,
                    new_config_data=new_data,
                    source_links=source_links,
                    comment=comment,
                    current_row=current_row,
                )
            else:
                persist_full_config(
                    supabase,
                    config_key=spec.config_key,
                    new_config_data=new_data,
                    source_links=source_links,
                    comment=comment,
                    current_row=current_row,
                )
        else:
            logger.info("Dry-run — données validées, pas d'écriture")

        logger.info("--- FIN Orchestrateur %s ---", spec.scraper_name)
        emit_orchestrator_result(
            scraper=spec.scraper_name,
            success=True,
            config_key=spec.config_key,
            data=emit_data if isinstance(emit_data, dict) else {"data": emit_data},
            sources_used=sources_used,
            warnings=warnings or None,
            decision_case=decision.case,
            sources_agreement=decision.sources_agreement,
            discrepancies=decision.discrepancies,
            current_value=current_emit,
            proposed_value=proposed_emit,
            ai_candidate=ai_candidate,
            tier=effective_tier,
            requires_review=requires_review,
        )
        return 0

    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        _maybe_enqueue_orchestrator_repair(spec, str(e))
        emit_orchestrator_result(
            scraper=spec.scraper_name,
            success=False,
            config_key=spec.config_key,
            data={},
            sources_used=[],
            error=str(e),
        )
        return code if isinstance(code, int) else 1
    except Exception as e:
        logger.critical("Erreur fatale: %s", e, exc_info=True)
        _maybe_enqueue_orchestrator_repair(spec, str(e))
        emit_orchestrator_result(
            scraper=spec.scraper_name,
            success=False,
            config_key=spec.config_key,
            data={},
            sources_used=[],
            error=str(e),
        )
        return 1


def _run_one(
    script: ScraperScript,
    *,
    cwd: str,
    timeout: int,
) -> Optional[Dict[str, Any]]:
    non_blocking = (
        not script.blocking
        or is_ai_scraper_label(script.label)
        or is_non_blocking_scraper_label(script.label)
    )
    try:
        return run_labeled_script(
            script.label, script.path, cwd=cwd, timeout=timeout
        )
    except SystemExit:
        if non_blocking:
            return None
        raise
    except Exception as e:
        logger.error("Erreur %s: %s", script.label, e)
        if non_blocking:
            return None
        raise


def main_entry(spec: RateSpec) -> None:
    parser = argparse.ArgumentParser(description=f"Orchestrateur {spec.scraper_name}")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valide et émet le JSON sans écrire en base",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Ignore les scripts *_AI.py (pas d'appel OpenRouter)",
    )
    args, _ = parser.parse_known_args()
    if args.dry_run:
        os.environ["EYWAI_SCRAPING_DRY_RUN"] = "1"
    if args.no_ai:
        os.environ["EYWAI_SCRAPING_DISABLE_AI"] = "1"
    sys.exit(run_orchestrator(spec))
