"""
Chargement centralisé des barèmes payroll_config (moteur + simulation + tests).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def _float_in_range(value: Any, *, name: str, min_v: float, max_v: float) -> Optional[str]:
    if value is None:
        return f"{name} manquant"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return f"{name} non numérique: {value!r}"
    if not (min_v <= f <= max_v):
        return f"{name}={f} hors [{min_v}, {max_v}]"
    return None


def ensure_dict(val: Any) -> Dict[str, Any]:
    """Normalise config_data (dict ou chaîne JSON)."""
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return val if isinstance(val, dict) else {}


def charger_db_baremes(supabase) -> Dict[str, Any]:
    """Lit payroll_config actif et retourne config_key -> config_data."""
    configs = (
        supabase.table("payroll_config")
        .select("config_key, config_data")
        .eq("is_active", True)
        .execute()
    )
    if not configs.data:
        raise RuntimeError(
            "Aucune configuration de paie active trouvée dans Supabase."
        )
    return {
        c["config_key"]: ensure_dict(c.get("config_data")) for c in configs.data
    }


def charger_conventions_collectives(supabase) -> Dict[str, Any]:
    """Charge convention_collective_rules indexées par idcc_{idcc}."""
    conventions: Dict[str, Any] = {}
    try:
        cc_rules_resp = (
            supabase.table("convention_collective_rules")
            .select("idcc, rules")
            .execute()
        )
        if cc_rules_resp.data:
            for row in cc_rules_resp.data:
                idcc = row.get("idcc")
                rules = ensure_dict(row.get("rules"))
                if idcc:
                    conventions[f"idcc_{idcc}"] = rules
    except Exception:
        pass
    return conventions


def _extract_primes_list(primes_data: Any) -> List[Dict[str, Any]]:
    if isinstance(primes_data, dict):
        primes_list = primes_data.get("primes", [])
    elif isinstance(primes_data, list):
        primes_list = primes_data
    else:
        primes_list = []
    return primes_list if isinstance(primes_list, list) else []


def assembler_baremes(
    db_baremes: Dict[str, Any],
    conventions_collectives: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construit le dict self.baremes final (source unique moteur + simulation).
    """
    pas_data = db_baremes.get("pas", {})
    if isinstance(pas_data, dict):
        pas_baremes = pas_data.get("baremes", [])
    else:
        pas_baremes = []

    primes_list = _extract_primes_list(db_baremes.get("primes", {}))

    taux_vmrr = db_baremes.get("taux_vmrr", {})
    if isinstance(taux_vmrr, list):
        vmrr_payload: Any = taux_vmrr
    else:
        vmrr_payload = taux_vmrr

    return {
        "cotisations": db_baremes.get("cotisations", {}),
        "pas": pas_baremes if isinstance(pas_baremes, list) else [],
        "smic": db_baremes.get("smic", {}),
        "pss": db_baremes.get("pss", {}),
        "frais_pro": db_baremes.get("frais_pro", {}),
        "heures_supp": db_baremes.get("heures_supp", {}),
        "primes": primes_list,
        "conventions_collectives": conventions_collectives or {},
        "ij_plafonds": db_baremes.get("ij_plafonds", {}),
        "baremes_km": db_baremes.get("baremes_km", {}),
        "taux_vmrr": vmrr_payload,
        "alternance": db_baremes.get("alternance", {}),
        "reduction_generale": db_baremes.get("reduction_generale", {}),
        "stage": db_baremes.get("stage", {}),
        "cdd": db_baremes.get("cdd", {}),
    }


def baremes_lookup(
    baremes: Dict[str, Any],
    cle: str,
    *chemin: str,
    alertes: Optional[List[Dict[str, Any]]] = None,
    critique: bool = False,
) -> Any:
    """
    Lit une valeur scrapée dans baremes. Si absente : None + alerte (pas de défaut numérique).
    """
    bloc = baremes.get(cle)
    if bloc is None:
        _ajouter_alerte(
            alertes,
            code="bareme_cle_absente",
            cle=cle,
            chemin=list(chemin),
            critique=critique,
            message=f"Clé barème absente : {cle}",
        )
        return None

    cur: Any = bloc
    path_so_far: List[str] = []
    for segment in chemin:
        path_so_far.append(str(segment))
        if not isinstance(cur, dict):
            _ajouter_alerte(
                alertes,
                code="bareme_chemin_invalide",
                cle=cle,
                chemin=path_so_far,
                critique=critique,
                message=f"Chemin invalide {cle}.{'.'.join(path_so_far)}",
            )
            return None
        if segment not in cur:
            _ajouter_alerte(
                alertes,
                code="bareme_chemin_absent",
                cle=cle,
                chemin=path_so_far,
                critique=critique,
                message=f"Valeur absente : {cle}.{'.'.join(path_so_far)}",
            )
            return None
        cur = cur[segment]

    return cur


def _ajouter_alerte(
    alertes: Optional[List[Dict[str, Any]]],
    *,
    code: str,
    cle: str,
    chemin: List[str],
    critique: bool,
    message: str,
) -> None:
    if alertes is None:
        return
    alertes.append(
        {
            "code": code,
            "config_key": cle,
            "chemin": chemin,
            "critique": critique,
            "severity": "warning" if critique else "info",
            "message": message,
            "donnee_non_officielle": True,
        }
    )


def controler_integrite_baremes(baremes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Contrôles de présence et plausibilité non bloquants."""
    alertes: List[Dict[str, Any]] = []

    smic = baremes.get("smic") or {}
    if isinstance(smic, dict):
        cg = smic.get("cas_general")
        msg = _float_in_range(cg, name="smic.cas_general", min_v=9.0, max_v=20.0)
        if msg:
            alertes.append(
                {
                    "code": "integrite_smic",
                    "severity": "warning",
                    "message": msg,
                    "donnee_non_officielle": True,
                }
            )
    else:
        alertes.append(
            {
                "code": "integrite_smic_absent",
                "severity": "warning",
                "message": "Barème SMIC absent",
                "donnee_non_officielle": True,
            }
        )

    pss = baremes.get("pss") or {}
    if isinstance(pss, dict):
        mensuel = pss.get("mensuel")
        msg = _float_in_range(mensuel, name="pss.mensuel", min_v=3000.0, max_v=6000.0)
        if msg:
            alertes.append(
                {
                    "code": "integrite_pss",
                    "severity": "warning",
                    "message": msg,
                    "donnee_non_officielle": True,
                }
            )
    else:
        alertes.append(
            {
                "code": "integrite_pss_absent",
                "severity": "warning",
                "message": "Barème PSS absent",
                "donnee_non_officielle": True,
            }
        )

    reduction_generale = baremes.get("reduction_generale") or {}
    if isinstance(reduction_generale, dict) and reduction_generale:
        # Contrôles de plausibilité des paramètres RGDU (cohérent avec baremes_lookup).
        controles_rgdu = [
            ("reduction_generale.tmin", reduction_generale.get("tmin"), 0.0, 0.05),
            ("reduction_generale.p", reduction_generale.get("p"), 1.0, 3.0),
            (
                "reduction_generale.point_sortie_smic",
                reduction_generale.get("point_sortie_smic"),
                3.0,
                3.0,
            ),
        ]
        tdelta = reduction_generale.get("tdelta")
        if isinstance(tdelta, dict):
            controles_rgdu.append(
                ("reduction_generale.tdelta.fnal_moins_50", tdelta.get("fnal_moins_50"), 0.30, 0.45)
            )
            controles_rgdu.append(
                ("reduction_generale.tdelta.fnal_50_et_plus", tdelta.get("fnal_50_et_plus"), 0.30, 0.45)
            )
        for nom, valeur, min_v, max_v in controles_rgdu:
            msg = _float_in_range(valeur, name=nom, min_v=min_v, max_v=max_v)
            if msg:
                alertes.append(
                    {
                        "code": "integrite_reduction_generale",
                        "severity": "warning",
                        "message": msg,
                        "donnee_non_officielle": True,
                    }
                )

    cotisations = baremes.get("cotisations") or {}
    liste: List[Any] = []
    if isinstance(cotisations, dict):
        root_key = next(
            (k for k, v in cotisations.items() if isinstance(v, list)), None
        )
        if root_key:
            liste = cotisations.get(root_key, [])
        elif isinstance(cotisations.get("cotisations"), list):
            liste = cotisations["cotisations"]
    if not liste:
        alertes.append(
            {
                "code": "integrite_cotisations_vides",
                "severity": "warning",
                "message": "Liste des cotisations vide",
                "donnee_non_officielle": True,
            }
        )

    return alertes


def comparer_taux_vm_entreprise(
    taux_entreprise: Optional[float],
    taux_vmrr: Any,
    *,
    commune: Optional[str] = None,
    tolerance: float = 0.001,
) -> Optional[Dict[str, Any]]:
    """
    Contrôle de cohérence VM entreprise vs barème scrapé (alerte, pas de calcul auto).
    Retourne une alerte dict si écart détecté, sinon None.
    """
    if taux_entreprise is None:
        return None
    if not taux_vmrr:
        return {
            "code": "vm_bareme_absent",
            "severity": "info",
            "message": "Barème taux_vmrr absent — contrôle VM impossible",
        }

    taux_officiel: Optional[float] = None
    rows: List[Dict[str, Any]] = []
    if isinstance(taux_vmrr, list):
        rows = [r for r in taux_vmrr if isinstance(r, dict)]
    elif isinstance(taux_vmrr, dict):
        inner = taux_vmrr.get("rows") or taux_vmrr.get("taux") or []
        if isinstance(inner, list):
            rows = [r for r in inner if isinstance(r, dict)]

    if commune and rows:
        commune_norm = commune.strip().lower()
        for row in rows:
            lib = str(
                row.get("commune")
                or row.get("libelle")
                or row.get("Commune")
                or ""
            ).lower()
            if commune_norm in lib or lib in commune_norm:
                raw = row.get("taux") or row.get("Taux") or row.get("taux_vm")
                if raw is not None:
                    try:
                        taux_officiel = float(raw)
                        break
                    except (TypeError, ValueError):
                        pass

    if taux_officiel is None:
        return {
            "code": "vm_commune_introuvable",
            "severity": "info",
            "message": "Taux VM officiel introuvable pour la commune — contrôle partiel",
        }

    try:
        te = float(taux_entreprise)
    except (TypeError, ValueError):
        return {
            "code": "vm_entreprise_invalide",
            "severity": "warning",
            "message": "Taux VM entreprise non numérique",
        }

    if abs(te - taux_officiel) > tolerance:
        return {
            "code": "vm_ecart_taux",
            "severity": "warning",
            "message": (
                f"Écart VM : entreprise={te:.4f} vs officiel={taux_officiel:.4f}"
            ),
            "taux_entreprise": te,
            "taux_officiel": taux_officiel,
        }
    return None
