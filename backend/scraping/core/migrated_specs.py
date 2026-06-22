"""
Définitions RateSpec pour tous les taux (migration DRY).

Chaque dossier importe : from core.migrated_specs import SPEC_XXX
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from core.cotisation_helpers import (
    equal_sections_keys,
    patch_cotisation_fields,
    payload_sections,
)
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import (
    ValidationResult,
    validate_csg_valeurs,
    validate_ij_plafonds,
    validate_pss_sections,
    require_float_range,
    require_non_null_patronal,
)

SCRAPING_ROOT = Path(__file__).resolve().parent.parent


def _dir(name: str) -> Path:
    return SCRAPING_ROOT / name


def _scripts(
    folder: str,
    names: list[str],
    *,
    ai_enabled: bool = True,
    legisocial_blocking: bool = False,
    primary_blocking: bool = True,
) -> list[ScraperScript]:
    d = _dir(folder)
    out: list[ScraperScript] = []
    for n in names:
        blocking = True
        if n.endswith("_AI.py"):
            if not ai_enabled:
                continue
            blocking = False
        elif "LegiSocial" in n:
            blocking = not legisocial_blocking
        elif not primary_blocking and not n.endswith("_AI.py") and "LegiSocial" not in n:
            blocking = False
        out.append(ScraperScript(n, str(d / n), blocking=blocking))
    return out


# --- PSS ---


def _pss_extract(p: dict) -> dict:
    s = p.get("sections", {})
    return {
        k: v
        for k, v in s.items()
        if v is not None and isinstance(v, (int, float)) and k != "annee"
    }


def _pss_equal(a: dict, b: dict) -> bool:
    keys = set(a) | set(b)
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        fa, fb = float(va), float(vb)
        if fa == 0 and fb == 0:
            continue
        if abs(fa - fb) / max(abs(fa), abs(fb), 1) > 0.01:
            return False
    return True


SPEC_PSS = RateSpec(
    scraper_name="PSS",
    config_key="pss",
    scripts=_scripts("PSS", ["PSS.py", "PSS_AI.py"]),
    extract_signature=_pss_extract,
    signatures_equal=_pss_equal,
    validate_signature=lambda s: validate_pss_sections({**s, "annee": __import__("datetime").datetime.now().year}),
    build_config_data=lambda sig, _c: sig,
    persistence_mode=PersistenceMode.FULL,
    primary_label="PSS.py",
    script_timeout=180,
)


# --- CSG ---


def _csg_extract(p: dict) -> dict:
    return p.get("valeurs") or {}


def _csg_equal(a: dict, b: dict) -> bool:
    sa, sb = a.get("salarial") or {}, b.get("salarial") or {}
    for k in ("deductible", "non_deductible"):
        if not math.isclose(
            float(sa.get(k, 0)), float(sb.get(k, 0)), abs_tol=1e-9
        ):
            return False
    return True


def _csg_build(sig: dict, current: Optional[dict]) -> dict:
    cur = current["config_data"] if current else None
    return patch_cotisation_fields(
        cur,
        patches=[("csg", {"valeurs": sig, "base": "brut"})],
        default_new_items={
            "csg": {
                "id": "csg",
                "libelle": "CSG/CRDS",
                "base": "brut",
            }
        },
    )


SPEC_CSG = RateSpec(
    scraper_name="CSG",
    config_key="cotisations",
    scripts=_scripts(
        "CSG",
        ["CSG.py", "CSG_AI.py"],
        ai_enabled=True,
    ),
    extract_signature=_csg_extract,
    signatures_equal=_csg_equal,
    validate_signature=validate_csg_valeurs,
    build_config_data=_csg_build,
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="CSG.py",
)


# --- IJ ---


def _ij_extract(p: dict) -> dict:
    return p.get("valeurs", {})


def _ij_equal(a: dict, b: dict) -> bool:
    for k in ("maladie", "maternite_paternite", "at_mp", "at_mp_majoree"):
        va, vb = a.get(k), b.get(k)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if not math.isclose(float(va), float(vb), abs_tol=0.01):
            return False
    return True


SPEC_IJ_MALADIE = RateSpec(
    scraper_name="IJmaladie",
    config_key="ij_plafonds",
    scripts=_scripts(
        "IJmaladie",
        ["IJmaladie.py", "IJmaladie_AI.py"],
    ),
    extract_signature=_ij_extract,
    signatures_equal=_ij_equal,
    validate_signature=validate_ij_plafonds,
    build_config_data=lambda sig, _c: sig,
    persistence_mode=PersistenceMode.FULL,
    primary_label="IJmaladie.py",
    script_timeout=180,
)


def _patronal_only_spec(
    folder: str,
    scraper_name: str,
    item_id: str,
    libelle: str,
    scripts: list[str],
    primary: str,
) -> RateSpec:
    def extract(p: dict) -> dict:
        v = p.get("valeurs") or payload_sections(p)
        return {"patronal": v.get("patronal")}

    def equal(a: dict, b: dict) -> bool:
        pa, pb = a.get("patronal"), b.get("patronal")
        if pa is None or pb is None:
            return pa is pb
        return math.isclose(float(pa), float(pb), abs_tol=1e-9)

    def build(sig: dict, current: Optional[dict]) -> dict:
        cur = current["config_data"] if current else None
        return patch_cotisation_fields(
            cur,
            patches=[(item_id, {"patronal": sig["patronal"]})],
            default_new_items={
                item_id: {
                    "id": item_id,
                    "libelle": libelle,
                    "base": "brut",
                }
            },
        )

    return RateSpec(
        scraper_name=scraper_name,
        config_key="cotisations",
        scripts=_scripts(folder, scripts),
        extract_signature=extract,
        signatures_equal=equal,
        validate_signature=lambda s: require_non_null_patronal(s),
        build_config_data=build,
        persistence_mode=PersistenceMode.COTISATIONS,
        primary_label=primary,
        signature_for_emit=lambda s: s,
    )


SPEC_AGS = _patronal_only_spec(
    "AGS",
    "AGS",
    "ags",
    "AGS",
    ["AGS.py", "AGS_AI.py"],
    "AGS.py",
)

SPEC_CSA = _patronal_only_spec(
    "CSA",
    "CSA",
    "csa",
    "Contribution solidarité autonomie (CSA)",
    ["CSA.py", "CSA_AI.py"],
    "CSA.py",
)

SPEC_ASSURANCE_CHOMAGE = _patronal_only_spec(
    "assurancechomage",
    "assurancechomage",
    "assurance_chomage",
    "Assurance chômage",
    [
        "assurancechomage.py",
        "assurancechomage_AI.py",
    ],
    "assurancechomage.py",
)


def _alloc_extract(p: dict) -> dict:
    v = p.get("valeurs") or {}
    return {"plein": v.get("patronal_plein"), "reduit": v.get("patronal_reduit")}


def _alloc_build(sig: dict, current: Optional[dict]) -> dict:
    cur = current["config_data"] if current else None
    return patch_cotisation_fields(
        cur,
        patches=[
            (
                "allocations_familiales",
                {
                    "patronal_plein": sig["plein"],
                    "patronal_reduit": sig["reduit"],
                },
            )
        ],
        default_new_items={
            "allocations_familiales": {
                "id": "allocations_familiales",
                "libelle": "Allocations familiales",
                "base": "brut",
            }
        },
    )


SPEC_ALLOC = RateSpec(
    scraper_name="alloc",
    config_key="cotisations",
    scripts=_scripts("alloc", ["alloc.py", "alloc_AI.py"]),
    extract_signature=_alloc_extract,
    signatures_equal=lambda a, b: equal_sections_keys(
        a, b, ["plein", "reduit"], abs_tol=1e-9
    ),
    validate_signature=lambda s: ValidationResult(
        s.get("plein") is not None and s.get("reduit") is not None,
        "taux alloc manquants",
    ),
    build_config_data=_alloc_build,
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="alloc.py",
)


def _vieillesse_spec(dirname: str, scraper_name: str, *, salarial: bool) -> RateSpec:
    field = "salarial" if salarial else "patronal"
    ids = ("retraite_secu_plafond", "retraite_secu_deplafond")
    scripts_list = [
        f"{dirname}.py",
        f"{dirname}_AI.py",
    ]

    def extract(p: dict) -> dict:
        return payload_sections(p)

    def equal(a: dict, b: dict) -> bool:
        return equal_sections_keys(a, b, ["plafonne", "deplafonne"], abs_tol=1e-6)

    def validate(sig: dict) -> ValidationResult:
        if sig.get("plafonne") is None or sig.get("deplafonne") is None:
            return ValidationResult(False, "plafonne/deplafonne manquant")
        return ValidationResult(True)

    def build(sig: dict, current: Optional[dict]) -> dict:
        cur = current["config_data"] if current else None
        patches = [
            (ids[0], {field: sig["plafonne"]}),
            (ids[1], {field: sig["deplafonne"]}),
        ]
        defaults = {
            ids[0]: {
                "id": ids[0],
                "libelle": "Sécurité sociale Vieillesse plafonnée",
                "base": "brut_plafonne",
            },
            ids[1]: {
                "id": ids[1],
                "libelle": "Sécurité sociale Vieillesse déplafonnée",
                "base": "brut",
            },
        }
        if salarial:
            defaults[ids[0]]["patronal"] = 0.0855
            defaults[ids[1]]["patronal"] = 0.0202
        else:
            defaults[ids[0]]["salarial"] = 0.069
            defaults[ids[1]]["salarial"] = 0.004
        return patch_cotisation_fields(cur, patches=patches, default_new_items=defaults)

    return RateSpec(
        scraper_name=scraper_name,
        config_key="cotisations",
        scripts=_scripts(dirname, scripts_list),
        extract_signature=extract,
        signatures_equal=equal,
        validate_signature=validate,
        build_config_data=build,
        persistence_mode=PersistenceMode.COTISATIONS,
        primary_label=f"{dirname}.py",
    )


SPEC_VIEILLESSE_PATRONAL = _vieillesse_spec(
    "vieillessepatronal", "vieillessepatronal", salarial=False
)
SPEC_VIEILLESSE_SALARIAL = _vieillesse_spec(
    "vieillessesalarial", "vieillessesalarial", salarial=True
)


# --- CFP ---


def _cfp_extract(p: dict) -> dict:
    s = payload_sections(p)
    return {"moins_11": s.get("patronal_moins_11"), "plus_11": s.get("patronal_11_et_plus")}


def _cfp_build(sig: dict, current: Optional[dict]) -> dict:
    cur = current["config_data"] if current else None
    return patch_cotisation_fields(
        cur,
        patches=[
            (
                "CFP",
                {
                    "patronal": {
                        "taux_moins_11": sig["moins_11"],
                        "taux_11_et_plus": sig["plus_11"],
                    }
                },
            )
        ],
        default_new_items={
            "CFP": {"id": "CFP", "libelle": "Contribution formation professionnelle", "base": "brut"}
        },
    )


SPEC_CFP = RateSpec(
    scraper_name="CFP",
    config_key="cotisations",
    scripts=_scripts("CFP", ["CFP.py", "CFP_AI.py"]),
    extract_signature=_cfp_extract,
    signatures_equal=lambda a, b: equal_sections_keys(
        a, b, ["moins_11", "plus_11"], abs_tol=1e-9
    ),
    validate_signature=lambda s: ValidationResult(
        s.get("moins_11") is not None and s.get("plus_11") is not None,
        "taux CFP incomplets",
    ),
    build_config_data=_cfp_build,
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="CFP.py",
)


# --- FNAL ---


def _fnal_extract(p: dict) -> dict:
    s = payload_sections(p)
    return {"moins_50": s.get("patronal_moins_50"), "plus_50": s.get("patronal_50_et_plus")}


SPEC_FNAL = RateSpec(
    scraper_name="FNAL",
    config_key="cotisations",
    scripts=_scripts("FNAL", ["FNAL.py", "FNAL_AI.py"]),
    extract_signature=_fnal_extract,
    signatures_equal=lambda a, b: equal_sections_keys(
        a, b, ["moins_50", "plus_50"], abs_tol=1e-9
    ),
    validate_signature=lambda s: ValidationResult(
        s.get("moins_50") is not None and s.get("plus_50") is not None,
        "taux FNAL incomplets",
    ),
    build_config_data=lambda sig, cur: patch_cotisation_fields(
        cur["config_data"] if cur else None,
        patches=[
            (
                "fnal",
                {
                    "patronal": {
                        "taux_moins_50": sig["moins_50"],
                        "taux_50_et_plus": sig["plus_50"],
                    }
                },
            )
        ],
        default_new_items={
            "fnal": {"id": "fnal", "libelle": "FNAL", "base": "brut"},
        },
    ),
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="FNAL.py",
)


# --- MMID patronal ---


def _mmid_pat_extract(p: dict) -> dict:
    s = payload_sections(p)
    return {"plein": s.get("patronal_plein"), "reduit": s.get("patronal_reduit")}


SPEC_MMID_PATRONAL = RateSpec(
    scraper_name="MMIDpatronal",
    config_key="cotisations",
    scripts=_scripts(
        "MMIDpatronal",
        ["MMIDpatronal.py", "MMIDpatronal_AI.py"],
    ),
    extract_signature=_mmid_pat_extract,
    signatures_equal=lambda a, b: equal_sections_keys(
        a, b, ["plein", "reduit"], abs_tol=1e-9
    ),
    validate_signature=lambda s: ValidationResult(
        s.get("plein") is not None and s.get("reduit") is not None,
        "MMID patronal incomplet",
    ),
    build_config_data=lambda sig, cur: patch_cotisation_fields(
        cur["config_data"] if cur else None,
        patches=[
            (
                "securite_sociale_maladie",
                {"patronal_plein": sig["plein"], "patronal_reduit": sig["reduit"]},
            )
        ],
        default_new_items={
            "securite_sociale_maladie": {
                "id": "securite_sociale_maladie",
                "libelle": "Sécurité sociale — Maladie",
                "base": "brut",
            }
        },
    ),
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="MMIDpatronal.py",
)


# --- MMID salarial (Alsace-Moselle) ---


def _mmid_sal_extract(p: dict) -> dict:
    s = payload_sections(p)
    return {"alsace": s.get("alsace_moselle", {}).get("taux_salarial") if isinstance(s.get("alsace_moselle"), dict) else s.get("salarial_Alsace_Moselle")}


SPEC_MMID_SALARIAL = RateSpec(
    scraper_name="MMIDsalarial",
    config_key="cotisations",
    scripts=_scripts(
        "MMIDsalarial",
        ["MMIDsalarial.py", "MMIDsalarial_AI.py"],
    ),
    extract_signature=lambda p: {
        "alsace": (p.get("sections") or {}).get("alsace_moselle", {}).get("taux_salarial")
        or (p.get("valeurs") or {}).get("salarial_Alsace_Moselle")
    },
    signatures_equal=lambda a, b: (
        a.get("alsace") is not None
        and b.get("alsace") is not None
        and math.isclose(float(a["alsace"]), float(b["alsace"]), abs_tol=1e-9)
    ),
    validate_signature=lambda s: require_float_range(
        s.get("alsace"), name="salarial_Alsace_Moselle", min_v=0.0, max_v=0.05
    ),
    build_config_data=lambda sig, cur: patch_cotisation_fields(
        cur["config_data"] if cur else None,
        patches=[("securite_sociale_maladie", {"salarial_Alsace_Moselle": sig["alsace"]})],
        default_new_items={
            "securite_sociale_maladie": {
                "id": "securite_sociale_maladie",
                "libelle": "Sécurité sociale — Maladie",
                "base": "brut",
            }
        },
    ),
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="MMIDsalarial.py",
)

