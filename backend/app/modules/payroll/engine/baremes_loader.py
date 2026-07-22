"""
Chargement centralisé des barèmes payroll_config (moteur + simulation + tests).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


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
    """Normalise une valeur attendue en dict (règles CCN, etc.)."""
    if val is None:
        return {}
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return val if isinstance(val, dict) else {}


def ensure_config_data(val: Any) -> Any:
    """Normalise payroll_config.config_data (dict, liste JSON, ou chaîne JSON).

    Important : certains barèmes (ex. taux_vmrr) sont stockés comme listes de
    lignes — ne pas les réduire à {} via ensure_dict.
    """
    if val is None:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, (dict, list)):
            return parsed
        return {}
    return {}


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
        c["config_key"]: ensure_config_data(c.get("config_data"))
        for c in configs.data
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
                    conventions[f"idcc_{idcc}"] = _enrich_cc_rules_with_seed(
                        rules, str(idcc)
                    )
    except Exception:
        pass
    return conventions


def _enrich_cc_rules_with_seed(rules: dict[str, Any], idcc: str) -> dict[str, Any]:
    """Complète les règles CCN manquantes (ex. prime d'ancienneté) via seed officiel."""
    try:
        from app.modules.collective_agreements.rules.schema import (
            CCRulesDocument,
            document_to_engine_rules,
        )
        from app.modules.collective_agreements.rules.seeds import (
            apply_seed_to_document,
            get_seed,
        )

        seed = get_seed(idcc)
        if not seed or not seed.prime:
            return rules
        doc = CCRulesDocument(idcc=idcc)
        doc = apply_seed_to_document(doc, seed)
        engine_rules = document_to_engine_rules(doc)
        prime = engine_rules.get("prime_anciennete")
        if not prime:
            return rules
        merged = dict(rules)
        existing = rules.get("prime_anciennete")
        if not isinstance(existing, dict) or not existing:
            merged["prime_anciennete"] = prime
            return merged

        # Une extraction Légifrance partielle ne doit pas neutraliser les
        # compléments déterministes du seed (plafond d'ancienneté, zones de
        # valeur du point, prorata…). Les valeurs extraites restent prioritaires.
        enriched_prime = dict(prime)
        enriched_prime.update(existing)
        for key in (
            "base_de_calcul",
            "eligibilite",
            "prorata",
            "taux_par_classe",
        ):
            defaults = prime.get(key)
            current = existing.get(key)
            if isinstance(defaults, dict) and isinstance(current, dict):
                enriched_prime[key] = {**defaults, **current}

        seed_zones = prime.get("valeurs_point") or []
        current_zones = existing.get("valeurs_point") or []
        if isinstance(seed_zones, list) and isinstance(current_zones, list):
            enriched_prime["valeurs_point"] = list(current_zones) + [
                zone for zone in seed_zones if zone not in current_zones
            ]

        merged["prime_anciennete"] = enriched_prime
        return merged
    except Exception:
        return rules


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
        "interim": db_baremes.get("interim", {}),
        "conges": db_baremes.get("conges", {}),
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
        if isinstance(cur, dict):
            if segment in cur:
                cur = cur[segment]
            elif str(segment) in cur:
                cur = cur[str(segment)]
            else:
                _ajouter_alerte(
                    alertes,
                    code="bareme_chemin_absent",
                    cle=cle,
                    chemin=path_so_far,
                    critique=critique,
                    message=f"Valeur absente : {cle}.{'.'.join(path_so_far)}",
                )
                return None
        elif isinstance(cur, list):
            try:
                idx = int(segment)
            except (TypeError, ValueError):
                _ajouter_alerte(
                    alertes,
                    code="bareme_chemin_invalide",
                    cle=cle,
                    chemin=path_so_far,
                    critique=critique,
                    message=f"Chemin invalide {cle}.{'.'.join(path_so_far)}",
                )
                return None
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                _ajouter_alerte(
                    alertes,
                    code="bareme_chemin_absent",
                    cle=cle,
                    chemin=path_so_far,
                    critique=critique,
                    message=f"Valeur absente : {cle}.{'.'.join(path_so_far)}",
                )
                return None
        else:
            _ajouter_alerte(
                alertes,
                code="bareme_chemin_invalide",
                cle=cle,
                chemin=path_so_far,
                critique=critique,
                message=f"Chemin invalide {cle}.{'.'.join(path_so_far)}",
            )
            return None

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


def _normaliser_taux_vm_decimal(raw: Any) -> Optional[float]:
    """Convertit une valeur barème VM en décimal (0.025), sans défaut arbitraire."""
    if raw is None:
        return None
    try:
        if isinstance(raw, str):
            raw = raw.replace(",", ".").replace("%", "").strip()
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if abs(val) > 1:
        val = val / 100.0
    return val


def _lignes_vmrr(taux_vmrr: Any) -> List[Dict[str, Any]]:
    if isinstance(taux_vmrr, list):
        return [r for r in taux_vmrr if isinstance(r, dict)]
    if isinstance(taux_vmrr, dict):
        inner = taux_vmrr.get("rows") or taux_vmrr.get("taux") or []
        if isinstance(inner, list):
            return [r for r in inner if isinstance(r, dict)]
    return []


def _libelle_commune_vmrr(row: Dict[str, Any]) -> str:
    for key, val in row.items():
        key_l = str(key).lower()
        if val is None or not str(val).strip():
            continue
        if key_l in ("commune", "libelle", "libcom", "libcommune") or "commune" in key_l:
            return str(val).strip()
    for key in ("commune", "libelle", "Commune", "LIBCOM"):
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _taux_ligne_vmrr(row: Dict[str, Any]) -> Optional[float]:
    for key in ("taux", "Taux", "taux_vm", "TAUX", "Taux VM", "TauxVM"):
        if key in row:
            taux = _normaliser_taux_vm_decimal(row[key])
            if taux is not None:
                return taux
    for key, val in row.items():
        if "taux" in str(key).lower():
            taux = _normaliser_taux_vm_decimal(val)
            if taux is not None:
                return taux
    return None


def commune_entreprise_depuis_donnees(entreprise: Dict[str, Any]) -> Optional[str]:
    ident = entreprise.get("identification") or {}
    adresse = ident.get("adresse") or {}
    ville = adresse.get("ville")
    if ville and str(ville).strip():
        return str(ville).strip()
    return None


def resoudre_taux_vm_officiel(
    taux_vmrr: Any,
    commune: Optional[str],
    *,
    alertes: Optional[List[Dict[str, Any]]] = None,
) -> Optional[float]:
    """
    Taux VM applicable depuis le barème scrapé URSSAF (taux_vmrr) et la commune.
    Aucune valeur en dur : None + alerte si barème, commune ou ligne absents.
    """
    commune_clean = str(commune).strip() if commune else ""
    if not commune_clean:
        _ajouter_alerte(
            alertes,
            code="vm_commune_absente",
            cle="taux_vmrr",
            chemin=[],
            critique=False,
            message="Commune entreprise absente — taux VM non résolu depuis le barème scrapé",
        )
        return None

    if not taux_vmrr:
        _ajouter_alerte(
            alertes,
            code="vm_bareme_absent",
            cle="taux_vmrr",
            chemin=[],
            critique=False,
            message=(
                "Barème taux_vmrr absent — synchronisez la source "
                "« Versement mobilité » (VM) dans les référentiels taux"
            ),
        )
        return None

    rows = _lignes_vmrr(taux_vmrr)
    if not rows:
        _ajouter_alerte(
            alertes,
            code="vm_bareme_vide",
            cle="taux_vmrr",
            chemin=[],
            critique=False,
            message="Barème taux_vmrr vide — relancez le scraping VM",
        )
        return None

    commune_norm = _normaliser_libelle_commune(commune_clean)

    # 1) Égalité exacte (prioritaire) — évite EU⊂MAGNIEU, RI⊂CERIZAY
    for row in rows:
        lib = _normaliser_libelle_commune(_libelle_commune_vmrr(row))
        if lib and lib == commune_norm:
            taux = _taux_ligne_vmrr(row)
            if taux is not None:
                return taux

    # 2) Contenance ville → libellé plus long uniquement (ex. « Aix » ⊂ « Aix en Provence »)
    #    Jamais l'inverse (libellé court ⊂ ville).
    if len(commune_norm) >= 4:
        for row in rows:
            lib = _normaliser_libelle_commune(_libelle_commune_vmrr(row))
            if lib and commune_norm in lib and lib != commune_norm:
                taux = _taux_ligne_vmrr(row)
                if taux is not None:
                    return taux

    _ajouter_alerte(
        alertes,
        code="vm_commune_introuvable",
        cle="taux_vmrr",
        chemin=[commune_clean],
        critique=False,
        message=(
            f"Taux VM introuvable pour « {commune_clean} » dans le barème scrapé taux_vmrr"
        ),
    )
    return None


def _normaliser_libelle_commune(value: str) -> str:
    """Normalise un libellé commune pour comparaison VM (casse, tirets, espaces)."""
    s = str(value or "").strip().lower()
    for old, new in (("-", " "), ("'", " "), ("’", " ")):
        s = s.replace(old, new)
    return " ".join(s.split())


def taux_vm_entreprise_depuis_donnees(entreprise: Dict[str, Any]) -> Optional[float]:
    raw = (
        (entreprise.get("parametres_paie") or {})
        .get("taux_specifiques", {})
        .get("taux_versement_mobilite")
    )
    if raw is None:
        return None
    return _normaliser_taux_vm_decimal(raw)


def resoudre_taux_vm_pour_paie(
    baremes: Dict[str, Any],
    entreprise: Dict[str, Any],
    *,
    alertes: Optional[List[Dict[str, Any]]] = None,
) -> Optional[float]:
    """
    Taux VM pour le calcul du bulletin :
    1. Barème scrapé taux_vmrr + commune (prioritaire)
    2. Repli fiche entreprise (taux_vm) si le barème n'est pas encore synchronisé
    3. Alerte seulement si aucune des deux sources n'est utilisable
    """
    commune = commune_entreprise_depuis_donnees(entreprise)
    taux_vmrr = baremes.get("taux_vmrr")
    taux_officiel = resoudre_taux_vm_officiel(taux_vmrr, commune, alertes=None)
    if taux_officiel is not None:
        return taux_officiel

    taux_entreprise = taux_vm_entreprise_depuis_donnees(entreprise)
    if taux_entreprise is not None:
        return taux_entreprise

    if not commune:
        _ajouter_alerte(
            alertes,
            code="vm_commune_absente",
            cle="taux_vmrr",
            chemin=[],
            critique=False,
            message="Commune entreprise absente — taux VM non résolu",
        )
        return None

    if not taux_vmrr:
        _ajouter_alerte(
            alertes,
            code="vm_bareme_absent",
            cle="taux_vmrr",
            chemin=[],
            critique=False,
            message=(
                "Barème taux_vmrr absent et aucun taux VM sur la fiche entreprise — "
                "synchronisez la source « Versement mobilité » (VM) ou renseignez le taux"
            ),
        )
        return None

    return resoudre_taux_vm_officiel(taux_vmrr, commune, alertes=alertes)


def comparer_taux_vm_entreprise(
    taux_entreprise: Optional[float],
    taux_vmrr: Any,
    *,
    commune: Optional[str] = None,
    tolerance: float = 0.001,
) -> Optional[Dict[str, Any]]:
    """
    Contrôle optionnel : taux VM saisi manuellement sur l'entreprise vs barème scrapé.
    Si aucune surcharge (null ou 0), le barème scrapé fait foi — pas d'alerte ici.
    """
    if taux_entreprise is None:
        return None

    try:
        te = float(taux_entreprise)
    except (TypeError, ValueError):
        return {
            "code": "vm_entreprise_invalide",
            "severity": "warning",
            "message": "Taux VM entreprise non numérique",
        }

    if abs(te) > 1:
        te = te / 100.0

    if abs(te) <= 1e-9:
        return None

    taux_officiel = resoudre_taux_vm_officiel(taux_vmrr, commune, alertes=None)
    if taux_officiel is None:
        if not taux_vmrr:
            return {
                "code": "vm_bareme_absent",
                "severity": "info",
                "message": (
                    "Barème taux_vmrr absent — impossible de contrôler la surcharge VM "
                    "entreprise"
                ),
            }
        return None

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
