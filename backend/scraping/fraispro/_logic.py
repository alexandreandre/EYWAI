"""Normalisation, comparaison et build pour frais professionnels."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.validation import ValidationResult
from utils import is_non_blocking_scraper_label

ITEM_ID = "frais_pro"


def _norm_label(text: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(text or "")
        .replace("\xa0", " ")
        .replace("\u202f", " ")
        .strip(),
    ).lower()


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v), 6)
    except Exception:
        return None


def _norm_repas(d: Dict[str, Any]) -> Dict[str, Optional[float]]:
    d = d or {}
    return {
        "sur_lieu_travail": _f(d.get("sur_lieu_travail")),
        "hors_locaux_avec_restaurant": _f(d.get("hors_locaux_avec_restaurant")),
        "hors_locaux_sans_restaurant": _f(d.get("hors_locaux_sans_restaurant")),
    }


def _norm_petit_dep(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append(
            {
                "km_min": int(x.get("km_min")),
                "km_max": int(x.get("km_max")),
                "montant": _f(x.get("montant")),
            }
        )
    out.sort(key=lambda z: (z["km_min"], z["km_max"]))
    return out


def _norm_metropole(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append(
            {
                "periode_sejour": _norm_label(x.get("periode_sejour")),
                "repas": _f(x.get("repas")),
                "logement_paris_banlieue": _f(x.get("logement_paris_banlieue")),
                "logement_province": _f(x.get("logement_province")),
            }
        )
    out.sort(key=lambda z: z["periode_sejour"])
    return out


def _norm_outre_mer(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append(
            {
                "periode_sejour": _norm_label(x.get("periode_sejour")),
                "hebergement": _f(x.get("hebergement")),
                "repas": _f(x.get("repas")),
            }
        )
    out.sort(key=lambda z: z["periode_sejour"])
    return out


def _norm_mutation(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    hp = d.get("hebergement_provisoire") or {}
    hd = d.get("hebergement_definitif") or {}
    return {
        "hebergement_provisoire": {"montant_par_jour": _f(hp.get("montant_par_jour"))},
        "hebergement_definitif": {
            "frais_installation": _f(hd.get("frais_installation")),
            "majoration_par_enfant": _f(hd.get("majoration_par_enfant")),
            "plafond_total": _f(hd.get("plafond_total")),
        },
    }


def _norm_mobilite(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    priv = d.get("employeurs_prives") or {}
    pubs = []
    for x in d.get("employeurs_publics") or []:
        pubs.append(
            {
                "jours_utilises": _norm_label(x.get("jours_utilises")),
                "montant_annuel": _f(x.get("montant_annuel")),
            }
        )
    pubs.sort(key=lambda z: z["jours_utilises"])
    return {
        "employeurs_prives": {
            "limite_base": _f(priv.get("limite_base")),
            "limite_cumul_transport_public": _f(
                priv.get("limite_cumul_transport_public")
            ),
            "limite_cumul_carburant_total": _f(
                priv.get("limite_cumul_carburant_total")
            ),
            "limite_cumul_carburant_part_carburant": _f(
                priv.get("limite_cumul_carburant_part_carburant")
            ),
        },
        "employeurs_publics": pubs,
    }


def _norm_teletravail(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    sans = d.get("indemnite_sans_accord") or {}
    avec = d.get("indemnite_avec_accord") or {}
    mat = d.get("materiel_informatique_perso") or {}
    return {
        "indemnite_sans_accord": {
            "par_jour": _f(sans.get("par_jour")),
            "limite_mensuelle": _f(sans.get("limite_mensuelle")),
            "par_mois_pour_1_jour_semaine": _f(
                sans.get("par_mois_pour_1_jour_semaine")
            ),
        },
        "indemnite_avec_accord": {k: _f(v) for k, v in avec.items()}
        if isinstance(avec, dict)
        else {},
        "materiel_informatique_perso": {
            "montant_mensuel": _f(mat.get("montant_mensuel"))
        },
    }


def sig_valid(sig: Dict[str, Any]) -> bool:
    """Données minimales : forfaits repas URSSAF non nuls."""
    repas = (sig.get("sections") or {}).get("repas") or {}
    keys = (
        "sur_lieu_travail",
        "hors_locaux_avec_restaurant",
        "hors_locaux_sans_restaurant",
    )
    vals = [repas.get(k) for k in keys]
    if not any(v is not None and float(v) > 0 for v in vals):
        return False
    return all(
        repas.get(k) is not None and float(repas.get(k)) > 0 for k in keys
    )


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise le payload complet de frais_pro."""
    if payload.get("id") != ITEM_ID:
        raise ValueError(
            f"ID '{ITEM_ID}' attendu, reçu '{payload.get('id')}'"
        )

    sections = payload.get("sections", {}) or {}
    return {
        "id": ITEM_ID,
        "libelle": payload.get("libelle", "Frais professionnels"),
        "sections": {
            "repas": _norm_repas(sections.get("repas")),
            "petit_deplacement": _norm_petit_dep(sections.get("petit_deplacement")),
            "grand_deplacement": {
                "metropole": _norm_metropole(
                    (sections.get("grand_deplacement") or {}).get("metropole")
                ),
                "outre_mer_groupe1": _norm_outre_mer(
                    (sections.get("grand_deplacement") or {}).get("outre_mer_groupe1")
                ),
                "outre_mer_groupe2": _norm_outre_mer(
                    (sections.get("grand_deplacement") or {}).get("outre_mer_groupe2")
                ),
            },
            "mutation_professionnelle": _norm_mutation(
                sections.get("mutation_professionnelle")
            ),
            "mobilite_durable": _norm_mobilite(sections.get("mobilite_durable")),
            "teletravail": _norm_teletravail(sections.get("teletravail")),
        },
    }


def accept_payload(label: str, payload: Dict[str, Any]) -> bool:
    try:
        sig = core_signature(payload)
    except ValueError:
        return False
    if sig_valid(sig):
        return True
    if is_non_blocking_scraper_label(label):
        return False
    return True


def _eq_float(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def _eq_repas(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return all(
        _eq_float(a.get(k), b.get(k))
        for k in (
            "sur_lieu_travail",
            "hors_locaux_avec_restaurant",
            "hors_locaux_sans_restaurant",
        )
    )


def _eq_petit_dep(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x["km_min"] != y["km_min"] or x["km_max"] != y["km_max"]:
            return False
        if not _eq_float(x["montant"], y["montant"]):
            return False
    return True


def _eq_metropole(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False

    def _sort_key(row: Dict[str, Any]) -> tuple:
        return (
            -float(row.get("repas") or 0),
            -float(row.get("logement_paris_banlieue") or 0),
            -float(row.get("logement_province") or 0),
        )

    for x, y in zip(sorted(a, key=_sort_key), sorted(b, key=_sort_key)):
        if not (
            _eq_float(x.get("repas"), y.get("repas"))
            and _eq_float(x.get("logement_paris_banlieue"), y.get("logement_paris_banlieue"))
            and _eq_float(x.get("logement_province"), y.get("logement_province"))
        ):
            return False
    return True


def _eq_outre_mer(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False

    def _sort_key(row: Dict[str, Any]) -> tuple:
        return (
            -float(row.get("repas") or 0),
            -float(row.get("hebergement") or 0),
        )

    for x, y in zip(sorted(a, key=_sort_key), sorted(b, key=_sort_key)):
        if not (
            _eq_float(x.get("hebergement"), y.get("hebergement"))
            and _eq_float(x.get("repas"), y.get("repas"))
        ):
            return False
    return True


def _eq_mutation(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        _eq_float(
            a["hebergement_provisoire"].get("montant_par_jour"),
            b["hebergement_provisoire"].get("montant_par_jour"),
        )
        and _eq_float(
            a["hebergement_definitif"].get("frais_installation"),
            b["hebergement_definitif"].get("frais_installation"),
        )
        and _eq_float(
            a["hebergement_definitif"].get("majoration_par_enfant"),
            b["hebergement_definitif"].get("majoration_par_enfant"),
        )
        and _eq_float(
            a["hebergement_definitif"].get("plafond_total"),
            b["hebergement_definitif"].get("plafond_total"),
        )
    )


def _eq_mobilite(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa, pb = a["employeurs_prives"], b["employeurs_prives"]
    if not all(
        _eq_float(pa.get(k), pb.get(k))
        for k in (
            "limite_base",
            "limite_cumul_transport_public",
            "limite_cumul_carburant_total",
            "limite_cumul_carburant_part_carburant",
        )
    ):
        return False
    la, lb = a["employeurs_publics"], b["employeurs_publics"]
    if len(la) != len(lb):
        return False
    for x, y in zip(la, lb):
        if x["jours_utilises"] != y["jours_utilises"]:
            return False
        if not _eq_float(x["montant_annuel"], y["montant_annuel"]):
            return False
    return True


def _eq_teletravail(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    sa, sb = a["indemnite_sans_accord"], b["indemnite_sans_accord"]
    if not all(
        _eq_float(sa.get(k), sb.get(k))
        for k in ("par_jour", "limite_mensuelle", "par_mois_pour_1_jour_semaine")
    ):
        return False
    aa, ab = a.get("indemnite_avec_accord", {}), b.get("indemnite_avec_accord", {})
    if set(aa.keys()) != set(ab.keys()):
        return False
    for k in aa.keys():
        if not _eq_float(_f(aa[k]), _f(ab[k])):
            return False
    ma, mb = a["materiel_informatique_perso"], b["materiel_informatique_perso"]
    return _eq_float(ma.get("montant_mensuel"), mb.get("montant_mensuel"))


def equal_core(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Compare deux signatures 'frais_pro' complètes."""
    sa, sb = a["sections"], b["sections"]
    return (
        _eq_repas(sa["repas"], sb["repas"])
        and _eq_petit_dep(sa["petit_deplacement"], sb["petit_deplacement"])
        and _eq_metropole(
            sa["grand_deplacement"]["metropole"], sb["grand_deplacement"]["metropole"]
        )
        and _eq_outre_mer(
            sa["grand_deplacement"]["outre_mer_groupe1"],
            sb["grand_deplacement"]["outre_mer_groupe1"],
        )
        and _eq_outre_mer(
            sa["grand_deplacement"]["outre_mer_groupe2"],
            sb["grand_deplacement"]["outre_mer_groupe2"],
        )
        and _eq_mutation(sa["mutation_professionnelle"], sb["mutation_professionnelle"])
        and _eq_mobilite(sa["mobilite_durable"], sb["mobilite_durable"])
        and _eq_teletravail(sa["teletravail"], sb["teletravail"])
    )


def validate_signature(sig: Dict[str, Any]) -> ValidationResult:
    if not sig_valid(sig):
        return ValidationResult(False, "forfaits repas incomplets ou nuls")
    return ValidationResult(True)


def build_config_data(sig: Dict[str, Any], _current: Optional[dict]) -> Dict[str, Any]:
    return {"FRAIS_PRO": [sig]}
